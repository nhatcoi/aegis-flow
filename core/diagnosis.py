"""Rule-based diagnosis of a failed Kripke/CTL check.

A counterexample only shows *that* a property fails. This module points at the
part of the model to look at — the transition that enters the bad state, the
labels that make the property false there, the loop or dead end that blocks a
liveness property — and traces the property back to requirements through the
test cases whose expected result names it. Everything is derived from the
model, so the output is deterministic and needs no external service.
"""
from __future__ import annotations

from .kripke import KripkeStructure, VerificationResult
from .spec_loader import Requirement, Specification


def _norm(text: str) -> str:
    return "".join(text.split()).lower()


def diagnose(r: VerificationResult, model: KripkeStructure | None) -> list[str]:
    if r.status == "pass":
        return []
    if r.status == "error":
        return ["Công thức không phân tích được, nên chưa có kết luận. Kiểm tra lại cú pháp CTL trong đặc tả."]
    if model is None:
        return []

    def labels(st: str) -> str:
        return "{" + ", ".join(model.labeling.get(st, [])) + "}"

    def exits(st: str) -> list[str]:
        return [n for n in model.succ.get(st, []) if n != st]

    lines: list[str] = []
    if r.kind == "deadlock":
        for st in r.violation_states:
            lines.append(f"Trạng thái <b>{st}</b> {labels(st)} không có chuyển tiếp nào đi ra: "
                         "hệ thống tới đây thì dừng hẳn.")
        lines.append("Cần thêm chuyển tiếp từ trạng thái này sang trạng thái kết thúc hoặc trạng thái xử lý tiếp.")
        return lines

    path = r.counterexample_path
    if r.loop_start is not None and path:
        loop = list(dict.fromkeys(path[r.loop_start:]))
        lines.append(f"Đường đi rơi vào vòng lặp vô hạn qua <b>{' → '.join(loop)}</b>; trong vòng này điều kiện "
                     "mà công thức đòi hỏi (vế AF/A[U]) không bao giờ xảy ra.")
        for st in loop:
            out = exits(st)
            lines.append(f"Lối ra của <b>{st}</b>: " + (", ".join(out) if out else
                                                         "không có lối ra nào khác ngoài chính nó"))
        lines.append("Cần thêm (hoặc bắt buộc) một chuyển tiếp thoát khỏi vòng lặp tới trạng thái thỏa điều kiện.")
    elif len(path) >= 2:
        prev, last = path[-2], path[-1]
        lines.append(f"Bước chuyển gây lỗi: <b>{prev} → {last}</b>.")
        lines.append(f"Tại <b>{last}</b> các nhãn đúng là {labels(last)}, làm công thức sai ở trạng thái này.")
        lines.append(f"Cần bỏ chuyển tiếp {prev} → {last}, thêm điều kiện chặn, hoặc sửa nhãn của {last} "
                     "nếu mô hình gán sai.")
    elif len(path) == 1:
        lines.append(f"Trạng thái khởi tạo <b>{path[0]}</b> {labels(path[0])} đã vi phạm công thức.")
    return lines


def related_requirements(r: VerificationResult, spec: Specification) -> list[Requirement]:
    """Requirements traced through test cases whose expected result names this check."""
    key = _norm(r.formula) if r.formula else ""
    ids: list[str] = []
    for tc in spec.test_cases:
        expected = _norm(tc.expected_result)
        if (key and key in expected) or (r.kind == "deadlock" and "deadlock" in expected):
            ids += tc.requirement_ids
    by_id = {req.id: req for req in spec.requirements}
    return [by_id[i] for i in dict.fromkeys(ids) if i in by_id]
