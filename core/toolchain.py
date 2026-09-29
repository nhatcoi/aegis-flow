"""Compile generated C code with sanitizers and run it on malicious inputs (Chương 2.5, 4.3).

For each C function a small harness ``main()`` is generated, compiled against
v0 and v1 with ``-fsanitize=address,undefined`` and executed. The sanitizer
log is parsed into findings, giving runtime evidence for the static findings.
Every step degrades gracefully when the compiler or cppcheck is missing.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .codegen import GeneratedFunction

SANITIZER_CWE = [
    (r"AddressSanitizer: stack-buffer-overflow", "stack-buffer-overflow", "CWE-121"),
    (r"AddressSanitizer: heap-buffer-overflow", "heap-buffer-overflow", "CWE-122"),
    (r"AddressSanitizer: attempting double-free", "double-free", "CWE-415"),
    (r"AddressSanitizer: heap-use-after-free", "heap-use-after-free", "CWE-416"),
    (r"LeakSanitizer: detected memory leaks", "memory-leak", "CWE-401"),
    (r"runtime error: signed integer overflow", "signed-integer-overflow", "CWE-190"),
    (r"runtime error: .*null pointer", "null-dereference", "CWE-476"),
]

LEAK_DETECTION = platform.system() == "Linux"  # LeakSanitizer is not supported on macOS


@dataclass
class SanitizerRun:
    function: str
    version: str  # "v0" | "v1"
    status: str  # "clean" | "detected" | "skipped" | "build-error"
    command: str = ""
    input_desc: str = ""
    returncode: int | None = None
    log: str = ""
    detections: list[tuple[str, str, int | None]] = field(default_factory=list)  # (kind, cwe, line)
    note: str = ""


def compiler() -> str | None:
    for cc in ("clang", "gcc"):
        path = shutil.which(cc)
        if path:
            return path
    return None


def compiler_version() -> str:
    cc = compiler()
    if not cc:
        return "không có"
    out = subprocess.run([cc, "--version"], capture_output=True, text=True, check=False).stdout
    return out.splitlines()[0] if out else cc


def _harness(gf: GeneratedFunction) -> tuple[str, str] | None:
    fn = gf.spec
    kind = fn.kind.lower()
    if kind == "buffer_copy":
        size = fn.buffer_size or 16
        n = size * 8
        return (
            f"""#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int {fn.name}(const char *);
int main(void) {{
    char *payload = malloc({n} + 1);
    memset(payload, 'A', {n});
    payload[{n}] = '\\0';
    int rc = {fn.name}(payload);
    printf("rc=%d\\n", rc);
    free(payload);
    return 0;
}}
""",
            f"chuỗi {n} ký tự 'A' (gấp 8 lần bộ đệm {size} byte)",
        )
    if kind == "alloc_release":
        return (
            f"""#include <stdio.h>
int {fn.name}(void);
int main(void) {{ printf("rc=%d\\n", {fn.name}()); return 0; }}
""",
            "gọi hàm một lần",
        )
    if kind == "arithmetic":
        return (
            f"""#include <limits.h>
#include <stdio.h>
int {fn.name}(int, int, int *);
int main(void) {{
    int out = 0;
    int rc = {fn.name}(INT_MAX, 1, &out);
    printf("rc=%d out=%d\\n", rc, out);
    return 0;
}}
""",
            "(INT_MAX, 1)",
        )
    return None


def _parse(log: str, source_name: str) -> list[tuple[str, str, int | None]]:
    found = []
    for pattern, kind, cwe in SANITIZER_CWE:
        m = re.search(pattern, log)
        if not m:
            continue
        line = None
        loc = re.search(rf"{re.escape(source_name)}:(\d+)", log[m.start():])
        if loc:
            line = int(loc.group(1))
        found.append((kind, cwe, line))
    return found


def run_sanitizers(gf: GeneratedFunction, version: str, workdir: Path, timeout: int = 30) -> SanitizerRun:
    code = gf.code_vulnerable if version == "v0" else gf.code_safe
    name = gf.spec.name
    harness = _harness(gf)
    if gf.language != "c" or harness is None:
        return SanitizerRun(name, version, "skipped", note="Không phải hàm C có harness.")
    cc = compiler()
    if cc is None:
        return SanitizerRun(name, version, "skipped", note="Không tìm thấy clang/gcc.")

    workdir.mkdir(parents=True, exist_ok=True)
    src = workdir / f"{name}_{version}.c"
    main = workdir / f"{name}_{version}_harness.c"
    exe = workdir / f"{name}_{version}.bin"
    src.write_text(code, encoding="utf-8")
    main.write_text(harness[0], encoding="utf-8")
    cmd = [cc, "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g", "-O0",
           "-o", str(exe), str(src), str(main)]
    build = subprocess.run(cmd, capture_output=True, text=True, check=False)
    shown = " ".join(Path(c).name if c.startswith(str(workdir)) else c for c in cmd)
    if build.returncode != 0:
        return SanitizerRun(name, version, "build-error", command=shown, log=build.stderr)

    env = dict(os.environ, ASAN_OPTIONS=f"detect_leaks={int(LEAK_DETECTION)}:halt_on_error=1",
               UBSAN_OPTIONS="print_stacktrace=1")
    try:
        proc = subprocess.run([str(exe)], capture_output=True, text=True, timeout=timeout, env=env, check=False)
        log, rc = proc.stdout + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        log, rc = "TIMEOUT", None
    finally:
        exe.unlink(missing_ok=True)
        dsym = exe.with_suffix(".bin.dSYM")
        if dsym.exists():
            shutil.rmtree(dsym, ignore_errors=True)
    detections = _parse(log, src.name)
    note = "" if LEAK_DETECTION else "LeakSanitizer không hỗ trợ trên macOS: CWE-401 chỉ có bằng chứng tĩnh."
    return SanitizerRun(name, version, "detected" if detections else "clean", command=shown,
                        input_desc=harness[1], returncode=rc, log=log, detections=detections, note=note)


def run_cppcheck(source: str, filename: str) -> str | None:
    """Return cppcheck's findings for `source`, or None when cppcheck is not installed."""
    exe = shutil.which("cppcheck")
    if exe is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / filename
        path.write_text(source, encoding="utf-8")
        proc = subprocess.run(
            [exe, "--enable=all", "--inconclusive", "--suppress=missingIncludeSystem",
             "--template={file}:{line}: [{severity}] {id}: {message} (CWE-{cwe})", str(path)],
            capture_output=True, text=True, check=False,
        )
    return "\n".join(line for line in proc.stderr.splitlines() if ": [" in line)
