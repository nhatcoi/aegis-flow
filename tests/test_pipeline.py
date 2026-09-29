"""End-to-end tests: payment gateway v0/v1 specs, test-case evaluation and results export."""
import json
from pathlib import Path

import pytest

from core.pipeline import main, run_pipeline
from core.spec_loader import TestCase, load_specification
from core.toolchain import compiler

HAS_CC = compiler() is not None

SPECS = Path(__file__).resolve().parent.parent / "dataset" / "specs_excel"


@pytest.fixture(scope="module")
def v0():
    return run_pipeline(load_specification(SPECS / "payment_gateway_v0_spec.xlsx"), fuzz_budget=500, run_tools=HAS_CC)


@pytest.fixture(scope="module")
def v1():
    return run_pipeline(load_specification(SPECS / "payment_gateway_v1_spec.xlsx"), fuzz_budget=500, run_tools=False)


def test_spec_meets_course_checklist():
    spec = load_specification(SPECS / "payment_gateway_v0_spec.xlsx")
    assert len(spec.requirements) >= 5 and len(spec.test_cases) >= 5 and len(spec.arithmetic_checks) >= 5
    assert {r.category for r in spec.requirements} == {"safety", "liveness", "memory", "functional"}
    assert len(spec.mutual_exclusions) >= 5
    bugs = {f.bug for f in spec.functions if f.language == "c"}
    assert {"buffer-overflow", "memory-leak", "double-free", "use-after-free"} <= bugs
    assert {"divide", "magic_value"} <= {f.kind for f in spec.functions if f.language == "python"}


def test_v0_design_flaws_have_counterexamples(v0):
    results = {r.formula: r for r in v0.kripke.property_results if r.formula}
    assert results["AG(shipped -> paid)"].counterexample_path[-1] == "SHIPPED_UNPAID"
    liveness = results["AG(timeout -> AF(paid | failed))"]
    assert liveness.status == "fail" and liveness.loop_start is not None
    assert results["AG(!double_capture)"].status == "fail"
    assert v0.kripke.deadlock_states == ["REFUNDING"]
    bmc = {b.property: b for b in v0.bmc}
    assert bmc["AG(!violation)"].status == "unsafe" and bmc["AG(!violation)"].violation_depth == 2


@pytest.mark.skipif(not HAS_CC, reason="CWE-190 in C code is only confirmed by UBSan")
def test_v0_every_declared_bug_is_confirmed_by_a_tool(v0):
    assert not v0.audit.declared_only
    cwes = {f.cwe_id for f in v0.audit.confirmed}
    assert {"CWE-120", "CWE-401", "CWE-415", "CWE-416", "CWE-190", "CWE-369", "CWE-798", "CWE-667",
            "CWE-693", "CWE-833"} <= cwes
    code_findings = [f for f in v0.audit.confirmed if f.fixed is not None]
    assert code_findings and all(f.fixed for f in code_findings)


def test_v1_is_clean(v1):
    assert v1.kripke.is_valid
    assert all(b.passed for b in v1.bmc)
    assert not v1.audit.open_findings
    assert [t.status for t in v1.test_results] == ["PASS"] * len(v1.test_results)


@pytest.mark.skipif(not HAS_CC, reason="TC-8 needs UBSan evidence")
def test_v0_test_cases_fail_where_bugs_exist(v0):
    status = {t.test_case.id: t.status for t in v0.test_results}
    assert status["TC-9"] == "PASS" and status["TC-12"] == "PASS"
    assert all(status[f"TC-{i}"] == "FAIL" for i in (1, 2, 3, 4, 5, 6, 7, 8, 10, 11))


@pytest.mark.parametrize(
    "expected, status",
    [
        ("Không phát hiện CWE-120 tại parse_order_id", "PASS"),
        ("Phát hiện CWE-120 tại parse_webhook_signature", "PASS"),
        ("Không phát hiện CWE-120 tại parse_webhook_signature", "FAIL"),
        ("AG(!double_capture) SAI", "PASS"),
        ("Tìm được input (7788, 9999)", "PASS"),
        ("Hệ thống hoạt động ổn định", "NOT_EVALUATED"),
    ],
)
def test_expected_result_phrases(v0, expected, status):
    from core.pipeline import evaluate_test_case

    assert evaluate_test_case(TestCase("TC-x", expected_result=expected), v0).status == status


def test_cli_writes_results_folder(tmp_path):
    out = tmp_path / "res"
    assert main([str(SPECS / "payment_gateway_v0_spec.xlsx"), "--budget", "200", "--no-tools", "--out", str(out)]) == 0
    for rel in ("report.md", "before_after.md", "summary.json", "environment.txt", "logs/ctl.txt", "logs/bmc.txt",
                "logs/scan.txt", "logs/z3.txt", "logs/fuzz.csv", "logs/ast.csv", "logs/tests.csv",
                "figures/kripke.png", "figures/kripke.tex", "source/parse_webhook_signature_v0.c",
                "source/refund_ratio_v1.py"):
        assert (out / rel).exists(), rel
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["spec"] == "payment_gateway_v0"
    assert "| CWE-120 |" in (out / "before_after.md").read_text(encoding="utf-8")
