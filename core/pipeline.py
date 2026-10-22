"""End-to-end verification pipeline: Spec -> Kripke/CTL -> BMC -> Code -> Scan/ASan -> SMT -> Fuzz -> CWE.

Single entry point shared by the CLI and the GUI::

    uv run python -m core.pipeline dataset/specs_excel/payment_gateway_v0_spec.xlsx --seed 1 --out results/payment_gateway_v0
"""
from __future__ import annotations

import argparse
import platform
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import z3

from .arithmetic_z3 import SMTCheckResult, check_all_arithmetic
from .bmc import BMCResult, bmc_properties
from .c_analyzer import Finding, analyze_c_source
from .codegen import GeneratedFunction, generate_all_functions
from .cwe_analyzer import SecurityAuditReport, analyze_security_vulnerabilities
from .fuzzing import FuzzResult, StateFuzzResult, fuzz_generated, fuzz_state_machine
from .kripke import KripkeCheckReport, KripkeStructure
from .spec_loader import Specification, TestCase, load_specification
from .static_ast import FunctionMetrics, function_metrics
from .toolchain import SanitizerRun, compiler_version, run_cppcheck, run_sanitizers


@dataclass
class TestCaseResult:
    test_case: TestCase
    status: str  # "PASS" | "FAIL" | "NOT_EVALUATED"
    reason: str


@dataclass
class PipelineReport:
    spec: Specification
    seed: int
    fuzz_budget: int
    kripke_model: KripkeStructure | None = None
    kripke: KripkeCheckReport | None = None
    flows: dict[str, KripkeCheckReport] = field(default_factory=dict)
    bmc: list[BMCResult] = field(default_factory=list)
    functions: list[GeneratedFunction] = field(default_factory=list)
    static: dict[tuple[str, str], list[Finding]] = field(default_factory=dict)
    sanitizers: list[SanitizerRun] = field(default_factory=list)
    cppcheck: dict[tuple[str, str], str] = field(default_factory=dict)
    metrics: list[tuple[str, FunctionMetrics]] = field(default_factory=list)
    smt: list[SMTCheckResult] = field(default_factory=list)
    fuzz: list[FuzzResult] = field(default_factory=list)
    state_fuzz: list[StateFuzzResult] = field(default_factory=list)
    audit: SecurityAuditReport | None = None
    test_results: list[TestCaseResult] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)


def environment_info(seed: int, budget: int, bmc_depth: int | None = None,
                     sanitizer_timeout: int = 30) -> dict[str, str]:
    return {
        "thời gian": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        "hệ điều hành": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": sys.version.split()[0],
        "z3-solver": z3.get_version_string(),
        "trình biên dịch C": compiler_version(),
        "seed": str(seed),
        "ngân sách fuzzing": str(budget),
        "độ sâu BMC": "tự động (CT)" if bmc_depth is None else str(bmc_depth),
        "timeout sanitizer": f"{sanitizer_timeout}s",
    }


# ---------------------------------------------------------------------------
# Test case evaluation
# ---------------------------------------------------------------------------
NEGATION_RE = re.compile(r"(không|khong|0)\b[^.;]{0,40}$", re.IGNORECASE)


def _negated(text: str, pos: int) -> bool:
    """True when the phrase at `pos` is preceded (same clause) by a negation, e.g. 'Không phát hiện CWE-120'."""
    return bool(NEGATION_RE.search(text[max(0, pos - 45):pos]))


def evaluate_test_case(tc: TestCase, rep: PipelineReport) -> TestCaseResult:
    """Decide PASS/FAIL from the expected-result text when it names something checkable.

    Recognised clauses (optionally negated with "không"): CWE-xxx [tại <hàm>], a CTL formula
    followed by ĐÚNG/SAI, "không deadlock", Z3 SAT / UNSAT, crash / ZeroDivisionError / bypass
    [tại <hàm>], and a concrete input pair "(a, b)" that a fuzzer must find.
    """
    exp = tc.expected_result
    checks: list[tuple[bool, str]] = []
    components = [fn.name for fn in rep.spec.functions if fn.name in exp]
    components += [s.name for s in rep.smt if s.name in exp]

    def relevant_findings(cwe: str):
        found = [f for f in rep.audit.confirmed if f.cwe_id == cwe] if rep.audit else []
        return [f for f in found if f.source_component in components] if components else found

    for m in re.finditer(r"CWE-\d+", exp):
        hits = relevant_findings(m.group(0))
        where = f" tại {', '.join(components)}" if components else ""
        if _negated(exp, m.start()):
            checks.append((not hits, f"{m.group(0)}{where}: {len(hits)} phát hiện (mong đợi 0)"))
        else:
            checks.append((bool(hits), f"{m.group(0)}{where}: {len(hits)} phát hiện (mong đợi ≥ 1)"))

    props = {r.formula: r for r in (rep.kripke.property_results if rep.kripke else []) if r.formula}
    compact = exp.replace(" ", "")
    for formula, r in props.items():
        pos = compact.find(formula.replace(" ", ""))
        if pos < 0:
            continue
        tail = compact[pos + len(formula.replace(" ", "")):][:12].upper()
        if tail.startswith(("ĐÚNG", "DUNG", "TRUE", "ĐẠT")):
            checks.append((r.passed, f"{formula} = {'đúng' if r.passed else 'sai'} (mong đợi đúng)"))
        elif tail.startswith(("SAI", "FALSE", "VIPHẠM")):
            checks.append((not r.passed, f"{formula} = {'đúng' if r.passed else 'sai'} (mong đợi sai)"))
    if re.search(r"không (có )?(trạng thái )?deadlock|không bị treo|khong bi treo", exp, re.IGNORECASE) and rep.kripke:
        checks.append((not rep.kripke.deadlock_states, f"deadlock: {', '.join(rep.kripke.deadlock_states) or 'không'}"))

    smt = [s for s in rep.smt if s.name in components] or rep.smt
    if re.search(r"\bUNSAT\b", exp):
        checks.append((bool(smt) and all(s.patch_status == "unsat" for s in smt), "Z3 UNSAT với tiền điều kiện của v1"))
    if re.search(r"(?<!UN)\bSAT\b", exp):
        checks.append((any(s.overflow_possible for s in smt), "Z3 SAT (tồn tại input gây tràn)"))

    m = re.search(r"ZeroDivisionError|crash|bypass|vượt qua xác thực", exp, re.IGNORECASE)
    if m:
        fz = [r for r in rep.fuzz if r.version == "v0" and (not components or r.function in components)]
        found = [r for r in fz if r.found]
        if _negated(exp, m.start()):
            checks.append((not found, f"fuzzing: {len(found)}/{len(fz)} chiến dịch tìm ra lỗi (mong đợi 0)"))
        else:
            checks.append((bool(found), f"fuzzing: {len(found)}/{len(fz)} chiến dịch tìm ra lỗi (mong đợi ≥ 1)"))
    m = re.search(r"\((-?\d+)\s*,\s*(-?\d+)\)", exp)
    if m:
        target = (int(m.group(1)), int(m.group(2)))
        hit = [r for r in rep.fuzz if r.version == "v0" and r.first_input == target]
        checks.append((bool(hit), f"input {target} {'được' if hit else 'không được'} fuzzer tìm ra"))

    if not checks:
        return TestCaseResult(tc, "NOT_EVALUATED", "Kết quả mong đợi không nêu tiêu chí kiểm tra tự động được.")
    ok = all(c for c, _ in checks)
    return TestCaseResult(tc, "PASS" if ok else "FAIL", "; ".join(r for _, r in checks))


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def run_pipeline(spec: Specification, seed: int = 1, fuzz_budget: int = 2000, *,
                 run_tools: bool = True, workdir: Path | None = None,
                 bmc_depth: int | None = None, sanitizer_timeout: int = 30,
                 fuzz_search: str = "bfs") -> PipelineReport:
    """``bmc_depth=None`` runs BMC up to the completeness threshold (reachability diameter)."""
    rep = PipelineReport(spec, seed, fuzz_budget,
                         environment=environment_info(seed, fuzz_budget, bmc_depth, sanitizer_timeout))

    def timed(key: str):
        class _T:
            def __enter__(self):
                self.t = time.perf_counter()

            def __exit__(self, *exc):
                rep.timings[key] = time.perf_counter() - self.t
        return _T()

    with timed("ch1_kripke"):
        if spec.state_machine and spec.state_machine.states:
            rep.kripke_model = KripkeStructure.from_state_machine(spec.state_machine, spec.name)
            rep.kripke = rep.kripke_model.verify_all(spec.safety_properties, spec.mutual_exclusions)
        for name, sm in spec.additional_flows.items():
            rep.flows[name] = KripkeStructure.from_state_machine(sm, name).verify_all(
                spec.safety_properties, spec.mutual_exclusions)

    with timed("ch3_bmc"):
        if rep.kripke_model:
            rep.bmc = bmc_properties(rep.kripke_model, spec.safety_properties, spec.mutual_exclusions,
                                     max_bound=bmc_depth)

    with timed("codegen"):
        rep.functions = generate_all_functions(spec)

    with timed("ch2_static"):
        for gf in rep.functions:
            for version in ("v0", "v1"):
                if gf.language == "c":
                    code = gf.code_vulnerable if version == "v0" else gf.code_safe
                    rep.static[(gf.spec.name, version)] = analyze_c_source(code, f"{gf.spec.name}_{version}.c")
                    if run_tools:
                        out = run_cppcheck(code, f"{gf.spec.name}_{version}.c")
                        if out is not None:
                            rep.cppcheck[(gf.spec.name, version)] = out
                rep.metrics.append((version, function_metrics(gf, version)))

    with timed("ch2_sanitizers"):
        if run_tools:
            with tempfile.TemporaryDirectory() as tmp:
                build_dir = workdir or Path(tmp)
                for gf in rep.functions:
                    if gf.language == "c" and (gf.has_bug or gf.spec.kind == "arithmetic"):
                        for version in ("v0", "v1"):
                            rep.sanitizers.append(run_sanitizers(gf, version, build_dir, timeout=sanitizer_timeout))

    with timed("ch3_smt"):
        rep.smt = check_all_arithmetic(spec.arithmetic_checks)

    with timed("ch4_fuzz"):
        for gf in rep.functions:
            rep.fuzz.extend(fuzz_generated(gf, fuzz_budget, seed, concolic_strategy=fuzz_search))
        if spec.state_machine and spec.state_machine.states:
            deadlocks = set(rep.kripke.deadlock_states) if rep.kripke else None
            rep.state_fuzz = fuzz_state_machine(
                spec.state_machine,
                budget=min(fuzz_budget, 500),
                seed=seed,
                known_deadlocks=deadlocks,
            )

    with timed("cwe"):
        rep.audit = analyze_security_vulnerabilities(
            spec, rep.kripke, rep.smt, functions=rep.functions, static=rep.static,
            sanitizers=rep.sanitizers, fuzz=rep.fuzz, bmc=rep.bmc)
        rep.test_results = [evaluate_test_case(tc, rep) for tc in spec.test_cases]
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chạy toàn bộ pipeline kiểm chứng và xuất bằng chứng.")
    parser.add_argument("spec", help="Đặc tả .json hoặc .xlsx")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--budget", type=int, default=2000, help="Số lần thử fuzzing cho mỗi chiến lược")
    parser.add_argument("--fuzz-search", choices=["bfs", "dfs"], default="bfs",
                        help="Chiến lược duyệt cây đường đi cho Concolic Fuzzing (mặc định: bfs)")
    parser.add_argument("--bmc-depth", type=int, metavar="K",
                        help="Độ sâu tối đa của BMC (mặc định: completeness threshold của mô hình)")
    parser.add_argument("--sanitizer-timeout", type=int, default=30, metavar="GIÂY",
                        help="Thời gian tối đa cho mỗi lần chạy harness ASan/UBSan (mặc định 30)")
    parser.add_argument("--out", type=Path, help="Thư mục xuất kết quả (mặc định results/<tên đặc tả>)")
    parser.add_argument("--no-tools", action="store_true", help="Bỏ qua biên dịch/ASan/cppcheck")
    parser.add_argument("--compare", metavar="SPEC_V1",
                        help="Đặc tả đã sửa: chạy thêm và ghi comparison.md (so sánh thiết kế trước/sau)")
    args = parser.parse_args(argv)

    from .reporter import comparison_markdown, write_results

    spec = load_specification(args.spec)
    out = args.out or Path("results") / spec.name
    opts = {"run_tools": not args.no_tools, "bmc_depth": args.bmc_depth,
            "sanitizer_timeout": args.sanitizer_timeout, "fuzz_search": args.fuzz_search}
    rep = run_pipeline(spec, args.seed, args.budget, workdir=out / "build", **opts)
    write_results(rep, out)
    if args.compare:
        fixed = load_specification(args.compare)
        fixed_out = out.parent / fixed.name
        fixed_rep = run_pipeline(fixed, args.seed, args.budget, workdir=fixed_out / "build", **opts)
        write_results(fixed_rep, fixed_out)
        (out / "comparison.md").write_text(comparison_markdown(rep, fixed_rep), encoding="utf-8")
        print(f"Đã ghi so sánh thiết kế vào {out / 'comparison.md'}")
    print(rep.audit.summary_text)
    print()
    for tr in rep.test_results:
        print(f"{tr.test_case.id}: {tr.status} — {tr.reason}")
    print(f"\nĐã xuất kết quả vào {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
