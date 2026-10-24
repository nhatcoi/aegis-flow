"""Black-box, coverage-guided and concolic fuzzing of generated Python functions (Chương 4).

* Black-box: random int32 inputs mixed with boundary values; no feedback.
* Coverage-guided: hill climbing on line coverage (sys.settrace) — keeps a
  mutated input only when it executes a line never seen before (Chương 4.4).
* Concolic: runs the function concretely while evaluating every branch
  condition symbolically with Z3; each path-condition prefix is negated to
  derive a new input (Chương 4.6, SAGE/KLEE style). Division is treated as an
  implicit branch ``divisor != 0`` so the solver can target the crash.

The oracle is kind-specific: any exception is a crash (CWE-369 for division,
CWE-248 otherwise); for vulnerable ``magic_value`` functions returning True
means the hard-coded bypass was reached (CWE-798). Configured authentication
accepts True only for credentials matching the configured secret. Library
models use a fixed environment and do not analyze authentication timing.
"""
from __future__ import annotations

import ast
import hmac
import itertools
import os
import random
import re
import sys
import time
import traceback
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
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
    traceback: str = ""


def run_oracle(func: Callable, kind: str, args: tuple) -> Outcome:
    try:
        value = func(*args)
    except ZeroDivisionError:
        return Outcome("ZeroDivisionError", "CWE-369", traceback=traceback.format_exc())
    except Exception as e:  # noqa: BLE001 - every uncaught exception is a crash for the oracle
        return Outcome(type(e).__name__, "CWE-248", traceback=traceback.format_exc())
    if kind in {'magic_value', 'configured_auth'} and value is True:
        expected = os.environ.get('WEBHOOK_SECRET', '')
        authorized = kind == 'configured_auth' and bool(expected) and ':'.join(map(str, args)) == expected
        if not authorized:
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
    trials: list[dict[str, Any]] = field(default_factory=list)
    queries: list[dict[str, Any]] = field(default_factory=list)
    seed: int | None = None
    status: str = "not_started"
    stop_reason: str = ""
    solver_timeout_ms: int = 1000
    assumptions: list[str] = field(default_factory=list)
    _covered: set[int] = field(default_factory=set, repr=False)

    @property
    def found(self) -> bool:
        return self.first_hit is not None

    @property
    def unique_findings(self) -> int:
        return len({(t["finding"], t["trace"][-1] if t["trace"] else None)
                    for t in self.trials if t["finding"]})

    def observe(self, func: Callable, kind: str, i: int, args: tuple, **origin) -> dict:
        """Observe execution for evidence; only the coverage strategy uses feedback to select inputs."""
        trace: list[int] = []

        def tracer(frame, event, arg):
            if frame.f_code is func.__code__:
                if event == "line":
                    trace.append(frame.f_lineno)
                return tracer
            return None

        old = sys.gettrace()
        started = time.perf_counter()
        sys.settrace(tracer)
        try:
            out = run_oracle(func, kind, args)
        finally:
            sys.settrace(old)
        self.iterations = i
        self.record(i, args, out)
        covered_before = self._covered.copy()
        trial = {
            "iteration": i, "input": list(args), "trace": trace, "lines": sorted(set(trace)),
            "new_lines": sorted(set(trace) - covered_before), "finding": out.finding,
            "cwe": out.cwe, "value": out.value, "traceback": out.traceback,
            "seconds": time.perf_counter() - started, **origin,
        }
        self.trials.append(trial)
        self._covered.update(trace)
        self.lines_covered = len(self._covered)
        return trial

    def finish(self, reason: str) -> None:
        self.stop_reason = reason
        self.status = "found" if self.found else (
            "inconclusive" if reason in {"unsupported", "solver_unknown"} else "no_finding")
        self.events.append(f"Kết thúc: {reason}; {self.iterations}/{self.budget} lần thực thi; "
                           f"{self.hits} hit, {self.unique_findings} nhóm lỗi.")

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
    trials: list[dict[str, Any]] = field(default_factory=list)
    budget: int = 0
    seed: int = 1
    stop_reason: str = ""

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
    res.seed = seed
    t0 = time.perf_counter()
    for i in range(1, budget + 1):
        args = tuple(_random_int(rng) for _ in range(_arity(func)))
        res.observe(func, kind, i, args, origin="random_int32 / boundary")
        if stop_on_hit and res.found:
            break
    res.seconds = time.perf_counter() - t0
    res.finish("first_hit" if stop_on_hit and res.found else "budget_exhausted")
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


def _mutate(rng: random.Random, args: tuple, details: dict | None = None) -> tuple:
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
    if details is not None:
        details.update(operator=["bit_flip", "arithmetic", "boundary", "random_replace", "parameter_copy"][op],
                       parameter=i, before=args[i], after=new[i])
    return tuple(new)


def coverage_guided_fuzz(func: Callable, kind: str, budget: int = 1000, seed: int = 1, *,
                         name: str = "", version: str = "v0", stop_on_hit: bool = False) -> FuzzResult:
    rng = random.Random(seed)
    res = FuzzResult(name or func.__name__, version, "coverage", budget)
    res.seed = seed
    corpus = [(tuple(SEED_VALUE for _ in range(_arity(func))), None)]
    seen: set[int] = set()
    t0 = time.perf_counter()
    for i in range(1, budget + 1):
        base, parent = corpus[0] if i == 1 else rng.choice(corpus)
        mutation: dict = {}
        args = base if i == 1 else _mutate(rng, base, mutation)
        trial = res.observe(func, kind, i, args, origin="seed" if i == 1 else "mutation",
                            parent_iteration=parent, parent_input=list(base), mutation=mutation)
        lines = set(trial["lines"])
        trial["kept_in_corpus"] = bool(lines - seen)
        if lines - seen:
            seen |= lines
            corpus.append((args, i))
            res.events.append(f"lần {i}: coverage mới {len(seen)} dòng với input {args}")
        trial["corpus_size"] = len(corpus)
        if stop_on_hit and res.found:
            break
    res.seconds = time.perf_counter() - t0
    res.lines_covered = len(seen)
    res.finish("first_hit" if stop_on_hit and res.found else "budget_exhausted")
    return res


# ---------------------------------------------------------------------------
# Concolic
# ---------------------------------------------------------------------------
class _Concolic:
    """Concrete + symbolic interpreter for the restricted function subset."""

    def __init__(self, fdef: ast.FunctionDef, namespace: dict):
        self.fdef = fdef
        self.unsupported = False
        self.params = [a.arg for a in fdef.args.args]
        self.environment = dict(os.environ)
        self.assumptions: list[str] = []
        self.globals = {'__builtins__': {'str': str}}
        if namespace.get('os') is os:
            self.globals['os'] = SimpleNamespace(environ=self.environment)
        if namespace.get('hmac') is hmac:
            self.globals['hmac'] = hmac

    def run(self, args: tuple) -> list[Any]:
        """Return the path condition (list of Z3 bools) followed by `args`."""
        self.conc = dict(zip(self.params, args))
        self.sym: dict[str, Any] = {p: z3.Int(p) for p in self.params}
        self.path: list[Any] = []
        self.branches: list[dict] = []
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
                    value = self._eval(st.value)
                    cond = self._sym(st.value)
                    if z3.is_bool(cond) and not isinstance(st.value, ast.Constant):
                        self.path.append(cond if value else z3.Not(cond))
                        self.branches.append({'line': st.lineno, 'condition': ast.unparse(st.value),
                                              'taken': bool(value), 'kind': 'return_predicate'})
                raise _Return
            if isinstance(st, ast.If):
                taken = bool(self._eval(st.test))
                cond = self._truth(self._sym(st.test))
                if cond is None:
                    raise _Unsupported
                self.path.append(cond if taken else z3.Not(cond))
                self.branches.append({"line": st.lineno, "condition": ast.unparse(st.test), "taken": taken})
                self._block(st.body if taken else st.orelse)
            elif isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                name = st.targets[0].id
                self.conc[name] = self._eval(st.value)
                self.sym[name] = self._sym(st.value)
            else:
                raise _Unsupported

    def _eval(self, node):
        calls = [child for child in ast.walk(node) if isinstance(child, ast.Call)]
        if calls and (self._sym(node) is None or any(self._sym(call) is None for call in calls)):
            raise _Unsupported
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.FloorDiv, ast.Div, ast.Mod)):
            divisor = self._sym(node.right)
            if divisor is not None:
                self.path.append(divisor != 0 if self._eval_plain(node.right) != 0 else divisor == 0)
        return self._eval_plain(node)

    def _eval_plain(self, node):
        expr = ast.Expression(body=node)
        return eval(compile(expr, "<concolic>", "eval"), self.globals, dict(self.conc))

    @staticmethod
    def _truth(value):
        if z3.is_bool(value):
            return value
        if z3.is_arith(value):
            return value != 0
        if z3.is_string(value):
            return z3.Length(value) != 0
        return None

    def _library_call(self, node):
        name = ast.unparse(node.func)
        if name == 'os.environ.get' and 'os' in self.globals:
            if node.keywords or not 1 <= len(node.args) <= 2:
                return None
            if not all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args):
                return None
            value = self._eval_plain(node)
            if not isinstance(value, str):
                return None
            assumption = f'os.environ.get({node.args[0].value}): cấu hình cố định trong chiến dịch; không duyệt mọi cấu hình.'
            if assumption not in self.assumptions:
                self.assumptions.append(assumption)
            return z3.StringVal(value)
        if name != 'hmac.compare_digest' or 'hmac' not in self.globals or node.keywords or len(node.args) != 2:
            return None
        template, expected = node.args
        # Exact summary for the generated canonical decimal pair; no cryptography/timing claims.
        if not isinstance(template, ast.JoinedStr) or len(template.values) != 3:
            return None
        left, sep, right = template.values
        if not (isinstance(sep, ast.Constant) and sep.value == ':' and
                all(isinstance(v, ast.FormattedValue) and v.conversion == -1 and v.format_spec is None
                    and isinstance(v.value, ast.Name) and v.value.id in self.params for v in (left, right))):
            return None
        fixed = self._sym(expected)
        if not z3.is_string_value(fixed):
            return None
        text = fixed.as_string()
        if not text.isascii():
            return None
        assumption = 'hmac.compare_digest: mô hình kết quả bằng nhau của chuỗi int32:int32; không phân tích timing.'
        if assumption not in self.assumptions:
            self.assumptions.append(assumption)
        if not re.fullmatch(r'-?(?:0|[1-9][0-9]*):-?(?:0|[1-9][0-9]*)', text):
            return z3.BoolVal(False)
        a, b = text.split(':')
        # Noncanonical -0, enormous integers and values outside int32 cannot match an int32 f-string.
        if len(a) > 11 or len(b) > 11:
            return z3.BoolVal(False)
        x, y = int(a), int(b)
        if str(x) != a or str(y) != b:
            return z3.BoolVal(False)
        return z3.And(self.sym[left.value.id] == x, self.sym[right.value.id] == y)

    def _sym(self, node):
        from .arithmetic_z3 import _ast_to_z3
        try:
            if isinstance(node, ast.Call):
                return self._library_call(node)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return z3.StringVal(node.value)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                truth = self._truth(self._sym(node.operand))
                return z3.Not(truth) if truth is not None else None
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
    solver_timeout_ms: int = 1000,
) -> FuzzResult:
    if search_strategy not in {"bfs", "dfs"}:
        raise ValueError("Concolic search must be bfs or dfs")
    if solver_timeout_ms < 1:
        raise ValueError("Solver timeout must be positive")
    fdef = next(n for n in ast.walk(ast.parse(code)) if isinstance(n, ast.FunctionDef))
    engine = _Concolic(fdef, func.__globals__)
    res = FuzzResult(name or func.__name__, version, "concolic", budget,
                     search_strategy=search_strategy, solver_timeout_ms=solver_timeout_ms)
    worklist = deque([(tuple(SEED_VALUE for _ in engine.params), None, None)])
    explored: set[str] = set()
    t0 = time.perf_counter()
    reason = "worklist_exhausted"
    unknown_seen = False
    while worklist and res.iterations < budget:
        args, parent, query_id = worklist.pop() if search_strategy == "dfs" else worklist.popleft()
        i = res.iterations + 1
        trial = res.observe(func, kind, i, args, origin="solver" if query_id else "seed",
                            parent_iteration=parent, query_id=query_id)
        path = engine.run(args)
        res.assumptions = list(engine.assumptions)
        trial.update(path_condition=[str(c) for c in path], branches=engine.branches,
                     pending_inputs=len(worklist), symbolic_supported=not engine.unsupported)
        res.events.append(f"lần {i} ({search_strategy.upper()}): input {args}, "
                          f"path condition: {trial['path_condition']}")
        if engine.unsupported:
            res.events.append("Không mô hình hóa được cú pháp/thư viện của đường này; dừng concolic.")
            reason = "unsupported"
            break
        if stop_on_hit and res.found:
            reason = "first_hit"
            break
        for k in range(len(path)):
            query = path[:k] + [z3.Not(path[k])]
            key = str(query)
            if key in explored:
                continue
            explored.add(key)
            solver = z3.Solver()
            solver.set(timeout=solver_timeout_ms)
            for param in engine.params:
                value = z3.Int(param)
                solver.add(value >= INT32_MIN, value <= INT32_MAX)
            solver.add(*query)
            started = time.perf_counter()
            status = solver.check()
            q = {"id": f"q{len(res.queries) + 1}", "iteration": i, "negated_branch": k,
                 "original_path": trial["path_condition"], "constraints": [str(c) for c in query],
                 "smt2": solver.to_smt2(), "status": str(status), "model": None,
                 "generated_input": None, "seconds": time.perf_counter() - started,
                 "reason_unknown": solver.reason_unknown() if status == z3.unknown else ""}
            if status == z3.sat:
                model = solver.model()
                values = tuple(model.eval(z3.Int(p), model_completion=True).as_long() for p in engine.params)
                q.update(model=dict(zip(engine.params, values)), generated_input=list(values))
                worklist.append((values, i, q["id"]))
            elif status == z3.unknown:
                unknown_seen = True
            res.queries.append(q)
            res.events.append(f"{q['id']}: phủ định nhánh {k + 1} → {status}; model={q['model']}")
        trial["pending_inputs"] = len(worklist)
    else:
        if worklist:
            reason = "budget_exhausted"
        elif unknown_seen:
            reason = "solver_unknown"
    res.seconds = time.perf_counter() - t0
    res.finish(reason)
    return res


# ---------------------------------------------------------------------------
# Campaign over a generated function
# ---------------------------------------------------------------------------
def fuzz_generated(
    gf: GeneratedFunction,
    budget: int = 2000,
    seed: int = 1,
    concolic_strategy: str = "bfs",
    solver_timeout_ms: int = 1000,
) -> list[FuzzResult]:
    """Run the three strategies on v0 and v1 of a generated Python function."""
    if gf.language != "python":
        return []
    results = []
    for version, code in (("v0", gf.code_vulnerable), ("v1", gf.code_safe)):
        kind = generated_oracle_kind(gf, version)
        func = load_function(code, gf.spec.name)
        opts = {"name": gf.spec.name, "version": version}
        results.append(blackbox_fuzz(func, kind, budget, seed, **opts))
        results.append(coverage_guided_fuzz(func, kind, budget, seed, **opts))
        results.append(concolic_fuzz(func, code, kind, budget, search_strategy=concolic_strategy,
                                     solver_timeout_ms=solver_timeout_ms, **opts))
    for result in results:
        result.seed = seed
    return results


def generated_oracle_kind(gf: GeneratedFunction, version: str) -> str:
    """A successful configured authentication is not the hardcoded bypass oracle."""
    code = gf.code_vulnerable if version == 'v0' else gf.code_safe
    if gf.spec.kind.lower() == 'magic_value' and code == gf.code_safe:
        return 'configured_auth'
    return gf.spec.kind.lower()


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
    if strategy.lower() not in {"bfs", "dfs", "coverage", "random_walk"}:
        raise ValueError("Unknown state exploration strategy")
    if max_depth < 0 or budget < 0:
        raise ValueError("Depth and budget must be non-negative")
    t0 = time.perf_counter()
    rng = random.Random(seed)
    states = list(sm.states)
    initial = [s for s in getattr(sm, "initial", []) if s in states] or (states[:1] if states else [])
    labeling = getattr(sm, "labeling", {})
    transitions = [list(t) for t in getattr(sm, "transitions", [])]

    succ: dict[str, list[str]] = {s: [] for s in states}
    for t in transitions:
        if len(t) >= 2:
            src, dst = t[0], t[1]
            if src in succ and dst in states:
                succ[src].append(dst)

    strat = strategy.lower()
    res = StateFuzzResult(name or getattr(sm, "name", "StateMachine"), version, strat, max_depth, [], [], 0.0, 0.0)

    res.budget, res.seed = budget, seed
    discovered_states: set[str] = set()
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
            "double_capture",
            "unpaid_shipping",
        }
        if bad_labels:
            tag = min(bad_labels)
            cwe = "CWE-667" if "conflict" in tag or "lock" in tag or {"webhook_locked", "recon_locked"} <= labels else "CWE-693"
            return StateCrash(
                kind="invariant_violation",
                state=curr,
                path=path,
                message=f"Phát hiện nhãn vi phạm '{tag}' tại trạng thái {curr}",
                cwe=cwe,
            )
        if ({"shipped", "paid"}.intersection(labels) == {"shipped"}
                or {"webhook_locked", "recon_locked"} <= labels):
            return StateCrash("invariant_violation", curr, path,
                              "Vi phạm shipped → paid hoặc loại trừ khóa webhook/đối soát",
                              "CWE-667" if "webhook_locked" in labels else "CWE-693")
        if (known_deadlocks and curr in known_deadlocks) or (
            len(succ.get(curr, [])) == 0
            and curr.upper() not in {"SUCCEEDED", "FAILED", "REFUNDED", "TERMINATED", "END", "DONE"}
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
            res.events.append(f"[{strat.upper()}] Crash: {c.message} sau {len(c.path) - 1} chuyển tiếp: {' -> '.join(c.path)}")

    def assess(path: list[str]) -> None:
        previous_states = len(discovered_states)
        previous_edges = len(fired_transitions)
        discovered_states.update(path)
        fired_transitions.update(itertools.pairwise(path))
        findings = []
        for end in range(1, len(path) + 1):
            crash = check_crash(path[:end])
            if crash:
                record_crash(crash)
                findings.append({"state": crash.state, "kind": crash.kind, "cwe": crash.cwe})
        res.trials.append({"iteration": paths_count, "path": list(path), "depth": len(path) - 1,
                           "new_states": len(discovered_states) - previous_states,
                           "new_transitions": len(fired_transitions) - previous_edges,
                           "states_evaluated": len(discovered_states),
                           "transitions_evaluated": len(fired_transitions), "findings": findings})

    init_paths = [list(p) for p in seed_paths] if seed_paths else [[s] for s in initial]
    for path in init_paths:
        if (not path or path[0] not in initial or len(path) - 1 > max_depth
                or any(state not in states for state in path)
                or any(dst not in succ[src] for src, dst in itertools.pairwise(path))):
            raise ValueError("Seed path must be an initial, valid path within the depth bound")

    if strat == "bfs":
        worklist = deque(init_paths)
        while worklist and paths_count < budget:
            path = worklist.popleft()
            paths_count += 1
            curr = path[-1]
            assess(path)
            if len(path) - 1 < max_depth:
                for nxt in succ.get(curr, []):
                    if path.count(nxt) < 2:
                        worklist.append(path + [nxt])

    elif strat == "dfs":
        worklist_stack = list(init_paths)
        while worklist_stack and paths_count < budget:
            path = worklist_stack.pop()
            paths_count += 1
            curr = path[-1]
            assess(path)
            if len(path) - 1 < max_depth:
                for nxt in reversed(succ.get(curr, [])):
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
                if len(path) - 1 >= max_depth:
                    break
                curr = path[-1]
                nxts = succ.get(curr, [])
                if not nxts:
                    break
                nxt = rng.choice(nxts)
                path.append(nxt)
                if path.count(nxt) >= 3:
                    break

            assess(path)

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

    unique_trans = {tuple(t[:2]) for t in transitions if len(t) >= 2}
    res.states_discovered = sorted(discovered_states)
    res.transitions_fired = [list(t) for t in sorted(fired_transitions)]
    res.state_coverage = len(discovered_states) / len(states) if states else 0.0
    res.transition_coverage = len(fired_transitions) / len(unique_trans) if unique_trans else 0.0
    res.crashes = crashes
    res.paths_explored = paths_count
    res.stop_reason = "budget_exhausted" if paths_count >= budget else "bounded_exploration_complete"
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

