"""Tests for the CTL parser and model checker (core/ctl.py)."""
import itertools
import random

import pytest

from core.ctl import CTLModelChecker, CTLSyntaxError, parse_ctl
from core.kripke import KripkeStructure


def model(states, initial, edges, labels):
    succ = {s: [] for s in states}
    for a, b in edges:
        succ[a].append(b)
    return CTLModelChecker(states, initial, succ, labels)


# --- parser -----------------------------------------------------------------
@pytest.mark.parametrize(
    "text, expected",
    [
        ("AG(!violation)", "AG(!violation)"),
        ("AG !(a & b)", "AG(!(a & b))"),
        ("AG(p -> AF(q))", "AG(p -> AF(q))"),
        ("a | b & c", "a | (b & c)"),
        ("a -> b -> c", "a -> (b -> c)"),
        ("E[a U b]", "E[a U b]"),
        ("A[ !x U (y || z) ]", "A[!x U y | z]"),
        ("EF(sach_dang_muon && !sach_con_trong)", "EF(sach_dang_muon & !sach_con_trong)"),
    ],
)
def test_parse_roundtrip(text, expected):
    assert str(parse_ctl(text)) == expected


@pytest.mark.parametrize("text", ["", "AG(", "AG(p))", "p &", "E[p q]", "AG(p @ q)", "->p"])
def test_parse_errors(text):
    with pytest.raises(CTLSyntaxError):
        parse_ctl(text)


# --- semantics on hand-built models -------------------------------------------
# free{a,b} -> busy -> stuck (self loop) ; busy -> done -> free
LASSO = {
    "states": ["free", "busy", "stuck", "done"],
    "initial": ["free"],
    "edges": [("free", "busy"), ("busy", "stuck"), ("stuck", "stuck"), ("busy", "done"), ("done", "free")],
    "labels": {"free": ["a", "b"], "busy": ["busy"], "stuck": [], "done": ["done"]},
}


def test_boolean_inside_temporal_regression():
    # Old checker returned True here: it looked for a label literally named "(a & b)".
    r = model(**LASSO).check("AG(!(a & b))")
    assert r.status == "fail"
    assert r.counterexample == ["free"]


def test_nested_liveness_fails_with_lasso():
    r = model(**LASSO).check("AG(busy -> AF(done))")
    assert r.status == "fail"
    assert r.counterexample == ["free", "busy", "stuck", "stuck"]
    assert r.loop_start == 2


def test_nested_liveness_holds():
    m = model(
        states=["idle", "busy", "done"],
        initial=["idle"],
        edges=[("idle", "busy"), ("busy", "done"), ("done", "idle")],
        labels={"idle": [], "busy": ["busy"], "done": ["done"]},
    )
    assert m.check("AG(busy -> AF(done))").status == "pass"
    assert m.check("AG(EF(done))").status == "pass"


def test_ag_counterexample_is_shortest_path():
    r = model(**LASSO).check("AG(!done)")
    assert r.status == "fail"
    assert r.counterexample == ["free", "busy", "done"]


def test_ef_witness():
    r = model(**LASSO).check("EF(done)")
    assert r.status == "pass"
    assert r.counterexample == ["free", "busy", "done"]


def test_until_operators():
    m = model(**LASSO)
    assert m.check("E[!done U done]").status == "pass"
    assert m.check("A[!done U done]").status == "fail"  # free->busy->stuck never reaches done


def test_syntax_error_is_not_a_pass():
    r = model(**LASSO).check("AG(p ->)")
    assert r.status == "error"
    assert not r.passed


def test_unknown_label_warns():
    r = model(**LASSO).check("AG(!violaton)")
    assert r.status == "pass"
    assert any("violaton" in w for w in r.warnings)


def test_deadlock_state_stutters_for_liveness():
    m = model(
        states=["s0", "s1"], initial=["s0"], edges=[("s0", "s1")], labels={"s0": [], "s1": []}
    )
    assert m.check("AF(goal)").status == "fail"  # stuck in s1 forever


def test_kripke_eval_ctl_integration():
    k = KripkeStructure(
        ["free", "main", "log", "conflict"],
        ["free"],
        [["free", "main"], ["free", "log"], ["main", "free"], ["main", "conflict"], ["log", "free"],
         ["conflict", "free"]],
        {"free": ["safe"], "main": ["main_locked"], "log": ["log_locked"],
         "conflict": ["main_locked", "log_locked", "violation"]},
    )
    res = k.eval_ctl("AG(!(main_locked & log_locked))")
    assert res.status == "fail"
    assert res.counterexample_path == ["free", "main", "conflict"]
    assert k.eval_ctl("EF(main_locked)").passed


# --- cross-check against brute-force path semantics ----------------------------
def _brute_af(succ, s, goal, depth):
    """True iff every path of length `depth` from s visits `goal` (depth >= |S| suffices)."""
    if s in goal:
        return True
    if depth == 0:
        return False
    return all(_brute_af(succ, t, goal, depth - 1) for t in succ[s])


def _brute_ef(succ, s, goal):
    seen, stack = set(), [s]
    while stack:
        x = stack.pop()
        if x in goal:
            return True
        if x not in seen:
            seen.add(x)
            stack.extend(succ[x])
    return False


@pytest.mark.parametrize("seed", range(30))
def test_random_models_match_bruteforce(seed):
    rng = random.Random(seed)
    n = rng.randint(2, 6)
    states = [f"s{i}" for i in range(n)]
    edges = [(a, b) for a, b in itertools.product(states, states) if rng.random() < 0.35]
    labels = {s: [p for p in ("p", "q") if rng.random() < 0.4] for s in states}
    m = model(states, ["s0"], edges, labels)
    succ = m.succ  # totalized
    q = {s for s in states if "q" in labels[s]}
    p = {s for s in states if "p" in labels[s]}

    reach = {s for s in states if _brute_ef(succ, "s0", {s})}
    assert (m.check("AG(!q)").status == "pass") == (not (reach & q))
    assert (m.check("EF(q)").status == "pass") == _brute_ef(succ, "s0", q)
    assert (m.check("AF(q)").status == "pass") == _brute_af(succ, "s0", q, n + 1)
    expected = all(_brute_af(succ, s, q, n + 1) for s in reach if s in p)
    assert (m.check("AG(p -> AF(q))").status == "pass") == expected
