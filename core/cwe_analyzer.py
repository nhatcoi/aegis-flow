"""Security vulnerability classification and CWE / CVE mapping analyzer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .arithmetic_z3 import SMTCheckResult
from .kripke import KripkeCheckReport
from .spec_loader import Specification


@dataclass
class CWEFinding:
    cwe_id: str
    cwe_name: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    source_component: str  # Function name, State machine property, etc.
    description: str
    illustrative_cve: str
    remediation: str


@dataclass
class SecurityAuditReport:
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    findings: list[CWEFinding] = field(default_factory=list)
    summary_text: str = ""


CWE_KNOWLEDGE_BASE = {
    "buffer-overflow": {
        "id": "CWE-120",
        "name": "Buffer Copy without Checking Size of Input (Classic Buffer Overflow)",
        "severity": "CRITICAL",
        "cve": "CVE-2015-7547 (glibc), CVE-2021-3156 (Sudo Baron Samedit)",
        "desc": "Sao chép dữ liệu đầu vào vào bộ đệm kích thước cố định bằng hàm không an toàn (như strcpy) mà không kiểm tra độ dài, cho phép ghi đè stack và thực thi mã tùy ý.",
        "fix": "Sử dụng các hàm an toàn có kiểm tra biên như strncpy, snprintf kèm kiểm tra ký tự kết thúc chuỗi '\\0'.",
    },
    "double-free": {
        "id": "CWE-415",
        "name": "Double Free",
        "severity": "HIGH",
        "cve": "CVE-2019-14287, CVE-2021-3156",
        "desc": "Giải phóng vùng nhớ heap hai lần trên cùng một con trỏ, làm hỏng cấu trúc dữ liệu của bộ quản lý bộ nhớ heap, dẫn tới tấn công chiếm quyền điều khiển luồng thực thi.",
        "fix": "Gán con trỏ về NULL ngay sau khi giải phóng: free(ptr); ptr = NULL;",
    },
    "memory-leak": {
        "id": "CWE-401",
        "name": "Missing Release of Memory after Effective Lifetime",
        "severity": "MEDIUM",
        "cve": "CVE-2022-26377",
        "desc": "Bộ nhớ được cấp phát động nhưng không được giải phóng trước khi kết thúc hàm hoặc mất tham chiếu, gây cạn kiệt tài nguyên hệ thống theo thời gian.",
        "fix": "Đảm bảo mọi nhánh rẽ (kể cả trường hợp gặp lỗi/exception) đều gọi free() hoặc dùng cơ chế RAII.",
    },
    "use-after-free": {
        "id": "CWE-416",
        "name": "Use After Free",
        "severity": "CRITICAL",
        "cve": "CVE-2023-38606",
        "desc": "Tham chiếu hoặc ghi dữ liệu vào con trỏ sau khi vùng nhớ đã được giải phóng, gây corrupt bộ nhớ hoặc thực thi mã từ xa.",
        "fix": "Xóa con trỏ và đặt thành NULL ngay sau khi giải phóng.",
    },
    "divide-by-zero": {
        "id": "CWE-369",
        "name": "Divide By Zero",
        "severity": "MEDIUM",
        "cve": "CVE-2020-1971",
        "desc": "Thực hiện phép toán chia mà không kiểm tra mẫu số bằng 0, dẫn tới lỗi ngắt hệ thống hoặc Denial of Service (DoS).",
        "fix": "Kiểm tra mẫu số khác 0 trước khi thực hiện phép chia hoặc xử lý ngoại lệ ZeroDivisionError.",
    },
    "integer-overflow": {
        "id": "CWE-190",
        "name": "Integer Overflow or Wraparound",
        "severity": "HIGH",
        "cve": "CVE-2016-5195 (Dirty COW), CVE-2018-4407",
        "desc": "Tính toán số nguyên vượt quá giới hạn miền biểu diễn 32-bit (INT_MAX), dẫn đến vòng lặp vô hạn hoặc bỏ qua kiểm tra kích thước bộ nhớ.",
        "fix": "Kiểm tra điều kiện tràn số trước khi cộng: if (b > 0 && a > INT_MAX - b) return ERROR; hoặc dùng kiểu 64-bit.",
    },
    "magic-value-bypass": {
        "id": "CWE-287",
        "name": "Improper Authentication / Hardcoded Credentials",
        "severity": "HIGH",
        "cve": "CVE-2020-10148 (SolarWinds API bypass)",
        "desc": "Chứa các giá trị bí mật (magic numbers) được hardcode trong mã nguồn để vượt qua kiểm tra quyền/khóa tài khoản.",
        "fix": "Loại bỏ mã backdoor, áp dụng xác thực qua token chuẩn hoặc dịch vụ xác thực tập trung có mã hóa bảo mật.",
    },
    "deadlock": {
        "id": "CWE-833",
        "name": "Deadlock",
        "severity": "HIGH",
        "cve": "CVE-2020-25692",
        "desc": "Hệ thống rơi vào trạng thái bế tắc không thể chuyển tiếp tiếp tục hoạt động, gây treo hệ thống toàn bộ.",
        "fix": "Bổ sung chuyển tiếp thoát timeout hoặc thiết kế lại thứ tự phân bổ tài nguyên.",
    },
    "race-condition": {
        "id": "CWE-362",
        "name": "Concurrent Execution using Shared Resource with Improper Synchronization (Race Condition)",
        "severity": "HIGH",
        "cve": "CVE-2021-3156, CVE-2016-5195",
        "desc": "Vi phạm tính chất loại trừ lẫn nhau: Hai tiến trình hoặc luồng cùng truy cập và thực thi vùng tranh chấp đồng thời mà không được đồng bộ đúng.",
        "fix": "Sử dụng Mutex, Semaphore, hoặc cơ chế Atomic Lock để đảm bảo tính loại trừ lẫn nhau nghiêm ngặt.",
    },
    "excessive-auth": {
        "id": "CWE-307",
        "name": "Improper Restriction of Excessive Authentication Attempts",
        "severity": "HIGH",
        "cve": "CVE-2020-2551",
        "desc": "Hệ thống không giới hạn số lần thử đăng nhập thất bại hoặc cơ chế lockout có lỗ hổng bypass, mở đường cho tấn công Brute-force và DoS.",
        "fix": "Triển khai giới hạn tần suất (Rate Limiting), khóa tạm thời theo cấp số nhân (Exponential Backoff) và CAPTCHA.",
    },
}


def analyze_security_vulnerabilities(
    spec: Specification,
    kripke_report: KripkeCheckReport | None = None,
    smt_results: list[SMTCheckResult] | None = None,
) -> SecurityAuditReport:
    findings: list[CWEFinding] = []

    # 1. Inspect Kripke model findings
    if kripke_report:
        if kripke_report.deadlock_states:
            info = CWE_KNOWLEDGE_BASE["deadlock"]
            findings.append(
                CWEFinding(
                    cwe_id=info["id"],
                    cwe_name=info["name"],
                    severity=info["severity"],
                    source_component=f"Kripke Model: {', '.join(kripke_report.deadlock_states)}",
                    description=f"{info['desc']} Các trạng thái deadlock phát hiện: {', '.join(kripke_report.deadlock_states)}",
                    illustrative_cve=info["cve"],
                    remediation=info["fix"],
                )
            )

        for prop in kripke_report.property_results:
            if not prop.passed:
                if "Loại trừ lẫn nhau" in prop.title:
                    info = CWE_KNOWLEDGE_BASE["race-condition"]
                    findings.append(
                        CWEFinding(
                            cwe_id=info["id"],
                            cwe_name=info["name"],
                            severity=info["severity"],
                            source_component=f"Model Checking: {prop.title}",
                            description=f"{info['desc']} Chi tiết: {prop.details}",
                            illustrative_cve=info["cve"],
                            remediation=info["fix"],
                        )
                    )
                elif "EF(trusted)" in prop.title or "AG(!violation)" in prop.title:
                    info = CWE_KNOWLEDGE_BASE["excessive-auth"]
                    findings.append(
                        CWEFinding(
                            cwe_id=info["id"],
                            cwe_name=info["name"],
                            severity=info["severity"],
                            source_component=f"Model Checking: {prop.title}",
                            description=f"Vi phạm kiểm chứng thuộc tính an toàn CTL: {prop.details}",
                            illustrative_cve=info["cve"],
                            remediation=info["fix"],
                        )
                    )

    # 2. Inspect Function Bugs
    for fn in spec.functions:
        if fn.bug == "buffer-overflow":
            info = CWE_KNOWLEDGE_BASE["buffer-overflow"]
            findings.append(
                CWEFinding(
                    cwe_id=info["id"],
                    cwe_name=info["name"],
                    severity=info["severity"],
                    source_component=f"Hàm C: {fn.name}()",
                    description=f"{info['desc']} Bộ đệm cố định: {fn.buffer_size or 16} bytes.",
                    illustrative_cve=info["cve"],
                    remediation=info["fix"],
                )
            )
        elif fn.bug == "double-free":
            info = CWE_KNOWLEDGE_BASE["double-free"]
            findings.append(
                CWEFinding(
                    cwe_id=info["id"],
                    cwe_name=info["name"],
                    severity=info["severity"],
                    source_component=f"Hàm C: {fn.name}()",
                    description=info["desc"],
                    illustrative_cve=info["cve"],
                    remediation=info["fix"],
                )
            )
        elif fn.bug == "memory-leak":
            info = CWE_KNOWLEDGE_BASE["memory-leak"]
            findings.append(
                CWEFinding(
                    cwe_id=info["id"],
                    cwe_name=info["name"],
                    severity=info["severity"],
                    source_component=f"Hàm C: {fn.name}()",
                    description=info["desc"],
                    illustrative_cve=info["cve"],
                    remediation=info["fix"],
                )
            )
        elif fn.bug == "use-after-free":
            info = CWE_KNOWLEDGE_BASE["use-after-free"]
            findings.append(
                CWEFinding(
                    cwe_id=info["id"],
                    cwe_name=info["name"],
                    severity=info["severity"],
                    source_component=f"Hàm C: {fn.name}()",
                    description=info["desc"],
                    illustrative_cve=info["cve"],
                    remediation=info["fix"],
                )
            )

        if fn.kind == "divide":
            info = CWE_KNOWLEDGE_BASE["divide-by-zero"]
            findings.append(
                CWEFinding(
                    cwe_id=info["id"],
                    cwe_name=info["name"],
                    severity=info["severity"],
                    source_component=f"Hàm Python: {fn.name}()",
                    description=info["desc"],
                    illustrative_cve=info["cve"],
                    remediation=info["fix"],
                )
            )
        elif fn.kind == "magic_value":
            info = CWE_KNOWLEDGE_BASE["magic-value-bypass"]
            findings.append(
                CWEFinding(
                    cwe_id=info["id"],
                    cwe_name=info["name"],
                    severity=info["severity"],
                    source_component=f"Hàm Python: {fn.name}()",
                    description=f"{info['desc']} Giá trị bí mật phát hiện: {fn.magic_values}",
                    illustrative_cve=info["cve"],
                    remediation=info["fix"],
                )
            )

    # 3. Inspect SMT Arithmetic Results
    if smt_results:
        for res in smt_results:
            if res.overflow_possible:
                info = CWE_KNOWLEDGE_BASE["integer-overflow"]
                findings.append(
                    CWEFinding(
                        cwe_id=info["id"],
                        cwe_name=info["name"],
                        severity=info["severity"],
                        source_component=f"Biểu thức SMT: {res.name}",
                        description=f"{info['desc']} Z3 Solver tìm thấy bộ giá trị gây tràn số: {res.overflow_values} -> giá trị tính được: {res.overflow_evaluated}",
                        illustrative_cve=info["cve"],
                        remediation=info["fix"],
                    )
                )

    crit = sum(1 for f in findings if f.severity == "CRITICAL")
    high = sum(1 for f in findings if f.severity == "HIGH")
    med = sum(1 for f in findings if f.severity == "MEDIUM")

    lines = [
        "=== BẢNG PHÂN TÍCH LỖ HỔNG BẢO MẬT & ÁNH XẠ CWE/CVE ===",
        f"- Tổng số lỗ hổng phát hiện: {len(findings)}",
        f"- Mức độ nghiêm trọng: [CRITICAL: {crit}]  [HIGH: {high}]  [MEDIUM: {med}]",
        "",
    ]
    for idx, f in enumerate(findings, 1):
        lines.append(f"{idx}. [{f.severity}] {f.cwe_id}: {f.cwe_name}")
        lines.append(f"   - Thành phần: {f.source_component}")
        lines.append(f"   - Mô tả: {f.description}")
        lines.append(f"   - Ví dụ CVE thực tế: {f.illustrative_cve}")
        lines.append(f"   - Khắc phục: {f.remediation}")
        lines.append("")

    return SecurityAuditReport(
        total_findings=len(findings),
        critical_count=crit,
        high_count=high,
        medium_count=med,
        findings=findings,
        summary_text="\n".join(lines),
    )
