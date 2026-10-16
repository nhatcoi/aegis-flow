"""Validation of AI-drafted specifications (no network: the model reply is given as text)."""
import json

from core.spec_draft import check_draft, extract_json, save_draft

GOOD = {
    "name": "ticket_demo",
    "requirements": [{"id": "REQ-1", "text": "Chỉ xuất vé khi đã trả tiền", "category": "safety"}],
    "state_machine": {
        "states": ["held", "paid", "issued_bug"], "initial": ["held"],
        "labeling": {"held": ["held"], "paid": ["paid"], "issued_bug": ["issued", "violation"]},
        "transitions": [["held", "paid"], ["held", "issued_bug"], ["paid", "held"], ["issued_bug", "held"]],
    },
    "safety_properties": ["AG(issued -> paid)", "AG(!violation)"],
    "functions": [{"name": "copy_seat", "language": "c", "kind": "buffer_copy", "params": ["code"],
                   "buffer_size": 16, "bug": "buffer-overflow"}],
    "test_cases": [{"id": "TC-1", "requirement_ids": ["REQ-1"], "expected_result": "AG(issued -> paid) ĐÚNG"}],
}


def test_extract_json_tolerates_fences_and_prose():
    reply = "Đây là đặc tả:\n```json\n" + json.dumps(GOOD) + "\n```\nChúc bạn thành công."
    assert extract_json(reply)["name"] == "ticket_demo"


def test_valid_draft_is_accepted():
    res = check_draft(json.dumps(GOOD))
    assert res.ok and res.spec.name == "ticket_demo" and not res.errors


def test_structural_mistakes_block_saving():
    bad = json.loads(json.dumps(GOOD))
    bad["state_machine"]["transitions"].append(["paid", "ghost"])
    bad["safety_properties"].append("AG(issued ->")
    bad["functions"].append({"name": "x", "language": "c", "kind": "quantum_sort"})
    res = check_draft(json.dumps(bad))
    assert not res.ok
    text = " ".join(res.errors)
    assert "ghost" in text and "quantum_sort" in text


def test_unknown_atom_and_dead_end_are_warnings():
    draft = json.loads(json.dumps(GOOD))
    draft["safety_properties"].append("AG(!refundd)")
    draft["state_machine"]["transitions"].remove(["issued_bug", "held"])
    res = check_draft(json.dumps(draft))
    assert res.ok
    assert any("refundd" in w for w in res.warnings)
    assert any("issued_bug" in w and "deadlock" in w for w in res.warnings)


def test_saved_draft_is_marked_as_ai_generated(tmp_path):
    path = save_draft(check_draft(json.dumps(GOOD)), "mô tả", "v8", directory=tmp_path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "ticket_demo_spec.json" and saved["_draft"]["generated_by"] == "AI (v8)"


def test_non_json_reply_is_an_error():
    assert not check_draft("Xin lỗi, tôi không thể giúp.").ok
