"""Rule-based diagnosis of failed Kripke/CTL checks."""
from pathlib import Path

from core.diagnosis import diagnose, related_requirements
from core.kripke import KripkeStructure
from core.spec_loader import load_specification

SPEC = Path(__file__).resolve().parent.parent / "dataset" / "specs_excel" / "payment_gateway_v0_spec.xlsx"


def _checked():
    spec = load_specification(SPEC)
    model = KripkeStructure.from_state_machine(spec.state_machine, spec.name)
    report = model.verify_all(spec.safety_properties, spec.mutual_exclusions)
    return spec, model, {r.formula or r.kind: r for r in report.property_results}


def test_safety_violation_points_at_last_transition():
    spec, model, results = _checked()
    lines = diagnose(results["AG(shipped -> paid)"], model)
    assert any("UNKNOWN → SHIPPED_UNPAID" in line for line in lines)
    assert [q.id for q in related_requirements(results["AG(shipped -> paid)"], spec)] == ["REQ-1"]


def test_lasso_reports_loop_and_exits():
    _, model, results = _checked()
    lines = diagnose(results["AG(timeout -> AF(paid | failed))"], model)
    assert any("vòng lặp" in line and "UNKNOWN" in line for line in lines)


def test_deadlock_names_dead_end_state():
    spec, model, results = _checked()
    lines = diagnose(results["deadlock"], model)
    assert any("REFUNDING" in line and "không có chuyển tiếp" in line for line in lines)
    assert {"REQ-3", "REQ-4", "REQ-13"} <= {q.id for q in related_requirements(results["deadlock"], spec)}


def test_passing_property_has_no_diagnosis():
    _, model, results = _checked()
    assert diagnose(results["AG(!(paid & failed))"], model) == []
