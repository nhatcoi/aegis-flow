"""Automated tests for the AegisFlow core pipeline."""
from pathlib import Path

from core.arithmetic_z3 import check_all_arithmetic
from core.codegen import generate_all_functions
from core.cwe_analyzer import analyze_security_vulnerabilities
from core.kripke import KripkeStructure
from core.pipeline import run_pipeline
from core.reporter import generate_markdown_report
from core.spec_loader import load_specification

BASE_DIR = Path(__file__).resolve().parent.parent
SPECS_JSON_DIR = BASE_DIR / "dataset" / "specs"
SPECS_EXCEL_DIR = BASE_DIR / "dataset" / "specs_excel"


def test_auth_rate_limit_spec():
    spec_path = SPECS_JSON_DIR / "auth_rate_limit_spec.json"
    assert spec_path.exists()
    spec = load_specification(spec_path)
    assert spec.name == "auth_rate_limit"
    assert len(spec.requirements) >= 7

    # 1. Kripke
    assert spec.state_machine is not None
    kripke = KripkeStructure.from_state_machine(spec.state_machine, spec.name)
    report = kripke.verify_all(spec.safety_properties, spec.mutual_exclusion)
    assert report.is_valid is True
    assert len(report.deadlock_states) == 0

    # 2. Codegen
    funcs = generate_all_functions(spec)
    assert len(funcs) == 4
    names = [f.spec.name for f in funcs]
    assert "parse_username" in names
    assert "cleanup_session" in names

    # 3. Arithmetic Z3
    smt_res = check_all_arithmetic(spec.arithmetic_checks)
    assert len(smt_res) == 1
    assert smt_res[0].overflow_possible is True  # Known integer overflow in counter

    # 4. CWE analysis
    audit = analyze_security_vulnerabilities(spec, report, smt_res)
    assert audit.total_findings >= 4
    cwes = [f.cwe_id for f in audit.findings]
    assert "CWE-120" in cwes  # Buffer overflow
    assert "CWE-415" in cwes  # Double free
    assert "CWE-190" in cwes  # Integer overflow


def test_session_manager_mutex_violation():
    spec_path = SPECS_JSON_DIR / "session_manager_spec.json"
    spec = load_specification(spec_path)
    assert spec.state_machine is not None

    kripke = KripkeStructure.from_state_machine(spec.state_machine, spec.name)
    report = kripke.verify_all(spec.safety_properties, spec.mutual_exclusion)
    # session_manager has a known mutex flaw
    assert report.is_valid is False
    assert any("p1 & p2" in r.title and not r.passed for r in report.property_results)


def test_session_manager_fixed():
    spec_path = SPECS_JSON_DIR / "session_manager_fixed_spec.json"
    spec = load_specification(spec_path)
    assert spec.state_machine is not None

    kripke = KripkeStructure.from_state_machine(spec.state_machine, spec.name)
    report = kripke.verify_all(spec.safety_properties, spec.mutual_exclusion)
    assert report.is_valid is True


def test_excel_elevator_control():
    spec_path = SPECS_EXCEL_DIR / "elevator_control_spec.xlsx"
    assert spec_path.exists()
    spec = load_specification(spec_path)
    assert spec.name == "elevator_control"
    assert len(spec.requirements) >= 5

    kripke = KripkeStructure.from_state_machine(spec.state_machine, spec.name)
    report = kripke.verify_all(spec.safety_properties, spec.mutual_exclusion)
    assert report.is_valid is True

    funcs = generate_all_functions(spec)
    assert len(funcs) >= 1

    smt_res = check_all_arithmetic(spec.arithmetic_checks)
    assert len(smt_res) >= 1

    audit = analyze_security_vulnerabilities(spec, report, smt_res)
    assert audit.total_findings >= 1

    md_report = generate_markdown_report(run_pipeline(spec, fuzz_budget=200, run_tools=False))
    assert "Kết quả kiểm chứng" in md_report


def test_payment_ecommerce_spec():
    spec_path = SPECS_JSON_DIR / "payment_ecommerce_spec.json"
    assert spec_path.exists()
    spec = load_specification(spec_path)
    assert spec.name == "payment_ecommerce"

    # 1. Kripke
    assert spec.state_machine is not None
    kripke = KripkeStructure.from_state_machine(spec.state_machine, spec.name)
    report = kripke.verify_all(spec.safety_properties, spec.mutual_exclusion)
    assert report.is_valid is True
    assert len(report.deadlock_states) == 0

    # 2. Codegen
    funcs = generate_all_functions(spec)
    assert len(funcs) == 5
    names = [f.spec.name for f in funcs]
    assert "parse_webhook_signature" in names
    assert "cleanup_payment_session" in names
    assert "calculate_total_payment" in names
    assert "refund_ratio" in names

    # 3. Arithmetic Z3
    smt_res = check_all_arithmetic(spec.arithmetic_checks)
    assert len(smt_res) == 1
    assert smt_res[0].overflow_possible is True

    # 4. CWE Analysis
    audit = analyze_security_vulnerabilities(spec, report, smt_res)
    cwes = [f.cwe_id for f in audit.findings]
    assert "CWE-120" in cwes  # Buffer overflow
    assert "CWE-415" in cwes  # Double free
    assert "CWE-190" in cwes  # Integer overflow
    assert "CWE-369" in cwes  # Divide by zero


def test_payment_flawed_spec():
    spec_path = SPECS_JSON_DIR / "payment_flawed_spec.json"
    assert spec_path.exists()
    spec = load_specification(spec_path)

    kripke = KripkeStructure.from_state_machine(spec.state_machine, spec.name)
    report = kripke.verify_all(spec.safety_properties, spec.mutual_exclusion)
    # UNKNOWN has no outgoing transition -> Deadlock!
    assert report.is_valid is False
    assert "UNKNOWN" in report.deadlock_states

