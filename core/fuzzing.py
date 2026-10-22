"""Black-box, coverage-guided and concolic fuzzing of generated Python functions (Chương 4).

* Black-box: random int32 inputs mixed with boundary values; no feedback.
* Coverage-guided: hill climbing on line coverage (sys.settrace) — keeps a
  mutated input only when it executes a line never seen before (Chương 4.4).
* Concolic: runs the function concretely while evaluating every branch
  condition symbolically with Z3; each path-condition prefix is negated to
  derive a new input (Chương 4.6, SAGE/KLEE style). Division is treated as an
  implicit branch ``divisor != 0`` so the solver can target the crash.

The oracle is kind-specific: any exception is a crash (CWE-369 for division,
CWE-248 otherwise); for ``magic_value`` functions returning True means the
hard-coded bypass was reached (CWE-798).
"""
from __future__ import annotations

import ast
import itertools
import random
import sys
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import z3

from .arithmetic_z3 import INT32_MAX, INT32_MIN
from .codegen import GeneratedFunction

SEED_VALUE = 1  # initial corpus is (1, 1, ...): a benign input, so crashes must be discovered
BOUNDARY = [0, 1, -1, 2, INT32_MAX, INT32_MIN, INT32_MAX - 1, INT32_MIN + 1, 255, 256, 65535, 65536]

ALLOWED_NODES = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.If, ast.Compare, ast.BinOp,
    ast.BoolOp, ast.UnaryOp, ast.Name, ast.Load, ast.Store, ast.Constant, ast.Assign, ast.Expr, ast.Call,
    ast.Attribute, ast.Import, ast.alias, ast.JoinedStr, ast.FormattedValue, ast.operator, ast.cmpop,
    ast.boolop, ast.unaryop,
)
ALLOWED_IMPORTS = {"hmac", "os"}
ALLOWED_ATTRS = {"environ", "get", "compare_digest"}


class UnsafeCodeError(ValueError):
    pass


def load_function(code: str, name: str) -> Callable[..., Any]:
    """Compile generated code after checking it only uses a small, side-effect free subset of Python."""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise UnsafeCodeError(f"Cú pháp không được phép: {type(node).__name__}")
        if isinstance(node, ast.Import) and any(a.name not in ALLOWED_IMPORTS for a in node.names):
            raise UnsafeCodeError("Import không được phép")
        if isinstance(node, ast.Attribute) and node.attr not in ALLOWED_ATTRS:
            raise UnsafeCodeError(f"Thuộc tính không được phép: {node.attr}")

    def guarded_import(mod, *args, **kwargs):
        if mod not in ALLOWED_IMPORTS:
            raise ImportError(mod)
        return __import__(mod, *args, **kwargs)

    namespace: dict[str, Any] = {"__builtins__": {"__import__": guarded_import, "str": str}}
    exec(compile(tree, f"<generated {name}>", "exec"), namespace)  # noqa: S102 - AST checked above
    return namespace[name]


# ---------------------------------------------------------------------------
# Oracle and results
# ---------------------------------------------------------------------------
@dataclass
class Outcome:
    finding: str | None  # e.g. "ZeroDivisionError", "bypass", None
    cwe: str | None
    value: Any = None


def run_oracle(func: Callable, kind: str, args: tuple) -> Outcome:
    try:
        value = func(*args)
    except ZeroDivisionError:
        return Outcome("ZeroDivisionError", "CWE-369")
    except Exception as e:  # noqa: BLE001 - every uncaught exception is a crash for the oracle
        return Outcome(type(e).__name__, "CWE-248")
    if kind == "magic_value" and value is True:
        return Outcome("bypass", "CWE-798", value)
    return Outcome(None, None, value)


@dataclass
class FuzzResult:
    function: str
    version: str
    strategy: str  # "blackbox" | "coverage" | "concolic"
    budget: int
    iterations: int = 0
    hits: int = 0
    first_hit: int | None = None
    first_input: tuple | None = None
    finding: str | None = None
    cwe: str | None = None
    seconds: float = 0.0
    lines_covered: int = 0
    search_strategy: str = "none"  # "bfs" | "dfs" | "none"
    events: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.first_hit is not None

    def record(self, i: int, args: tuple, out: Outcome) -> None:
        if out.finding is None:
            return
        self.hits += 1
        if self.first_hit is None:
            self.first_hit, self.first_input = i, args
            self.finding, self.cwe = out.finding, out.cwe
            self.events.append(f"lần {i}: {out.finding} với input {args}")


@dataclass
class StateCrash:
    kind: str  # "deadlock" | "invariant_violation" | "illegal_transition"
    state: str
    path: list[str]
    message: str
    cwe: str = "CWE-833"


@dataclass
class StateFuzzResult:
    name: str
    version: str
    strategy: str  # "bfs" | "dfs" | "coverage" | "random_walk"
    max_depth: int
    states_discovered: list[str]
    transitions_fired: list[list[str]]
    state_coverage: float
    transition_coverage: float
    crashes: list[StateCrash] = field(default_factory=list)
    paths_explored: int = 0
    seconds: float = 0.0
    events: list[str] = field(default_factory=list)

    @property
    def has_crash(self) -> bool:
        return len(self.crashes) > 0


def _random_int(rng: random.Random) -> int:
    if rng.random() < 0.3:
        return rng.choice(BOUNDARY)
    return rng.randint(INT32_MIN, INT32_MAX)


def _arity(func: Callable) -> int:
    return func.__code__.co_argcount


# ---------------------------------------------------------------------------
# Black-box
# ---------------------------------------------------------------------------
def blackbox_fuzz(func: Callable, kind: str, budget: int = 1000, seed: int = 1, *,
                  name: str = "", version: str = "v0", stop_on_hit: bool = False) -> FuzzResult:
    rng = random.Random(seed)
    res = FuzzResult(name or func.__name__, version, "blackbox", budget)
    t0 = time.perf_counter()
    for i in range(1, budget + 1):
        args = tuple(_random_int(rng) for _ in range(_arity(func)))
        res.iterations = i
        res.record(i, args, run_oracle(func, kind, args))
        if stop_on_hit and res.found:
            break
    res.seconds = time.perf_counter() - t0
    return res


# ---------------------------------------------------------------------------
# Coverage-guided (hill climbing on line coverage)
# ---------------------------------------------------------------------------
def _covered_lines(func: Callable, args: tuple, kind: str) -> tuple[set[int], Outcome]:
    lines: set[int] = set()
    code = func.__code__

    def tracer(frame, event, arg):
        if frame.f_code is code:
            if event == "line":
                lines.add(frame.f_lineno)
            return tracer
        return None

    old = sys.gettrace()
    sys.settrace(tracer)
    try:
        out = run_oracle(func, kind, args)
    finally:
        sys.settrace(old)
    return lines, out


def _mutate(rng: random.Random, args: tuple) -> tuple:
    new = list(args)
    i = rng.randrange(len(new))
    op = rng.randrange(5)
    if op == 0:
        new[i] = new[i] ^ (1 << rng.randrange(31))  # bit flip
    elif op == 1:
        new[i] = new[i] + rng.randint(-16, 16)  # arithmetic
    elif op == 2:
        new[i] = rng.choice(BOUNDARY)  # interesting value
    elif op == 3:
        new[i] = rng.randint(INT32_MIN, INT32_MAX)  # havoc
    else:
        j = rng.randrange(len(new))
        new[i] = new[j]  # splice between parameters
    new[i] = max(INT32_MIN, min(INT32_MAX, new[i]))
    return tuple(new)


def coverage_guided_fuzz(func: Callable, kind: str, budget: int = 1000, seed: int = 1, *,
                         name: str = "", version: str = "v0", stop_on_hit: bool = False) -> FuzzResult:
    rng = random.Random(seed)
    res = FuzzResult(name or func.__name__, version, "coverage", budget)
    corpus = [tuple(SEED_VALUE for _ in range(_arity(func)))]
    seen: set[int] = set()
    t0 = time.perf_counter()
    for i in range(1, budget + 1):
        args = corpus[0] if i == 1 else _mutate(rng, rng.choice(corpus))
        lines, out = _covered_lines(func, args, kind)
        res.iterations = i
        res.record(i, args, out)
        if lines - seen:
            seen |= lines
            corpus.append(args)
            res.events.append(f"lần {i}: coverage mới {len(seen)} dòng với input {args}")
        if stop_on_hit and res.found:
            break
    res.seconds = time.perf_counter() - t0
    res.lines_covered = len(seen)
    return res


# ---------------------------------------------------------------------------
# Concolic
# ---------------------------------------------------------------------------
class _Concolic:
    """Concrete + symbolic interpreter for the restricted function subset."""

    def __init__(self, fdef: ast.FunctionDef):
        self.fdef = fdef
        self.unsupported = False
        self.params = [a.arg for a in fdef.args.args]

    def run(self, args: tuple) -> list[Any]:
        """Return the path condition (list of Z3 bools) followed by `args`."""
        self.conc = dict(zip(self.params, args))
        self.sym: dict[str, Any] = {p: z3.Int(p) for p in self.params}
        self.path: list[Any] = []
        self.unsupported = False
        try:
            self._block(self.fdef.body)
        except _Return:
            pass
        except (_Unsupported, NameError):
            self.unsupported = True
        except Exception:  # noqa: BLE001, S110 - concrete crash ends the path; constraints so far are kept
            pass
        return self.path

    def _block(self, stmts):
        for st in stmts:
            if isinstance(st, ast.Return):
                if st.value is not None:
                    self._eval(st.value)
                raise _Return
            if isinstance(st, ast.If):
                taken = bool(self._eval(st.test))
                cond = self._sym(st.test)
                if cond is not None:
                    self.path.append(cond if taken else z3.Not(cond))
                self._block(st.body if taken else st.orelse)
            elif isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                name = st.targets[0].id
                self.conc[name] = self._eval(st.value)
                self.sym[name] = self._sym(st.value)
            else:
                raise _Unsupported

    def _eval(self, node):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.FloorDiv, ast.Div, ast.Mod)):
            divisor = self._sym(node.right)
            if divisor is not None:
                self.path.append(divisor != 0 if self._eval_plain(node.right) != 0 else divisor == 0)
        return self._eval_plain(node)

    def _eval_plain(self, node):
        expr = ast.Expression(body=node)
        return eval(compile(expr, "<concolic>", "eval"), {"__builtins__": {}}, dict(self.conc))

    def _sym(self, node):
        from .arithmetic_z3 import _ast_to_z3
        try:
            return _ast_to_z3(node, {k: v for k, v in self.sym.items() if v is not None})
        except Exception:  # noqa: BLE001 - unsupported expression stays concrete
            return None


class _Return(Exception):
    pass


class _Unsupported(Exception):
    pass


def concolic_fuzz(
    func: Callable,
    code: str,
    kind: str,
    budget: int = 1000,
    *,
    name: str = "",
    version: str = "v0",
    stop_on_hit: bool = False,
    search_strategy: str = "bfs",
) -> FuzzResult:
    fdef = next(n for n in ast.walk(ast.parse(code)) if isinstance(n, ast.FunctionDef))
    engine = _Concolic(fdef)
    strategy_label = "concolic"
    res = FuzzResult(name or func.__name__, version, strategy_label, budget, search_strategy=search_strategy)
    worklist = [tuple(SEED_VALUE for _ in engine.params)]
    explored: set[str] = set()
    t0 = time.perf_counter()
    i = 0
    is_dfs = search_strategy.lower() == "dfs"
    while worklist and i < budget:
        args = worklist.pop() if is_dfs else worklist.pop(0)
        i += 1
        res.iterations = i
        res.record(i, args, run_oracle(func, kind, args))
        if stop_on_hit and res.found:
            break
        path = engine.run(args)
        res.events.append(f"lần {i} ({search_strategy.upper()}): input {args}, path condition: {[str(c) for c in path]}")
        if engine.unsupported:
            res.events.append(
                "Hàm gọi thư viện/môi trường ngoài (os.environ, hmac) mà engine không mô hình hóa "
                "được — concolic dừng (giới hạn environment modeling, Ch.4.6)."
            )
        for k in range(len(path)):
            query = path[:k] + [z3.Not(path[k])]
            key = str(query)
            if key in explored:
                continue
            explored.add(key)
            solver = z3.Solver()
            solver.add(*[z3.And(v >= INT32_MIN, v <= INT32_MAX) for v in engine.sym.values()
                         if isinstance(v, z3.ArithRef) and z3.is_const(v)])
            solver.add(*query)
            if solver.check() == z3.sat:
                m = solver.model()
                worklist.append(tuple(m.eval(z3.Int(p), model_completion=True).as_long() for p in engine.params))
    res.seconds = time.perf_counter() - t0
    return res


# ---------------------------------------------------------------------------
# Campaign over a generated function
# ---------------------------------------------------------------------------
def fuzz_generated(
    gf: GeneratedFunction,
    budget: int = 2000,
    seed: int = 1,
    concolic_strategy: str = "bfs",
) -> list[FuzzResult]:
    """Run the three strategies on v0 and v1 of a generated Python function."""
    if gf.language != "python":
        return []
    kind = gf.spec.kind.lower()
    results = []
    for version, code in (("v0", gf.code_vulnerable), ("v1", gf.code_safe)):
        func = load_function(code, gf.spec.name)
        opts = {"name": gf.spec.name, "version": version}
        results.append(blackbox_fuzz(func, kind, budget, seed, **opts))
        results.append(coverage_guided_fuzz(func, kind, budget, seed, **opts))
        results.append(concolic_fuzz(func, code, kind, budget, search_strategy=concolic_strategy, **opts))
    return results


# ---------------------------------------------------------------------------
# State Machine Fuzzing (Stateful Sequence Fuzzer with BFS / DFS / Coverage)
# ---------------------------------------------------------------------------
def state_fuzz(
    sm: Any,
    strategy: str = "bfs",
    max_depth: int = 10,
    budget: int = 300,
    seed: int = 1,
    *,
    name: str = "",
    version: str = "v0",
    seed_paths: list[list[str]] | None = None,
    known_deadlocks: set[str] | None = None,
) -> StateFuzzResult:
    """Fuzz the state machine by generating state transition sequences (Chương 4).

    Strategies:
    * 'bfs': Level-by-level breadth-first search of state paths up to max_depth.
    * 'dfs': Depth-first exploration of state paths up to max_depth.
    * 'coverage': Coverage-guided state sequence generation: mutates paths from seed
      sequences, saving any path that visits a new state or fires a new transition.
    * 'random_walk': Random walk exploration without feedback.
    """
    t0 = time.perf_counter()
    rng = random.Random(seed)
    states = list(sm.states)
    initial = [s for s in getattr(sm, "initial", []) if s in states] or (states[:1] if states else [])
    labeling = getattr(sm, "labeling", {})
    transitions = [list(t) for t in getattr(sm, "transitions", [])]

    succ: dict[str, list[str]] = {s: [] for s in states}
    for src, dst in transitions:
        if src in succ and dst in states:
            succ[src].append(dst)

    strat = strategy.lower()
    res = StateFuzzResult(name or getattr(sm, "name", "StateMachine"), version, strat, max_depth, [], [], 0.0, 0.0)

    discovered_states: set[str] = set(initial)
    fired_transitions: set[tuple[str, str]] = set()
    crashes: list[StateCrash] = []
    seen_crash_keys: set[tuple[str, str]] = set()
    paths_count = 0

    def check_crash(path: list[str]) -> StateCrash | None:
        curr = path[-1]
        labels = set(labeling.get(curr, []))
        bad_labels = labels & {
            "violation",
            "lock_conflict",
            "deadlock",
            "conflict",
            "shipped_unpaid",
            "duplicate_capture",
        }
        if bad_labels:
            tag = next(iter(bad_labels))
            cwe = "CWE-667" if "conflict" in tag or "lock" in tag else "CWE-693"
            return StateCrash(
                kind="invariant_violation",
                state=curr,
                path=path,
                message=f"Phát hiện nhãn vi phạm '{tag}' tại trạng thái {curr}",
                cwe=cwe,
            )
        curr_lower = curr.lower()
        if "unpaid" in curr_lower or "conflict" in curr_lower or "duplicate" in curr_lower:
            return StateCrash(
                kind="invariant_violation",
                state=curr,
                path=path,
                message=f"Rơi vào trạng thái vi phạm an toàn logic: {curr}",
                cwe="CWE-693",
            )
        if (known_deadlocks and curr in known_deadlocks) or (
            len(succ.get(curr, [])) == 0
            and curr not in {"SUCCEEDED", "FAILED", "REFUNDED", "TERMINATED", "END"}
        ):
            return StateCrash(
                kind="deadlock",
                state=curr,
                path=path,
                message=f"Bế tắc (Deadlock): trạng thái {curr} không có chuyển tiếp tiếp theo",
                cwe="CWE-833",
            )
        return None

    def record_crash(c: StateCrash) -> None:
        key = (c.kind, c.state)
        if key not in seen_crash_keys:
            seen_crash_keys.add(key)
            crashes.append(c)
            res.events.append(f"[{strat.upper()}] Crash: {c.message} sau {len(c.path)} bước: {' -> '.join(c.path)}")

    init_paths = [list(p) for p in seed_paths] if seed_paths else [[s] for s in initial]

    if strat == "bfs":
        worklist = deque(init_paths)
        while worklist and paths_count < budget:
            path = worklist.popleft()
            paths_count += 1
            curr = path[-1]
            discovered_states.add(curr)
            crash = check_crash(path)
            if crash:
                record_crash(crash)
            if len(path) < max_depth:
                for nxt in succ.get(curr, []):
                    fired_transitions.add((curr, nxt))
                    discovered_states.add(nxt)
                    if path.count(nxt) < 2:
                        worklist.append(path + [nxt])

    elif strat == "dfs":
        worklist_stack = list(init_paths)
        while worklist_stack and paths_count < budget:
            path = worklist_stack.pop()
            paths_count += 1
            curr = path[-1]
            discovered_states.add(curr)
            crash = check_crash(path)
            if crash:
                record_crash(crash)
            if len(path) < max_depth:
                for nxt in reversed(succ.get(curr, [])):
                    fired_transitions.add((curr, nxt))
                    discovered_states.add(nxt)
                    if path.count(nxt) < 2:
                        worklist_stack.append(path + [nxt])

    elif strat in ("coverage", "random_walk"):
        corpus = list(init_paths)
        seen_states = set(discovered_states)
        seen_trans = set(fired_transitions)
        is_cov = strat == "coverage"

        while corpus and paths_count < budget:
            paths_count += 1
            base = rng.choice(corpus)
            path = list(base)
            steps_to_take = rng.randint(1, 4)
            for _ in range(steps_to_take):
                if len(path) >= max_depth:
                    break
                curr = path[-1]
                nxts = succ.get(curr, [])
                if not nxts:
                    break
                nxt = rng.choice(nxts)
                fired_transitions.add((curr, nxt))
                discovered_states.add(nxt)
                path.append(nxt)
                if path.count(nxt) >= 3:
                    break

            crash = check_crash(path)
            if crash:
                record_crash(crash)

            if is_cov:
                new_states = set(path) - seen_states
                new_trans = set(itertools.pairwise(path)) - seen_trans
                if new_states or new_trans:
                    seen_states |= new_states
                    seen_trans |= new_trans
                    corpus.append(path)
                    res.events.append(
                        f"[COVERAGE] Tăng độ phủ: +{len(new_states)} state, +{len(new_trans)} trans với chuỗi {' -> '.join(path[-3:])}"
                    )
                    if len(corpus) > 50:
                        corpus.pop(1)

    res.states_discovered = sorted(discovered_states)
    res.transitions_fired = [list(t) for t in sorted(fired_transitions)]
    res.state_coverage = len(discovered_states) / len(states) if states else 0.0
    res.transition_coverage = len(fired_transitions) / len(transitions) if transitions else 0.0
    res.crashes = crashes
    res.paths_explored = paths_count
    res.seconds = time.perf_counter() - t0
    return res


def fuzz_state_machine(
    sm: Any,
    budget: int = 300,
    seed: int = 1,
    version: str = "v0",
    max_depth: int = 8,
    known_deadlocks: set[str] | None = None,
) -> list[StateFuzzResult]:
    """Execute BFS, DFS, and Coverage-guided state sequence fuzzing on a state machine."""
    results = []
    for strat in ("bfs", "dfs", "coverage"):
        results.append(
            state_fuzz(
                sm,
                strategy=strat,
                max_depth=max_depth,
                budget=budget,
                seed=seed,
                version=version,
                known_deadlocks=known_deadlocks,
            )
        )
    return results

