"""Static analysis over the specification and over the generated Python artifact.

Two independent layers:

* source level — AST scan of every generated ``.py`` file. It rejects constructs the
  generator must never emit (``eval``, ``exec``, imports that reach the network or the
  filesystem), so a tampered generator cannot smuggle behaviour into an artifact.
* specification level — exhaustive enumeration of the declared finite domains. This
  catches modelling defects that dynamic scenarios miss: an event nobody can fire, a
  status nobody can reach, an invariant that no assignment can break (vacuous), a guard
  no state satisfies, or an effect whose result leaves the declared domain.

Nothing here executes the artifact; :mod:`atpm.testing` does that separately.
"""
import ast
import itertools

from .engine import evaluate, in_domain
from .formal import explore, input_combinations

# Names that must never appear in generated code. The engine copied into the artifact
# uses only ``copy.deepcopy`` plus the json module added by the generator.
FORBIDDEN_CALLS = {"eval", "exec", "compile", "open", "__import__", "input", "breakpoint", "globals"}
FORBIDDEN_IMPORTS = {"socket", "subprocess", "os", "sys", "shutil", "urllib", "http", "requests",
                     "pathlib", "pickle", "importlib", "ctypes", "multiprocessing"}
# Upper bound on domain enumeration so a large spec degrades to SKIP instead of hanging.
BUDGET = 200_000


def state_combinations(spec):
    names = list(spec["variables"])
    for values in itertools.product(*(spec["variables"][name]["values"] for name in names)):
        yield dict(zip(names, values))


def domain_size(spec):
    states = 1
    for item in spec["variables"].values():
        states *= len(item["values"])
    inputs = 1
    for item in spec["inputs"].values():
        inputs *= len(item["values"])
    return states, inputs


def budget_exceeded(spec):
    states, inputs = domain_size(spec)
    return states * inputs * max(1, len(spec["transitions"])) > BUDGET


def scan_source(name, source):
    """Return forbidden constructs found in one generated file."""
    findings = []
    tree = ast.parse(source, filename=name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            findings.append(f"{name}:{node.lineno} gọi {node.func.id}()")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    findings.append(f"{name}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in FORBIDDEN_IMPORTS:
                findings.append(f"{name}:{node.lineno} from {node.module} import ...")
        elif isinstance(node, ast.Attribute) and node.attr in {"system", "popen", "spawn"}:
            findings.append(f"{name}:{node.lineno} truy cập .{node.attr}")
    return findings


def unused_variables(spec):
    """Variables that no guard, effect or property ever reads, and nothing ever writes."""
    read, written = set(), set()

    def walk(expr):
        if isinstance(expr, str) and expr.startswith("$") and not expr.startswith("$input."):
            read.add(expr[1:])
        elif isinstance(expr, dict):
            for arg in next(iter(expr.values())):
                walk(arg)

    for transition in spec["transitions"]:
        walk(transition["guard"])
        for name, expr in transition["effects"].items():
            written.add(name)
            walk(expr)
        written.add("status")
    for prop in spec["properties"]:
        walk(prop["expression"])
    return sorted(name for name in spec["variables"] if name not in read and name not in written)


def vacuous_properties(spec):
    """Invariants that hold for every assignment in the declared domain prove nothing."""
    unbreakable = []
    for prop in spec["properties"]:
        if any(not evaluate(prop["expression"], state, {}) for state in state_combinations(spec)):
            continue
        unbreakable.append(prop["id"])
    return unbreakable


def dead_guards(spec):
    """Transitions whose from_states and guard cannot be satisfied together."""
    dead = []
    combinations = list(input_combinations(spec))
    for transition in spec["transitions"]:
        allowed = set(transition["from_states"])
        live = any(
            evaluate(transition["guard"], state, inputs)
            for state in state_combinations(spec) if state["status"] in allowed
            for inputs in combinations
        )
        if not live:
            dead.append(transition["event"])
    return dead


def domain_escapes(spec):
    """Effects that produce a value outside the declared domain on a state the guard admits.

    Only states satisfying ``from_states`` and the guard are considered, so a spec that
    keeps ``captured_count`` in range through its guard is not reported.
    """
    escapes = []
    combinations = list(input_combinations(spec))
    for transition in spec["transitions"]:
        allowed = set(transition["from_states"])
        for state in state_combinations(spec):
            if state["status"] not in allowed:
                continue
            for inputs in combinations:
                if not evaluate(transition["guard"], state, inputs):
                    continue
                for name, expr in transition["effects"].items():
                    value = evaluate(expr, state, inputs)
                    if not in_domain(value, spec["variables"][name]["values"]):
                        escape = f"{transition['event']}.{name} = {value!r}"
                        if escape not in escapes:
                            escapes.append(escape)
    return escapes


def reachability(spec):
    """Events never enabled and statuses never entered on any reachable path."""
    graph = explore(spec)
    fired = {edge["event"] for edge in graph["edges"]}
    entered = {node["state"]["status"] for node in graph["nodes"]}
    return {
        "unreachable_events": [t["event"] for t in spec["transitions"] if t["event"] not in fired],
        "unreachable_statuses": [s for s in spec["variables"]["status"]["values"] if s not in entered],
        "complete": graph["complete"],
        "node_count": len(graph["nodes"]),
    }


def static_checks(spec, artifact):
    """Run every static check and return one result row per check.

    Rows use the same shape as the dynamic cases in :mod:`atpm.testing`:
    ``{name, group, verdict, reason}`` with verdict PASS, FAIL or SKIP.
    """
    results = []

    def record(name, findings, reason=None):
        if findings:
            results.append({"name": name, "group": "static", "verdict": "FAIL",
                            "reason": reason or ", ".join(findings[:6])})
        else:
            results.append({"name": name, "group": "static", "verdict": "PASS"})

    syntax_errors = []
    forbidden = []
    for filename, source in artifact["files"].items():
        if not filename.endswith(".py"):
            continue
        try:
            forbidden.extend(scan_source(filename, source))
        except SyntaxError as error:
            syntax_errors.append(f"{filename}:{error.lineno} {error.msg}")
    record("Mã Python sinh ra có cú pháp hợp lệ", syntax_errors)
    record("Mã sinh không dùng eval, exec hay I/O ngoài", forbidden)

    embedded = f"SPEC_HASH = {artifact['spec_hash']!r}"
    record("Mã sinh gắn đúng SHA-256 của đặc tả",
           [] if embedded in artifact["files"]["payment_machine.py"] else ["SPEC_HASH không khớp"])

    reach = reachability(spec)
    if not reach["complete"]:
        results.append({"name": "Mọi sự kiện đều có thể kích hoạt", "group": "static", "verdict": "SKIP",
                        "reason": f"Khám phá dừng ở {reach['node_count']} trạng thái, kết luận không đầy đủ"})
        results.append({"name": "Mọi trạng thái khai báo đều đạt tới được", "group": "static",
                        "verdict": "SKIP", "reason": "Khám phá không đầy đủ"})
    else:
        record("Mọi sự kiện đều có thể kích hoạt", reach["unreachable_events"],
               f"Không bao giờ kích hoạt: {', '.join(reach['unreachable_events'])}"
               if reach["unreachable_events"] else None)
        record("Mọi trạng thái khai báo đều đạt tới được", reach["unreachable_statuses"],
               f"Không đạt tới: {', '.join(reach['unreachable_statuses'])}"
               if reach["unreachable_statuses"] else None)

    unused = unused_variables(spec)
    record("Không có biến trạng thái thừa", unused,
           f"Không được đọc hay ghi ở đâu: {', '.join(unused)}" if unused else None)

    if budget_exceeded(spec):
        states, inputs = domain_size(spec)
        reason = f"Miền {states}×{inputs} vượt ngân sách liệt kê {BUDGET}"
        for name in ("Thuộc tính an toàn không hiển nhiên đúng", "Mọi guard đều thỏa mãn được",
                     "Effect luôn nằm trong miền khai báo"):
            results.append({"name": name, "group": "static", "verdict": "SKIP", "reason": reason})
        return results

    vacuous = vacuous_properties(spec)
    record("Thuộc tính an toàn không hiển nhiên đúng", vacuous,
           f"Đúng với mọi tổ hợp giá trị nên không ràng buộc gì: {', '.join(vacuous)}" if vacuous else None)
    dead = dead_guards(spec)
    record("Mọi guard đều thỏa mãn được", dead,
           f"Guard không bao giờ đúng trên from_states: {', '.join(dead)}" if dead else None)
    escapes = domain_escapes(spec)
    record("Effect luôn nằm trong miền khai báo", escapes,
           f"Giá trị ngoài miền: {', '.join(escapes)}" if escapes else None)
    return results
