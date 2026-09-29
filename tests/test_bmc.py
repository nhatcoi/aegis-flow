"""Tests for Z3 bounded model checking (core/bmc.py)."""
from core.bmc import bmc_check, bmc_properties, reachability_diameter
from core.kripke import KripkeStructure

MUTEX = KripkeStructure(
    ["free", "main", "log", "conflict"],
    ["free"],
    [["free", "main"], ["free", "log"], ["main", "free"], ["main", "conflict"], ["log", "free"],
     ["conflict", "free"]],
    {"free": ["safe"], "main": ["main_locked"], "log": ["log_locked"],
     "conflict": ["main_locked", "log_locked", "violation"]},
)

LOGIN = KripkeStructure(
    ["idle", "entering", "verified", "session"],
    ["idle"],
    [["idle", "entering"], ["entering", "idle"], ["entering", "verified"], ["verified", "session"],
     ["session", "idle"]],
    {"idle": [], "entering": [], "verified": ["authenticated"], "session": ["authenticated", "logged_in"]},
)


def test_diameter():
    assert reachability_diameter(MUTEX) == 2
    assert reachability_diameter(LOGIN) == 3


def test_unsafe_mutex_gives_minimal_counterexample():
    r = bmc_check(MUTEX, "AG(!(main_locked & log_locked))")
    assert r.status == "unsafe"
    assert r.violation_depth == 2
    assert r.counterexample == ["free", "main", "conflict"]
    assert [s.result for s in r.steps] == ["unsat", "unsat", "sat"]


def test_safe_reaches_completeness_threshold():
    r = bmc_check(LOGIN, "AG(logged_in -> authenticated)")
    assert r.status == "safe_complete"
    assert r.completeness_threshold == 3
    assert len(r.steps) == 4


def test_bound_below_threshold_is_only_bounded_safety():
    r = bmc_check(MUTEX, "AG(!violation)", max_bound=1)
    assert r.status == "safe_bounded"
    assert "CHƯA" in r.details


def test_rejects_temporal_body():
    assert bmc_check(LOGIN, "AG(entering -> AF(session))").status == "error"


def test_bmc_properties_collects_mutex_pairs():
    results = bmc_properties(MUTEX, ["AG(!violation)", "EF(main_locked)"],
                             [{"atom1": "main_locked", "atom2": "log_locked"}])
    assert [r.property for r in results] == ["AG(!violation)", "AG(!(main_locked & log_locked))"]
    assert all(r.status == "unsafe" for r in results)
