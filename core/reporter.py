"""Integrated Report Generator for Spec Verification Lab (Chapters 1 to 4)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .arithmetic_z3 import SMTCheckResult
from .codegen import GeneratedFunction
from .cwe_analyzer import SecurityAuditReport
from .kripke import KripkeCheckReport
from .spec_loader import Specification


def generate_markdown_report(
    spec: Specification,
    kripke_report: KripkeCheckReport | None,
    functions: list[GeneratedFunction],
    smt_results: list[SMTCheckResult],
    security_audit: SecurityAuditReport,
) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# BÁO CÁO KIỂM CHỨNG ĐẶC TẢ VÀ AN TOÀN PHẦN MỀM",
        f"**Tên đặc tả:** `{spec.name}`  ",
        f"**Thời gian thực thi:** `{timestamp}`  ",
        f"**Công cụ:** Spec Verification Lab (Python Desktop)  ",
        "",
        "---",
        "",
        "## PHẦN 1: MÔ TẢ ĐẶC TẢ YÊU CẦU",
        f"**Mô tả:** {spec.description or 'Không có'}",
        "",
        "### Danh sách yêu cầu (Requirements):",
        "| ID | Nội dung yêu cầu | Phân loại | Mức độ ưu tiên |",
        "|---|---|---|---|",
    ]

    for req in spec.requirements:
        lines.append(f"| `{req.id}` | {req.text} | `{req.category}` | **{req.priority}** |")

    lines.extend([
        "",
        "---",
        "",
        "## CHƯƠNG 1: MÔ HÌNH HÓA KRIPKE VÀ KIỂM CHỨNG HÌNH THỨC (MODEL CHECKING)",
    ])

    if kripke_report and spec.state_machine:
        lines.extend([
            f"- **Tập trạng thái ($S$):** {len(spec.state_machine.states)} trạng thái (`{', '.join(spec.state_machine.states)}`)",
            f"- **Trạng thái khởi tạo ($S_0$):** `{', '.join(spec.state_machine.initial)}`",
            f"- **Số chuyển tiếp ($R$):** {len(spec.state_machine.transitions)}",
            f"- **Kết luận kiểm chứng:** **{'HỢP LỆ (SAFE)' if kripke_report.is_valid else 'PHÁT HIỆN LỖI (UNSAFE)'}**",
            "",
            "### Chi tiết kiểm tra các thuộc tính an toàn (Safety & CTL):",
        ])
        for idx, r in enumerate(kripke_report.property_results, 1):
            badge = "PASSED" if r.passed else "FAILED"
            lines.append(f"#### 1.{idx}. [{badge}] {r.title}")
            for d in r.details.split("\n"):
                lines.append(f"> {d}")
            if r.counterexample_path:
                lines.append(f"> **Vết phản ví dụ:** `{' -> '.join(r.counterexample_path)}`")
            lines.append("")
    else:
        lines.append("*Không có mô hình máy trạng thái Kripke trong đặc tả này.*")

    lines.extend([
        "",
        "---",
        "",
        "## CHƯƠNG 2: SINH MÃ NGUỒN TỪ ĐẶC TẢ (C / PYTHON)",
    ])

    if functions:
        for idx, fn in enumerate(functions, 1):
            lines.extend([
                f"### 2.{idx}. Hàm `{fn.spec.name}` ({fn.language.upper()}, {fn.spec.kind})",
                f"**Mô tả:** {fn.explanation}",
                "",
                "**Mã nguồn ban đầu (Minh họa lỗ hổng):**",
                f"```{fn.language}",
                fn.code_vulnerable,
                "```",
                "",
                "**Mã nguồn đã vá an toàn (Hardened / Secure version):**",
                f"```{fn.language}",
                fn.code_safe,
                "```",
                "",
            ])
    else:
        lines.append("*Không có hàm nào được định nghĩa để sinh mã.*")

    lines.extend([
        "",
        "---",
        "",
        "## CHƯƠNG 3: KIỂM TRA SỐ HỌC BẰNG Z3 SMT SOLVER (INTEGER OVERFLOW)",
    ])

    if smt_results:
        for idx, smt in enumerate(smt_results, 1):
            ovf_status = "PHÁT HIỆN TRÀN SỐ (CWE-190)" if smt.overflow_possible else "AN TOÀN"
            lines.extend([
                f"### 3.{idx}. Kiểm tra: `{smt.name}` — **{ovf_status}**",
                f"```text",
                smt.details,
                f"```",
                "",
            ])
    else:
        lines.append("*Không có biểu thức kiểm tra số học trong đặc tả.*")

    lines.extend([
        "",
        "---",
        "",
        "## CHƯƠNG 4: BẢNG TỔNG HỢP LỖ HỔNG AN TOÀN & ÁNH XẠ CWE/CVE",
        f"- **Tổng số lỗ hổng:** {security_audit.total_findings}",
        f"- **Mức độ:** `CRITICAL: {security_audit.critical_count}` | `HIGH: {security_audit.high_count}` | `MEDIUM: {security_audit.medium_count}`",
        "",
        "| STT | Mức độ | Mã CWE | Tên lỗ hổng | Thành phần | Ví dụ CVE thực tế |",
        "|---|---|---|---|---|---|",
    ])

    for idx, f in enumerate(security_audit.findings, 1):
        lines.append(
            f"| {idx} | **{f.severity}** | `{f.cwe_id}` | {f.cwe_name} | `{f.source_component}` | {f.illustrative_cve} |"
        )

    lines.extend([
        "",
        "### Hướng dẫn khắc phục chi tiết:",
    ])
    for idx, f in enumerate(security_audit.findings, 1):
        lines.extend([
            f"**{idx}. [{f.cwe_id}] {f.cwe_name} tại `{f.source_component}`:**",
            f"- *Mô tả:* {f.description}",
            f"- *Giải pháp:* {f.remediation}",
            "",
        ])

    if spec.test_cases:
        lines.extend([
            "---",
            "",
            "## PHẦN PHỤ LỤC: MA TRẬN TRUY VẾT TEST CASE (TEST TRACEABILITY MATRIX)",
            "| Mã Test | Yêu cầu liên quan | Tiêu đề | Điều kiện tiên quyết | Kết quả mong đợi | Ưu tiên |",
            "|---|---|---|---|---|---|",
        ])
        for tc in spec.test_cases:
            r_str = ", ".join(tc.requirement_ids)
            lines.append(f"| `{tc.id}` | `{r_str}` | {tc.title} | {tc.preconditions} | {tc.expected_result} | **{tc.priority}** |")

    return "\n".join(lines)


def export_report(
    filepath: str | Path,
    spec: Specification,
    kripke_report: KripkeCheckReport | None,
    functions: list[GeneratedFunction],
    smt_results: list[SMTCheckResult],
    security_audit: SecurityAuditReport,
) -> Path:
    md_content = generate_markdown_report(spec, kripke_report, functions, smt_results, security_audit)
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(md_content)
    return path
