"""Seeded black-box C fuzzing: one instrumented build, isolated stdin executions.

No native coverage feedback is claimed. All bytes and sanitizer logs are retained.
"""
from __future__ import annotations

import hashlib
import os
import random
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import toolchain
from .codegen import GeneratedFunction

FLAGS = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g', '-O0']
SUPPORTED = {'buffer_copy', 'arithmetic', 'alloc_release'}


@dataclass
class CFuzzResult:
    function: str
    version: str
    budget: int
    seed: int
    strategy: str = 'blackbox + ASan/UBSan'
    iterations: int = 0
    hits: int = 0
    first_hit: int | None = None
    first_input: str | None = None
    status: str = 'inconclusive'
    stop_reason: str = ''
    seconds: float = 0.0
    timeout: float = 30.0
    command: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    source: str = ''
    source_sha256: str = ''
    harness: str = ''
    build_log: str = ''
    note: str = ''
    trials: list[dict] = field(default_factory=list)

    @property
    def found(self):
        return self.hits > 0

    @property
    def verdict(self):
        if self.found:
            return 'TÌM THẤY LỖI'
        if self.status != 'clean':
            return 'CHƯA ĐỦ KẾT LUẬN'
        return 'CHƯA THẤY LỖI TRONG PHẠM VI CHẠY'


def c_harness(gf: GeneratedFunction) -> str:
    """Read exact bytes from stdin; never interpolate fuzz bytes into source/commands."""
    name, kind = gf.spec.name, gf.spec.kind.lower()
    header = '#include <stdio.h>\n#include <stdlib.h>\n#include <limits.h>\n'
    if kind == 'buffer_copy':
        return header + f'''int {name}(const char *);
int main(void) {{
    size_t cap = 256, len = 0;
    char *data = malloc(cap);
    if (!data) return 2;
    int c;
    while ((c = getchar()) != EOF) {{
        if (len + 1 >= cap) {{
            cap *= 2;
            char *next = realloc(data, cap);
            if (!next) {{ free(data); return 2; }}
            data = next;
        }}
        data[len++] = (char)c;
    }}
    data[len] = '\\0';
    int rc = {name}(data);
    printf("rc=%d\\n", rc);
    free(data);
    return 0;
}}
'''
    if kind == 'arithmetic':
        return header + f'''int {name}(int, int, int *);
int main(void) {{
    long long a, b;
    int out = 0;
    if (scanf("%lld %lld", &a, &b) != 2 || a < INT_MIN || a > INT_MAX ||
        b < INT_MIN || b > INT_MAX) return 2;
    int rc = {name}((int)a, (int)b, &out);
    printf("rc=%d out=%d\\n", rc, out);
    return 0;
}}
'''
    if kind == 'alloc_release':
        return header + f'''int {name}(void);
int main(void) {{
    int calls;
    if (scanf("%d", &calls) != 1 || calls < 1 || calls > 8) return 2;
    for (int i = 0; i < calls; ++i) printf("rc=%d\\n", {name}());
    return 0;
}}
'''
    raise ValueError('Unsupported C harness')


def generate_c_inputs(gf: GeneratedFunction, budget: int, seed: int):
    """Boundary seeds followed by seeded random mutations; yields (description, stdin)."""
    rng = random.Random(seed)
    kind = gf.spec.kind.lower()
    size = gf.spec.buffer_size or 16
    for i in range(budget):
        if kind == 'buffer_copy':
            lengths = [0, max(0, size - 1), size, size + 1, size * 8]
            length = lengths[i] if i < len(lengths) else rng.randrange(size * 8 + 1)
            payload = bytes(rng.randrange(33, 127) for _ in range(length))
            yield f'{length} bytes; payload={payload[:24]!r}', payload
        elif kind == 'arithmetic':
            pairs = [(0, 0), (1, -1), (2147483647, 1), (-2147483648, -1)]
            a, b = pairs[i] if i < len(pairs) else (rng.randint(-2147483648, 2147483647),
                                                     rng.randint(-2147483648, 2147483647))
            yield f'({a}, {b})', f'{a} {b}\n'.encode()
        elif kind == 'alloc_release':
            calls = i + 1 if i < 8 else rng.randint(1, 8)
            yield f'calls={calls}', f'{calls}\n'.encode()
        else:
            raise ValueError('Unsupported C input generator')


def fuzz_c_function(gf: GeneratedFunction, version: str, budget: int = 32, seed: int = 1,
                    timeout: float = 30.0, *, stdin: bytes | None = None) -> CFuzzResult:
    if version not in {'v0', 'v1'} or budget < 1 or timeout <= 0:
        raise ValueError('version v0/v1, budget >= 1 and timeout > 0 required')
    source = gf.code_vulnerable if version == 'v0' else gf.code_safe
    result = CFuzzResult(gf.spec.name, version, 1 if stdin is not None else budget, seed,
                         timeout=timeout, source=source,
                         source_sha256=hashlib.sha256(source.encode()).hexdigest())
    result.environment = {
        'ASAN_OPTIONS': f'detect_leaks={int(toolchain.LEAK_DETECTION)}:halt_on_error=1',
        'UBSAN_OPTIONS': 'print_stacktrace=1:halt_on_error=1',
    }
    if not toolchain.LEAK_DETECTION:
        result.note = 'LeakSanitizer tắt trên macOS; không xác nhận động CWE-401.'
    if gf.language != 'c' or gf.spec.kind.lower() not in SUPPORTED:
        result.status, result.stop_reason = 'skipped', 'unsupported_harness'
        return result
    cc = toolchain.compiler()
    if not cc:
        result.status, result.stop_reason = 'skipped', 'compiler_missing'
        return result
    result.harness = c_harness(gf)
    started = time.perf_counter()
    # TemporaryDirectory cleans binaries and debug symbol bundles even on timeout/build failure.
    with tempfile.TemporaryDirectory(prefix='aegis-c-fuzz-') as tmp:
        root = Path(tmp)
        src = root / f'{gf.spec.name}_{version}.c'
        harness = root / 'harness.c'
        exe = root / 'target.bin'
        src.write_text(source, encoding='utf-8')
        harness.write_text(result.harness, encoding='utf-8')
        result.command = [cc, *FLAGS, '-o', 'target.bin', src.name, harness.name]
        try:
            build = subprocess.run(result.command, cwd=root, capture_output=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            result.status, result.stop_reason, result.build_log = 'build-error', 'build_failed', str(exc)
        else:
            result.build_log = (build.stdout + build.stderr).decode(errors='replace')
            if build.returncode:
                result.status, result.stop_reason = 'build-error', 'build_failed'
            else:
                inputs = [('replay: exact stdin', stdin)] if stdin is not None else generate_c_inputs(gf, budget, seed)
                result.status, result.stop_reason = 'clean', 'budget_exhausted'
                for i, (description, payload) in enumerate(inputs, 1):
                    trial = _execute(exe, payload, timeout, result.environment, src.name)
                    trial.update(iteration=i, input=description, stdin_hex=payload.hex())
                    result.trials.append(trial)
                    result.iterations = i
                    if trial['detections']:
                        result.hits += 1
                        result.status = 'detected'
                        if result.first_hit is None:
                            result.first_hit, result.first_input = i, description
                        result.stop_reason = 'timeout' if trial['status'] == 'timeout' else 'first_hit'
                        break
                    if trial['status'] in {'timeout', 'crash', 'execution-error'}:
                        if not result.found:
                            result.status = 'inconclusive'
                        result.stop_reason = trial['status']
                        break
    result.seconds = time.perf_counter() - started
    return result


def _execute(exe, payload, timeout, overrides, source_name):
    try:
        proc = subprocess.run([str(exe)], input=payload, capture_output=True, timeout=timeout,
                              env=dict(os.environ, **overrides), check=False)
    except subprocess.TimeoutExpired as exc:
        log = ((exc.stdout or b'') + (exc.stderr or b'')).decode(errors='replace')
        return {'status': 'timeout', 'returncode': None, 'detections': toolchain._parse(log, source_name),
                'log': log}
    except OSError as exc:
        return {'status': 'execution-error', 'returncode': None, 'detections': [], 'log': str(exc)}
    log = (proc.stdout + proc.stderr).decode(errors='replace')
    detections = toolchain._parse(log, source_name)
    status = 'detected' if detections else ('crash' if proc.returncode else 'clean')
    return {'status': status, 'returncode': proc.returncode, 'detections': detections, 'log': log}


def replay_c_input(gf: GeneratedFunction, stdin_hex: str, timeout: float = 30.0) -> list[dict]:
    payload = bytes.fromhex(stdin_hex)
    return [asdict(fuzz_c_function(gf, v, timeout=timeout, stdin=payload)) for v in ('v0', 'v1')]
