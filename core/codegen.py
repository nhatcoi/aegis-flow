"""Source code generator for C and Python functions specified in FunctionSpec."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .spec_loader import FunctionSpec, Specification


@dataclass
class GeneratedFunction:
    spec: FunctionSpec
    code_vulnerable: str
    code_safe: str
    language: str
    explanation: str


def generate_function_code(fn: FunctionSpec) -> GeneratedFunction:
    lang = fn.language.lower()
    kind = fn.kind.lower()
    bug = fn.bug
    buf_sz = fn.buffer_size or 16

    # 1. C: buffer_copy
    if lang == "c" and kind == "buffer_copy":
        param_name = fn.params[0] if fn.params else "raw_input"
        vulnerable = f"""// [CWE-120/121] Buffer Copy without Checking Size of Input
#include <stdio.h>
#include <string.h>

void {fn.name}(const char *{param_name}) {{
    char buffer[{buf_sz}];
    // LỖ HỔNG: strcpy không kiểm tra kích thước đầu vào -> Buffer Overflow!
    strcpy(buffer, {param_name});
    printf("Processed input: %s\\n", buffer);
}}"""

        safe = f"""// [SECURE] An toàn: Sử dụng strncpy kèm ký tự kết thúc chuỗi '\\0'
#include <stdio.h>
#include <string.h>

void {fn.name}_safe(const char *{param_name}) {{
    char buffer[{buf_sz}];
    // PHÒNG CHỐNG: Giới hạn số byte sao chép tối đa theo kích thước bộ đệm
    strncpy(buffer, {param_name}, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\\0';
    printf("Processed input safely: %s\\n", buffer);
}}"""
        explanation = (
            f"Hàm C sao chép chuỗi vào bộ đệm kích thước {buf_sz} bytes. "
            f"Bản có lỗi dùng 'strcpy' dẫn tới Stack Buffer Overflow (CWE-120). "
            f"Bản an toàn dùng 'strncpy' và ép ký tự kết thúc '\\0'."
        )
        return GeneratedFunction(fn, vulnerable, safe, "c", explanation)

    # 2. C: alloc_release
    elif lang == "c" and kind == "alloc_release":
        if bug == "double-free":
            vulnerable = f"""// [CWE-415] Double Free
#include <stdio.h>
#include <stdlib.h>

void {fn.name}() {{
    char *session_data = (char *)malloc({buf_sz});
    if (!session_data) return;
    
    // Lần giải phóng thứ nhất
    free(session_data);
    
    // LỖ HỔNG: Giải phóng lần thứ 2 trên cùng một con trỏ -> Double Free!
    free(session_data);
}}"""
            explanation = "Hàm giải phóng bộ nhớ 2 lần trên cùng 1 địa chỉ heap (CWE-415)."

        elif bug == "memory-leak":
            vulnerable = f"""// [CWE-401] Memory Leak
#include <stdio.h>
#include <stdlib.h>

void {fn.name}() {{
    char *session_data = (char *)malloc({buf_sz});
    if (!session_data) return;
    // LỖ HỔNG: Thoát hàm mà không gọi free() -> Thất thoát bộ nhớ!
    return;
}}"""
            explanation = "Hàm cấp phát bộ nhớ động nhưng không giải phóng trước khi kết thúc (CWE-401)."

        elif bug == "use-after-free":
            vulnerable = f"""// [CWE-416] Use After Free
#include <stdio.h>
#include <stdlib.h>

void {fn.name}() {{
    char *session_data = (char *)malloc({buf_sz});
    if (!session_data) return;
    free(session_data);
    // LỖ HỔNG: Sử dụng vùng nhớ sau khi đã giải phóng!
    session_data[0] = 'X';
}}"""
            explanation = "Hàm ghi dữ liệu vào con trỏ sau khi đã giải phóng bộ nhớ (CWE-416)."

        else:
            vulnerable = f"""#include <stdio.h>
#include <stdlib.h>

void {fn.name}() {{
    char *session_data = (char *)malloc({buf_sz});
    if (!session_data) return;
    free(session_data);
}}"""
            explanation = "Hàm cấp phát và giải phóng phiên hợp lệ."

        safe = f"""// [SECURE] An toàn: Giải phóng và gán NULL ngay lập tức
#include <stdio.h>
#include <stdlib.h>

void {fn.name}_safe() {{
    char *session_data = (char *)malloc({buf_sz});
    if (!session_data) return;
    
    // PHÒNG CHỐNG: Kiểm tra và gán NULL ngay sau khi free
    free(session_data);
    session_data = NULL;
}}"""
        return GeneratedFunction(fn, vulnerable, safe, "c", explanation)

    # 3. C: arithmetic
    elif lang == "c" and kind == "arithmetic":
        p1 = fn.params[0] if len(fn.params) > 0 else "a"
        p2 = fn.params[1] if len(fn.params) > 1 else "b"
        vulnerable = f"""// [CWE-190] Integer Overflow or Wraparound
#include <limits.h>

int {fn.name}(int {p1}, int {p2}) {{
    // LỖ HỔNG: Phép cộng không kiểm tra tràn số nguyên 32-bit
    return {p1} + {p2};
}}"""
        safe = f"""// [SECURE] An toàn: Kiểm tra tràn số trước khi thực hiện phép cộng
#include <limits.h>
#include <stdbool.h>

bool {fn.name}_safe(int {p1}, int {p2}, int *result) {{
    // PHÒNG CHỐNG: Kiểm tra điều kiện tràn INT_MAX / INT_MIN
    if (({p2} > 0 && {p1} > INT_MAX - {p2}) || ({p2} < 0 && {p1} < INT_MIN - {p2})) {{
        return false; // Phát hiện nguy cơ tràn số
    }}
    *result = {p1} + {p2};
    return true;
}}"""
        explanation = "Hàm cộng số nguyên C. Bản có lỗi có thể gây tràn số INT_MAX (CWE-190)."
        return GeneratedFunction(fn, vulnerable, safe, "c", explanation)

    # 4. Python: divide
    elif lang == "python" and kind == "divide":
        p1 = fn.params[0] if len(fn.params) > 0 else "a"
        p2 = fn.params[1] if len(fn.params) > 1 else "b"
        vulnerable = f"""# [CWE-369] Divide By Zero
def {fn.name}({p1}: int, {p2}: int) -> int:
    # LỖ HỔNG: Chia trực tiếp không kiểm tra mẫu số khác 0
    return {p1} // {p2}
"""
        safe = f"""# [SECURE] An toàn: Bắt ngoại lệ hoặc kiểm tra mẫu số = 0
def {fn.name}_safe({p1}: int, {p2}: int) -> float:
    # PHÒNG CHỐNG: Tránh ZeroDivisionError khi tổng số lần thử = 0
    if {p2} == 0:
        return 0.0
    return {p1} / {p2}
"""
        explanation = f"Hàm tính tỷ lệ chia `{p1} // {p2}`. Bản có lỗi crash khi `{p2} == 0` (CWE-369)."
        return GeneratedFunction(fn, vulnerable, safe, "python", explanation)

    # 5. Python: magic_value (Concolic/white-box target)
    elif lang == "python" and kind == "magic_value":
        p1 = fn.params[0] if len(fn.params) > 0 else "code_a"
        p2 = fn.params[1] if len(fn.params) > 1 else "code_b"
        m1 = fn.magic_values[0] if len(fn.magic_values) > 0 else 9001
        m2 = fn.magic_values[1] if len(fn.magic_values) > 1 else 4477
        vulnerable = f"""# [CWE-287 / CWE-306] Hardcoded Backdoor / Magic Value Bypass
def {fn.name}({p1}: int, {p2}: int) -> bool:
    # LỖ HỔNG: Mã khóa bí mật bị hardcode trong mã nguồn cho phép vượt rào kiểm soát
    if {p1} == {m1}:
        if {p2} == {m2}:
            return True  # Backdoor trigger!
    return False
"""
        safe = f"""# [SECURE] An toàn: Không hardcode mã bí mật, xác thực qua cơ chế chuẩn
import hmac

def {fn.name}_safe({p1}: int, {p2}: int, expected_token_hash: bytes) -> bool:
    # PHÒNG CHỐNG: Sử dụng xác thực mã ngẫu nhiên hoặc kiểm tra token mã hóa
    user_token = f"{{code_a}}:{{code_b}}".encode()
    return hmac.compare_digest(hash(user_token), expected_token_hash)
"""
        explanation = f"Hàm có nhánh giá trị bí mật `{m1}`, `{m2}` (Backdoor bypass)."
        return GeneratedFunction(fn, vulnerable, safe, "python", explanation)

    # Default fallback
    else:
        params_str = ", ".join(fn.params)
        vulnerable = f"// Function: {fn.name}({params_str})\nvoid {fn.name}() {{ }}\n"
        safe = vulnerable
        explanation = f"Hàm {fn.name} ({lang}, {kind})."
        return GeneratedFunction(fn, vulnerable, safe, lang, explanation)


def format_code_with_line_numbers(code: str) -> str:
    lines = code.split("\n")
    max_len = len(str(len(lines)))
    return "\n".join(f"{i+1:>{max_len}} | {line}" for i, line in enumerate(lines))


def generate_all_functions(spec: Specification) -> list[GeneratedFunction]:
    return [generate_function_code(fn) for fn in spec.functions]
