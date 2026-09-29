"""Code generation from the HamSinhMa sheet.

Every function is emitted twice with the *same signature*:

* ``code_vulnerable`` (v0) — contains the bug declared in the ``Loi`` column,
  or is identical to v1 when no bug is declared.
* ``code_safe`` (v1) — the patched version.

Keeping the signature identical lets the same harness / fuzzer run on both
versions, which is what produces the before/after evidence.
"""
from __future__ import annotations

from dataclasses import dataclass

from .spec_loader import FunctionSpec, Specification

# Loi values meaning "no injected bug". For Python kinds an empty Loi keeps the course tool's
# behaviour (divide / magic_value are vulnerable by construction), so a patched design must say so.
SAFE_MARKERS = {"safe", "fixed", "an-toan", "an_toan"}

C_HEADER = "#define _POSIX_C_SOURCE 200809L\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n"


@dataclass
class GeneratedFunction:
    spec: FunctionSpec
    code_vulnerable: str
    code_safe: str
    language: str
    explanation: str

    @property
    def has_bug(self) -> bool:
        return self.code_vulnerable != self.code_safe


def _p(fn: FunctionSpec, i: int, default: str) -> str:
    return fn.params[i] if len(fn.params) > i else default


# ---------------------------------------------------------------------------
# C
# ---------------------------------------------------------------------------
def _buffer_copy(fn: FunctionSpec) -> GeneratedFunction:
    arg = _p(fn, 0, "raw_input")
    size = fn.buffer_size or 16
    safe = f"""{C_HEADER}
/* {fn.name}: sao chep du lieu dau vao vao bo dem {size} byte (v1 - da va) */
int {fn.name}(const char *{arg}) {{
    char buffer[{size}];
    if ({arg} == NULL) return -1;
    size_t len = strnlen({arg}, sizeof buffer);
    if (len >= sizeof buffer) return -1; /* tu choi input qua dai thay vi cat bot */
    memcpy(buffer, {arg}, len);
    buffer[len] = '\\0';
    printf("%s\\n", buffer);
    return 0;
}}
"""
    if fn.bug != "buffer-overflow":
        return GeneratedFunction(fn, safe, safe, "c", f"Sao chép an toàn vào bộ đệm {size} byte.")
    vulnerable = f"""{C_HEADER}
/* {fn.name}: sao chep du lieu dau vao vao bo dem {size} byte (v0 - co loi) */
int {fn.name}(const char *{arg}) {{
    char buffer[{size}];
    strcpy(buffer, {arg}); /* khong kiem tra kich thuoc dich */
    printf("%s\\n", buffer);
    return 0;
}}
"""
    explanation = (
        f"v0 dùng strcpy vào bộ đệm {size} byte nên input dài hơn {size - 1} ký tự gây tràn stack (CWE-120). "
        "v1 đo độ dài bằng strnlen và từ chối input quá dài thay vì cắt bớt âm thầm."
    )
    return GeneratedFunction(fn, vulnerable, safe, "c", explanation)


def _alloc_release(fn: FunctionSpec) -> GeneratedFunction:
    size = fn.buffer_size or 16
    safe = f"""{C_HEADER}
/* {fn.name}: cap phat, su dung va giai phong vung nho {size} byte (v1 - da va) */
int {fn.name}(void) {{
    char *data = (char *)malloc({size});
    if (data == NULL) return -1;
    memset(data, 0, {size});
    data[0] = 'A';
    free(data);
    data = NULL; /* tranh double-free / use-after-free */
    return 0;
}}
"""
    body = {
        "memory-leak": (
            "    data[0] = 'A';\n    return 0; /* thoat ma khong free */",
            "v0 thoát hàm mà không giải phóng vùng nhớ đã cấp phát (CWE-401).",
        ),
        "double-free": (
            "    data[0] = 'A';\n    free(data);\n    free(data); /* giai phong lan thu hai */\n    return 0;",
            "v0 giải phóng cùng một con trỏ hai lần, làm hỏng metadata của heap (CWE-415).",
        ),
        "use-after-free": (
            "    free(data);\n    data[0] = 'A'; /* ghi sau khi da free */\n    return 0;",
            "v0 ghi vào vùng nhớ sau khi đã giải phóng (CWE-416).",
        ),
    }
    if fn.bug not in body:
        return GeneratedFunction(fn, safe, safe, "c", f"Cấp phát/giải phóng {size} byte đúng vòng đời.")
    code, explanation = body[fn.bug]
    vulnerable = f"""{C_HEADER}
/* {fn.name}: cap phat, su dung va giai phong vung nho {size} byte (v0 - co loi) */
int {fn.name}(void) {{
    char *data = (char *)malloc({size});
    if (data == NULL) return -1;
    memset(data, 0, {size});
{code}
}}
"""
    return GeneratedFunction(fn, vulnerable, safe, "c", explanation + " v1 giải phóng đúng một lần rồi gán NULL.")


def _arithmetic(fn: FunctionSpec) -> GeneratedFunction:
    a, b = _p(fn, 0, "a"), _p(fn, 1, "b")
    vulnerable = f"""#include <limits.h>

/* {fn.name}: cong hai so nguyen 32-bit (v0 - co loi) */
int {fn.name}(int {a}, int {b}, int *out) {{
    *out = {a} + {b}; /* co the tran so: undefined behavior */
    return 0;
}}
"""
    safe = f"""#include <limits.h>

/* {fn.name}: cong hai so nguyen 32-bit (v1 - da va) */
int {fn.name}(int {a}, int {b}, int *out) {{
    if (({b} > 0 && {a} > INT_MAX - {b}) || ({b} < 0 && {a} < INT_MIN - {b})) {{
        return -1; /* tu choi thay vi de tran so */
    }}
    *out = {a} + {b};
    return 0;
}}
"""
    if fn.bug != "integer-overflow":
        return GeneratedFunction(fn, safe, safe, "c", f"Cộng `{a} + {b}` có kiểm tra tràn int32.")
    explanation = (
        f"v0 cộng `{a} + {b}` không kiểm tra biên nên có thể tràn int32 (CWE-190). "
        "v1 kiểm tra INT_MAX/INT_MIN trước khi cộng và trả lỗi."
    )
    return GeneratedFunction(fn, vulnerable, safe, "c", explanation)


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------
def _divide(fn: FunctionSpec) -> GeneratedFunction:
    a, b = _p(fn, 0, "a"), _p(fn, 1, "b")
    vulnerable = f"""def {fn.name}({a}, {b}):
    return {a} // {b}
"""
    safe = f"""def {fn.name}({a}, {b}):
    if {b} == 0:
        return 0
    return {a} // {b}
"""
    if (fn.bug or "").lower() in SAFE_MARKERS:
        return GeneratedFunction(fn, safe, safe, "python", f"Chia `{a} // {b}` có kiểm tra mẫu số 0.")
    explanation = f"v0 chia `{a} // {b}` không kiểm tra mẫu số nên crash khi `{b} == 0` (CWE-369). v1 xử lý mẫu số 0."
    return GeneratedFunction(fn, vulnerable, safe, "python", explanation)


def _magic_value(fn: FunctionSpec) -> GeneratedFunction:
    a, b = _p(fn, 0, "code_a"), _p(fn, 1, "code_b")
    m1 = fn.magic_values[0] if len(fn.magic_values) > 0 else 9001
    m2 = fn.magic_values[1] if len(fn.magic_values) > 1 else 4477
    vulnerable = f"""def {fn.name}({a}, {b}):
    if {a} == {m1}:
        if {b} == {m2}:
            return True
    return False
"""
    safe = f"""import hmac
import os


def {fn.name}({a}, {b}):
    expected = os.environ.get("WEBHOOK_SECRET", "")
    if not expected:
        return False
    return hmac.compare_digest(f"{{{a}}}:{{{b}}}", expected)
"""
    if (fn.bug or "").lower() in SAFE_MARKERS:
        return GeneratedFunction(fn, safe, safe, "python", "So khớp bí mật cấu hình bằng hmac.compare_digest.")
    explanation = (
        f"v0 chấp nhận cặp giá trị hardcode ({m1}, {m2}) làm cửa hậu vượt qua xác thực (CWE-798). "
        "v1 so khớp với bí mật cấu hình ngoài mã nguồn bằng hmac.compare_digest và từ chối khi chưa cấu hình."
    )
    return GeneratedFunction(fn, vulnerable, safe, "python", explanation)


GENERATORS = {
    ("c", "buffer_copy"): _buffer_copy,
    ("c", "alloc_release"): _alloc_release,
    ("c", "arithmetic"): _arithmetic,
    ("python", "divide"): _divide,
    ("python", "magic_value"): _magic_value,
}


def generate_function_code(fn: FunctionSpec) -> GeneratedFunction:
    gen = GENERATORS.get((fn.language.lower(), fn.kind.lower()))
    if gen is not None:
        return gen(fn)
    params = ", ".join(fn.params)
    stub = f"/* {fn.name}({params}): loai '{fn.kind}' chua ho tro sinh ma */\n"
    return GeneratedFunction(fn, stub, stub, fn.language.lower(), f"Hàm {fn.name} ({fn.language}, {fn.kind}).")


def format_code_with_line_numbers(code: str) -> str:
    lines = code.split("\n")
    width = len(str(len(lines)))
    return "\n".join(f"{i + 1:>{width}} | {line}" for i, line in enumerate(lines))


def generate_all_functions(spec: Specification) -> list[GeneratedFunction]:
    return [generate_function_code(fn) for fn in spec.functions]
