"""Pattern-based, intra-procedural static analyzer for C (Chương 2.5).

Each function body is scanned line by line while tracking the lifecycle of
heap pointers (allocated -> checked -> freed). It is deliberately simple:
no alias analysis and no inter-procedural flow, so it is neither sound nor
complete — its findings are confirmed dynamically with ASan (core/toolchain).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

RULES = {
    "dangerous-function": ("CWE-120", "HIGH", "Buffer Copy without Checking Size of Input"),
    "gets": ("CWE-242", "HIGH", "Use of Inherently Dangerous Function"),
    "format-string": ("CWE-134", "HIGH", "Use of Externally-Controlled Format String"),
    "malloc-unchecked": ("CWE-690", "MEDIUM", "Unchecked Return Value to NULL Pointer Dereference"),
    "malloc-size-overflow": ("CWE-680", "MEDIUM", "Integer Overflow to Buffer Overflow"),
    "double-free": ("CWE-415", "HIGH", "Double Free"),
    "use-after-free": ("CWE-416", "HIGH", "Use After Free"),
    "memory-leak": ("CWE-401", "MEDIUM", "Missing Release of Memory after Effective Lifetime"),
}

DANGEROUS = {"strcpy": "strnlen + memcpy", "strcat": "strncat / snprintf", "sprintf": "snprintf",
             "vsprintf": "vsnprintf"}
ALLOC_RE = re.compile(
    r"\b(\w+)\s*=\s*(?:\([^)]*\)\s*)?(malloc|calloc|realloc)\s*\(((?:[^()]|\([^()]*\))*)\)")
FREE_RE = re.compile(r"\bfree\s*\(\s*(\w+)\s*\)")
FUNC_RE = re.compile(r"^[A-Za-z_][\w\s\*]*?\b([A-Za-z_]\w*)\s*\([^;{]*\)\s*\{", re.MULTILINE)


@dataclass
class Finding:
    rule: str
    cwe: str
    severity: str
    function: str
    line: int
    code: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def _strip_comments(src: str) -> str:
    """Blank out comments and string literals, keeping offsets and line numbers."""
    def blank(m: re.Match) -> str:
        text = m.group(0)
        if text.startswith('"'):
            return '"' + re.sub(r"[^\n]", " ", text[1:-1]) + '"'
        return re.sub(r"[^\n]", " ", text)
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"', blank, src, flags=re.DOTALL)


def _functions(clean: str):
    """Yield (name, first_line_no, [body lines]) for every function definition."""
    for m in FUNC_RE.finditer(clean):
        depth, i = 0, m.end() - 1
        while i < len(clean):
            if clean[i] == "{":
                depth += 1
            elif clean[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        start_line = clean.count("\n", 0, m.start()) + 1
        yield m.group(1), start_line, clean[m.start():i + 1].split("\n")


def _uses(ptr: str, line: str) -> bool:
    """True if the line dereferences or passes `ptr` (not a reassignment or NULL test)."""
    if re.search(rf"\b{ptr}\s*=(?!=)", line) or FREE_RE.search(line):
        return False
    if re.search(rf"\b{ptr}\s*(==|!=)\s*NULL|NULL\s*(==|!=)\s*{ptr}|!\s*{ptr}\b", line):
        return False
    return bool(re.search(rf"\*\s*{ptr}\b|\b{ptr}\s*(\[|->)|[(,]\s*{ptr}\s*[,)]", line))


def _null_checked(ptr: str, line: str) -> bool:
    return bool(re.search(rf"if\s*\(\s*(!\s*{ptr}\b|{ptr}\s*==\s*NULL|NULL\s*==\s*{ptr}|{ptr}\s*\))", line))


def analyze_c_source(source: str, filename: str = "<source>") -> list[Finding]:
    clean = _strip_comments(source)
    raw_lines = source.split("\n")
    findings: list[Finding] = []

    def add(rule: str, func: str, line_no: int, message: str) -> None:
        cwe, sev, _ = RULES[rule]
        code = raw_lines[line_no - 1].strip() if 0 < line_no <= len(raw_lines) else ""
        findings.append(Finding(rule, cwe, sev, func, line_no, code, message))

    for func, start, body in _functions(clean):
        state: dict[str, dict] = {}  # ptr -> {"line", "checked", "freed_at"}
        segments = [(offset, seg) for offset, text in enumerate(body) for seg in text.split(";")]
        for idx, (offset, line) in enumerate(segments):
            n = start + offset
            for name, fix in DANGEROUS.items():
                if re.search(rf"\b{name}\s*\(", line):
                    add("dangerous-function", func, n, f"Gọi '{name}()' không giới hạn kích thước đích — dùng {fix}.")
            if re.search(r"\bgets\s*\(", line):
                add("gets", func, n, "Gọi 'gets()' (đã bị loại khỏi C11) — dùng fgets.")
            fmt = re.search(r"\b(printf|syslog)\s*\(\s*([A-Za-z_]\w*)\s*[,)]", line) or re.search(
                r"\bfprintf\s*\(\s*\w+\s*,\s*([A-Za-z_]\w*)\s*[,)]", line)
            if fmt:
                add("format-string", func, n, f"Chuỗi định dạng lấy từ biến '{fmt.group(fmt.lastindex)}'.")

            # use / free of already-freed pointers (checked before new events on this line)
            for ptr, st in state.items():
                if st["freed_at"] and _uses(ptr, line):
                    add("use-after-free", func, n, f"Dùng '{ptr}' sau khi đã free() tại dòng {st['freed_at']}.")
            for m in FREE_RE.finditer(line):
                ptr = m.group(1)
                st = state.get(ptr)
                if st is None:
                    continue
                if st["freed_at"]:
                    add("double-free", func, n, f"free('{ptr}') lần hai (đã free() tại dòng {st['freed_at']}).")
                st["freed_at"] = st["freed_at"] or n

            alloc = ALLOC_RE.search(line)
            if alloc:
                ptr, size = alloc.group(1), alloc.group(3)
                state[ptr] = {"line": n, "checked": False, "freed_at": None}
                if alloc.group(2) == "malloc" and re.search(r"[A-Za-z_]\w*\s*\*|\*\s*[A-Za-z_]", size) \
                        and "sizeof" not in size.split("*")[0]:
                    add("malloc-size-overflow", func, n, f"Kích thước cấp phát '{size.strip()}' có thể tràn khi nhân.")
                continue

            for ptr, st in list(state.items()):
                if re.search(rf"\b{ptr}\s*=(?!=)", line):
                    if not st["freed_at"] and not re.search(rf"\b{ptr}\s*=\s*NULL\b", line):
                        add("memory-leak", func, n,
                            f"Gán lại '{ptr}' khi vùng nhớ cấp phát tại dòng {st['line']} chưa được free().")
                    del state[ptr]  # pointer no longer refers to the tracked allocation
                    continue
                if not st["checked"] and _null_checked(ptr, line):
                    st["checked"] = True
                elif not st["checked"] and not st["freed_at"] and _uses(ptr, line):
                    add("malloc-unchecked", func, n, f"Dùng '{ptr}' (cấp phát dòng {st['line']}) chưa kiểm tra NULL.")
                    st["checked"] = True

            is_exit = re.search(r"\breturn\b", line) or idx == len(segments) - 1
            if is_exit:
                for ptr, st in state.items():
                    if st["freed_at"] or _null_checked(ptr, line) or re.search(rf"return\s+{ptr}\b", line):
                        continue
                    add("memory-leak", func, n,
                        f"'{ptr}' cấp phát tại dòng {st['line']} không được free() trước khi thoát hàm.")
                    st["freed_at"] = n  # report each allocation once
    return findings


def summarize(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.cwe] = counts.get(f.cwe, 0) + 1
    return counts
