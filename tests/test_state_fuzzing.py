"""Tests for Concolic search strategies (BFS vs DFS) and State Machine Fuzzing."""
from pathlib import Path

from core.codegen import generate_function_code
from core.fuzzing import concolic_fuzz, fuzz_state_machine, load_function, state_fuzz
from core.pipeline import run_pipeline
from core.spec_loader import FunctionSpec, StateMachine, load_specification

BASE_DIR = Path(__file__).resolve().parent.parent


def test_concolic_bfs_vs_dfs():
    """Verify both BFS and DFS search strategies in Concolic Fuzzing find target crashes."""
    gf = generate_function_code(
        FunctionSpec("unlock", "python", "magic_value", ["a", "b"], magic_values=[6284, 4917])
    )
    f = load_function(gf.code_vulnerable, "unlock")

    res_bfs = concolic_fuzz(f, gf.code_vulnerable, "magic_value", 50, search_strategy="bfs")
    assert res_bfs.found
    assert res_bfs.first_input == (6284, 4917)
    assert res_bfs.search_strategy == "bfs"

    res_dfs = concolic_fuzz(f, gf.code_vulnerable, "magic_value", 50, search_strategy="dfs")
    assert res_dfs.found
    assert res_dfs.first_input == (6284, 4917)
    assert res_dfs.search_strategy == "dfs"


def test_state_fuzzing_bfs_finds_shortest_crash():
    """Verify that BFS discovers the shortest state path leading to invariant crash."""
    sm = StateMachine(
        states=["S0", "S1", "S2", "S_BAD"],
        initial=["S0"],
        transitions=[
            ["S0", "S1"],
            ["S1", "S2"],
            ["S2", "S0"],
            ["S0", "S_BAD"],  # 1 step from S0
        ],
        labeling={"S_BAD": ["violation"]},
    )
    res = state_fuzz(sm, strategy="bfs", max_depth=5, budget=50)
    assert res.has_crash
    crash = res.crashes[0]
    assert crash.state == "S_BAD"
    assert crash.path == ["S0", "S_BAD"]
    assert res.state_coverage == 1.0


def test_state_fuzzing_deadlock_detection():
    """Verify that state fuzzing detects deadlock states."""
    sm = StateMachine(
        states=["INIT", "PROCESSING", "STUCK"],
        initial=["INIT"],
        transitions=[["INIT", "PROCESSING"], ["PROCESSING", "STUCK"]],
        labeling={},
    )
    res = state_fuzz(sm, strategy="dfs", max_depth=5, budget=50)
    assert res.has_crash
    deadlock_crashes = [c for c in res.crashes if c.kind == "deadlock"]
    assert len(deadlock_crashes) == 1
    assert deadlock_crashes[0].state == "STUCK"
    assert deadlock_crashes[0].path == ["INIT", "PROCESSING", "STUCK"]


def test_state_fuzzing_coverage_guided():
    """Verify coverage-guided state sequence fuzzing covers states and transitions."""
    sm = StateMachine(
        states=["A", "B", "C", "D"],
        initial=["A"],
        transitions=[["A", "B"], ["B", "C"], ["C", "D"], ["D", "A"], ["B", "D"]],
        labeling={},
    )
    res = state_fuzz(sm, strategy="coverage", max_depth=6, budget=80, seed=42)
    assert res.state_coverage == 1.0
    assert res.transition_coverage > 0.8
    assert res.paths_explored > 10


def test_payment_gateway_v0_vs_v1_state_fuzzing():
    """Verify that v0 triggers crashes on state violations and v1 has 0 crashes."""
    spec_v0 = load_specification(str(BASE_DIR / "dataset" / "specs_excel" / "payment_gateway_v0_spec.xlsx"))
    results_v0 = fuzz_state_machine(spec_v0.state_machine, budget=100, version="v0")

    bfs_v0 = next(r for r in results_v0 if r.strategy == "bfs")
    assert bfs_v0.has_crash
    crash_states = {c.state for c in bfs_v0.crashes}
    assert "DUPLICATE_CAPTURE" in crash_states
    assert "SHIPPED_UNPAID" in crash_states
    assert "lock_conflict" in crash_states

    spec_v1 = load_specification(str(BASE_DIR / "dataset" / "specs_excel" / "payment_gateway_v1_spec.xlsx"))
    results_v1 = fuzz_state_machine(spec_v1.state_machine, budget=100, version="v1")
    for r in results_v1:
        assert not r.has_crash


def test_pipeline_integration_state_fuzz():
    """Verify state fuzzing runs in the verification pipeline."""
    spec = load_specification(str(BASE_DIR / "dataset" / "specs_excel" / "payment_gateway_v0_spec.xlsx"))
    rep = run_pipeline(spec, seed=1, fuzz_budget=50, run_tools=False, fuzz_search="dfs")
    assert len(rep.state_fuzz) == 3  # bfs, dfs, coverage
    bfs = next(r for r in rep.state_fuzz if r.strategy == "bfs")
    assert bfs.has_crash
