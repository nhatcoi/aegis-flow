"""Draft a JSON specification from a plain-language description with an AI model.

The draft is a starting point, not evidence: it is parsed with the same loader
as hand-written specs and checked for the mistakes that would silently corrupt
every later verdict (unknown states, CTL syntax errors, atoms that no state
carries, unsupported function kinds, unreachable or dead-end states). Saved
drafts go to ``dataset/drafts/`` and are marked as AI-generated.
"""
from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import ai_explain
from .codegen import GENERATORS
from .kripke import KripkeStructure
from .spec_loader import Specification, load_specification

ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = ROOT / "dataset" / "drafts"

SYSTEM_PROMPT = """You write formal requirement specifications for AegisFlow, a teaching tool that verifies \
software safety (Kripke/CTL model checking, C memory bugs with ASan, Z3 overflow checks, fuzzing).
Reply with ONE JSON object only (no prose, no markdown fences). Text values in Vietnamese.

Schema (all top-level keys optional except name):
{
  "name": "snake_case_name",
  "description": "1-2 sentences",
  "requirements": [{"id": "REQ-1", "text": "...", "category": "safety|liveness|memory|functional",
                    "priority": "HIGH|MEDIUM|LOW"}],
  "state_machine": {"states": ["A", "B"], "initial": ["A"],
                    "labeling": {"A": ["atom1"], "B": ["atom2", "violation"]},
                    "transitions": [["A", "B"], ["B", "A"]]},
  "safety_properties": ["AG(!violation)", "AG(shipped -> paid)", "AG(timeout -> AF(paid | failed))"],
  "mutual_exclusion": [{"atom1": "lock_a", "atom2": "lock_b"}],
  "functions": [{"name": "fn", "language": "c|python", "kind": "...", "params": ["..."],
                 "buffer_size": 64, "bug": "...", "magic_values": [1234, 5678]}],
  "arithmetic_checks": [{"name": "total_counter", "int_vars": ["a", "b"], "overflow_expr": "a + b"}],
  "test_cases": [{"id": "TC-1", "requirement_ids": ["REQ-1"], "title": "...", "preconditions": "...",
                  "steps": ["..."], "expected_result": "AG(shipped -> paid) ĐÚNG"}]
}

Rules:
- Model the design as the user describes it, INCLUDING its flaws: if the description implies an unsafe path, \
keep that transition and give the bad state the label "violation" so the checker can find it.
- Every state appears in labeling with lowercase atoms; every transition endpoint is a declared state; every \
state should have at least one outgoing transition (a self-loop is fine for final states).
- CTL syntax: AG AF AX EG EF EX, E[p U q], A[p U q], ! & | -> <->, parentheses. Only use atoms that some \
state carries. Write 3-6 meaningful properties; avoid tautologies.
- functions: language "c" kinds: buffer_copy (bug "buffer-overflow" or null), alloc_release (bug \
"memory-leak" | "double-free" | "use-after-free" | null), arithmetic (bug "integer-overflow", params two ints). \
language "python" kinds: divide (params two ints; bug "" = vulnerable to division by zero, "safe" = patched), \
magic_value (params two ints, magic_values two ints; bug "" = hard-coded backdoor, "safe" = patched).
- arithmetic_checks.overflow_expr uses only + - * over int_vars.
- test_cases.expected_result must use a checkable phrase: "<CTL formula> ĐÚNG", "không có trạng thái \
deadlock", "Không phát hiện CWE-120 tại <function>", "Không crash (ZeroDivisionError) tại <function>", \
"Không phát hiện CWE-798", "Z3 UNSAT". Each test case lists the requirement ids it traces.
"""


@dataclass
class DraftCheck:
    data: dict | None = None
    spec: Specification | None = None
    errors: list[str] = field(default_factory=list)  # block saving
    warnings: list[str] = field(default_factory=list)  # worth reading, saving allowed

    @property
    def ok(self) -> bool:
        return self.spec is not None and not self.errors


def extract_json(text: str) -> dict:
    """Pull the JSON object out of a model reply (tolerates ```json fences and surrounding prose)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    body = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    if not body:
        raise ValueError("Phản hồi không chứa đối tượng JSON.")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise TypeError("JSON gốc phải là một đối tượng {…}.")
    return data


def draft_spec(cfg: ai_explain.AIConfig, description: str) -> str:
    """Ask the model for a draft; returns the pretty-printed JSON text (raises on a non-JSON reply)."""
    reply = ai_explain.chat(cfg, SYSTEM_PROMPT, description.strip(), temperature=0.2, timeout=180)
    return json.dumps(extract_json(reply), ensure_ascii=False, indent=2)


def check_draft(text: str) -> DraftCheck:
    res = DraftCheck()
    try:
        res.data = extract_json(text)
    except (ValueError, TypeError) as e:  # JSONDecodeError is a ValueError
        res.errors.append(f"JSON không hợp lệ: {e}")
        return res
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "draft.json"
        path.write_text(json.dumps(res.data, ensure_ascii=False), encoding="utf-8")
        try:
            res.spec = load_specification(path)
        except Exception as e:  # noqa: BLE001 - any loader failure is a draft error
            res.errors.append(f"Bộ nạp đặc tả từ chối: {e}")
            return res
    spec = res.spec
    if not spec.name or not re.fullmatch(r"[A-Za-z0-9_\-]+", spec.name):
        res.errors.append(f"name '{spec.name}' phải là chữ/số/_/- (dùng làm tên file).")

    sm = spec.state_machine
    if sm and sm.states:
        states = set(sm.states)
        bad_ends = sorted({x for t in sm.transitions for x in t if x not in states})
        if bad_ends:
            res.errors.append(f"Chuyển tiếp nhắc tới trạng thái chưa khai báo: {', '.join(bad_ends)}")
        missing_init = [s for s in sm.initial if s not in states]
        if missing_init or not sm.initial:
            res.errors.append(f"Trạng thái khởi tạo không hợp lệ: {missing_init or 'trống'}")
        if not res.errors:
            model = KripkeStructure.from_state_machine(sm, spec.name)
            report = model.verify_all(spec.safety_properties, spec.mutual_exclusions)
            for r in report.property_results:
                if r.status == "error":
                    res.errors.append(f"Công thức lỗi: {r.formula or r.title}: {r.details.splitlines()[0]}")
                res.warnings += [f"{r.formula or r.title}: {w}" for w in r.warnings]
            if report.unreachable_states:
                res.warnings.append(f"Trạng thái không tới được: {', '.join(report.unreachable_states)}")
            if report.deadlock_states:
                res.warnings.append(f"Trạng thái ngõ cụt (deadlock): {', '.join(report.deadlock_states)}")
    elif spec.safety_properties:
        res.warnings.append("Có safety_properties nhưng không có state_machine: Ch.1 sẽ bị bỏ qua.")

    for fn in spec.functions:
        if (fn.language.lower(), fn.kind.lower()) not in GENERATORS:
            res.errors.append(f"Hàm {fn.name}: ({fn.language}, {fn.kind}) không có khuôn sinh mã.")
    if not spec.safety_properties and not spec.functions and not spec.arithmetic_checks:
        res.warnings.append("Đặc tả không có gì để kiểm chứng (không luật, không hàm, không kiểm tra số học).")
    untraced = [tc.id for tc in spec.test_cases if not tc.requirement_ids]
    if untraced:
        res.warnings.append(f"Test case chưa truy vết tới yêu cầu nào: {', '.join(untraced)}")
    return res


def save_draft(check: DraftCheck, prompt: str, model: str, directory: Path = DRAFT_DIR) -> Path:
    if not check.ok:
        raise ValueError("Bản nháp còn lỗi, chưa lưu được.")
    data = dict(check.data)
    data["_draft"] = {"generated_by": f"AI ({model})", "created": datetime.now().astimezone().isoformat(timespec="seconds"),
                      "prompt": prompt.strip(), "note": "Bản nháp do AI tạo; cần người đọc lại trước khi dùng."}
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{check.spec.name}_spec.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
