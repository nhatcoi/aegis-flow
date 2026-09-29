"""Bounded Model Checking of Kripke safety properties with Z3 (Chương 3.5).

For a safety property AG(phi) with phi propositional, the bad states are
``bad = S \\ sat(phi)`` and the k-step BMC query is::

    BMC_k = I(s_0) & AND_{i<k} R(s_i, s_{i+1}) & OR_{i<=k} bad(s_i)

Each ``s_i`` is a Z3 integer holding a state index. The query is solved for
k = 0, 1, ..., K. The completeness threshold used is the reachability diameter
(the largest BFS distance from the initial states): every reachable state is
reachable within that many steps, so "no violation up to CT" proves the
property for paths of any length.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

import z3

from .ctl import CTLModelChecker, CTLSyntaxError, Node, parse_ctl
from .kripke import KripkeStructure


@dataclass
class BMCStep:
    k: int
    result: str  # "sat" | "unsat"
    seconds: float


@dataclass
class BMCResult:
    property: str
    status: str  # "unsafe" | "safe_complete" | "safe_bounded" | "error"
    details: str
    bad_states: list[str] = field(default_factory=list)
    counterexample: list[str] = field(default_factory=list)
    violation_depth: int | None = None
    completeness_threshold: int = 0
    max_bound: int = 0
    steps: list[BMCStep] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status in ("safe_complete", "safe_bounded")

    def to_text(self) -> str:
        lines = [f"BMC {self.property}: {self.status.upper()}", self.details]
        lines.append(f"  completeness threshold (CT) = {self.completeness_threshold}, K = {self.max_bound}")
        for st in self.steps:
            lines.append(f"  k={st.k:<3} BMC_k {st.result:<5} ({st.seconds * 1000:.1f} ms)")
        if self.counterexample:
            lines.append("  Counterexample:")
            for i, s in enumerate(self.counterexample):
                lines.append(f"    s_{i} = {s}")
        return "\n".join(lines)


def reachability_diameter(kripke: KripkeStructure) -> int:
    dist = {s: 0 for s in kripke.initial if s in kripke.succ}
    queue = deque(dist)
    while queue:
        s = queue.popleft()
        for t in kripke.succ[s]:
            if t not in dist:
                dist[t] = dist[s] + 1
                queue.append(t)
    return max(dist.values(), default=0)


def _is_propositional(n: Node) -> bool:
    return n.op in ("atom", "true", "false") or (
        n.op in ("not", "and", "or", "implies", "iff") and all(_is_propositional(a) for a in n.args)
    )


def safety_body(prop: str) -> Node:
    """Return phi for a property of the form AG(phi) with phi propositional."""
    node = parse_ctl(prop)
    if node.op != "AG" or not _is_propositional(node.args[0]):
        raise CTLSyntaxError("BMC chỉ hỗ trợ thuộc tính an toàn dạng AG(φ) với φ không chứa toán tử thời gian")
    return node.args[0]


def bmc_check(kripke: KripkeStructure, prop: str, max_bound: int | None = None) -> BMCResult:
    ct = reachability_diameter(kripke)
    bound = ct if max_bound is None else max_bound
    try:
        phi = safety_body(prop)
    except CTLSyntaxError as e:
        return BMCResult(prop, "error", f"LỖI: {e}", completeness_threshold=ct, max_bound=bound)

    checker = CTLModelChecker(kripke.states, kripke.initial, kripke.succ, kripke.labeling)
    good = checker.sat(phi)
    bad = [s for s in kripke.states if s not in good]
    index = {s: i for i, s in enumerate(kripke.states)}
    edges = [(index[a], index[b]) for a, succ in checker.succ.items() for b in succ]
    init = [index[s] for s in checker.initial]
    bad_idx = [index[s] for s in bad]

    result = BMCResult(prop, "safe_bounded", "", bad_states=bad, completeness_threshold=ct, max_bound=bound)
    for k in range(bound + 1):
        s = [z3.Int(f"s_{i}") for i in range(k + 1)]
        solver = z3.Solver()
        solver.add(*[z3.And(v >= 0, v < len(kripke.states)) for v in s])
        solver.add(z3.Or([s[0] == i for i in init]))
        for i in range(k):
            solver.add(z3.Or([z3.And(s[i] == a, s[i + 1] == b) for a, b in edges]))
        solver.add(z3.Or([z3.Or([v == b for b in bad_idx]) for v in s]) if bad_idx else z3.BoolVal(False))
        t0 = time.perf_counter()
        verdict = solver.check()
        result.steps.append(BMCStep(k, str(verdict), time.perf_counter() - t0))
        if verdict == z3.sat:
            model = solver.model()
            trace = [kripke.states[model.eval(v).as_long()] for v in s]
            first_bad = next(i for i, st in enumerate(trace) if st in bad)
            result.status = "unsafe"
            result.counterexample = trace[: first_bad + 1]
            result.violation_depth = first_bad
            result.details = (
                f"VI PHẠM tại độ sâu k={first_bad}: trạng thái '{trace[first_bad]}' không thỏa {phi}.\n"
                f"Phản ví dụ: {' -> '.join(result.counterexample)}"
            )
            return result

    if bound >= ct:
        result.status = "safe_complete"
        result.details = f"AN TOÀN: không có vi phạm với mọi k ≤ {bound} và đã đạt completeness threshold CT={ct}."
    else:
        result.details = (
            f"AN TOÀN ĐẾN ĐỘ SÂU k={bound}, CHƯA đạt completeness threshold CT={ct}: "
            "không loại trừ được vi phạm ở độ sâu lớn hơn."
        )
    return result


def bmc_properties(kripke: KripkeStructure, safety_properties: list[str],
                   mutual_exclusions: list[dict[str, str]] | None = None,
                   max_bound: int | None = None) -> list[BMCResult]:
    """Run BMC on every AG(propositional) property plus each mutual-exclusion pair."""
    props = []
    for p in safety_properties:
        try:
            safety_body(p)
            props.append(p)
        except CTLSyntaxError:
            continue
    for pair in mutual_exclusions or []:
        props.append(f"AG(!({pair['atom1']} & {pair['atom2']}))")
    return [bmc_check(kripke, p, max_bound) for p in dict.fromkeys(props)]
