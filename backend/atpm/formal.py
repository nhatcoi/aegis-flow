"""Finite-state exploration and incremental safety BMC (not arbitrary CTL/LTL)."""
import itertools
import json
import threading
import time
from collections import deque

import z3

from .engine import TransitionError, initial_state, step, violations
from .specification import spec_hash

FORMAL_LOCK = threading.Lock()


def input_combinations(spec):
    names = list(spec["inputs"])
    for values in itertools.product(*(spec["inputs"][name]["values"] for name in names)):
        yield dict(zip(names, values))


def explore(spec, limit=256):
    first = initial_state(spec)
    key = lambda state: json.dumps(state, sort_keys=True)
    nodes = [{"id": 0, "state": first, "violations": violations(spec, first)}]
    known = {key(first): 0}
    queue = deque([first])
    edges = []
    complete = True
    combinations = list(input_combinations(spec))
    while queue:
        state = queue.popleft()
        source = known[key(state)]
        unique = set()
        for transition in spec["transitions"]:
            for inputs in combinations:
                try:
                    updated = step(spec, state, transition["event"], inputs)
                except TransitionError:
                    continue
                target_key = key(updated)
                if target_key not in known:
                    if len(nodes) >= limit:
                        complete = False
                        continue
                    known[target_key] = len(nodes)
                    nodes.append({"id": len(nodes), "state": updated, "violations": violations(spec, updated)})
                    queue.append(updated)
                target = known[target_key]
                if (target, transition["event"]) not in unique:
                    unique.add((target, transition["event"]))
                    edges.append({"source": source, "target": target, "event": transition["event"],
                                  "inputs": inputs})
        # Explicit stuttering makes the relation total; it makes no liveness claim.
        edges.append({"source": source, "target": source, "event": "stutter", "inputs": {}})
    return {"nodes": nodes, "edges": edges, "complete": complete, "limit": limit,
            "spec_hash": spec_hash(spec)}


def symbol(name, definition):
    kind = type(definition["initial"])
    return z3.Bool(name) if kind is bool else z3.Int(name) if kind is int else z3.String(name)


def literal(value):
    if type(value) is bool:
        return z3.BoolVal(value)
    if type(value) is int:
        return z3.IntVal(value)
    return z3.StringVal(value)


def encode(expr, state, inputs):
    if isinstance(expr, str) and expr.startswith("$"):
        name = expr[1:]
        return inputs[name[6:]] if name.startswith("input.") else state[name]
    if not isinstance(expr, dict):
        return literal(expr)
    op, args = next(iter(expr.items()))
    values = [encode(arg, state, inputs) for arg in args]
    if op == "and":
        return z3.And(*values)
    if op == "or":
        return z3.Or(*values)
    if op == "not":
        return z3.Not(values[0])
    if op == "implies":
        return z3.Implies(*values)
    a, b = values
    return {"eq": lambda: a == b, "ne": lambda: a != b, "le": lambda: a <= b,
            "lt": lambda: a < b, "add": lambda: a + b, "sub": lambda: a - b}[op]()


def domain_constraints(symbols, definitions):
    return [z3.Or(*(symbols[key] == literal(value) for value in item["values"]))
            for key, item in definitions.items()]


def transition_formula(spec, before, after, inputs, event):
    alternatives = [z3.And(event == -1, *(after[name] == before[name] for name in before))]
    for index, transition in enumerate(spec["transitions"]):
        updates = dict(transition["effects"], status=transition["to_state"])
        assignments = [after[name] == encode(updates.get(name, f"${name}"), before, inputs)
                       for name in before]
        alternatives.append(z3.And(
            event == index,
            z3.Or(*(before["status"] == status for status in transition["from_states"])),
            encode(transition["guard"], before, inputs), *assignments,
        ))
    return z3.And(*domain_constraints(after, spec["variables"]),
                  *domain_constraints(inputs, spec["inputs"]), z3.Or(*alternatives))


def decoded(model, symbols):
    result = {}
    for name, sym in symbols.items():
        value = model.eval(sym, model_completion=True)
        result[name] = z3.is_true(value) if z3.is_bool(value) else (
            value.as_string() if z3.is_string_value(value) else value.as_long())
    return result


def verify(spec, bound):
    # The default Z3 context is not safe for concurrent use from request threads.
    with FORMAL_LOCK:
        started = time.monotonic()
        solver = z3.Solver()
        states = [{name: symbol(f"s0_{name}", item) for name, item in spec["variables"].items()}]
        solver.add(*(states[0][name] == literal(item["initial"]) for name, item in spec["variables"].items()))
        events, inputs = [], []
        results = {}
        for depth in range(bound + 1):
            if depth:
                states.append({name: symbol(f"s{depth}_{name}", item)
                               for name, item in spec["variables"].items()})
                inputs.append({name: symbol(f"i{depth}_{name}", item)
                               for name, item in spec["inputs"].items()})
                events.append(z3.Int(f"event_{depth}"))
                solver.add(transition_formula(spec, states[-2], states[-1], inputs[-1], events[-1]))
            for prop in spec["properties"]:
                if prop["id"] in results:
                    continue
                remaining = 12 - (time.monotonic() - started)
                if remaining <= 0:
                    results[prop["id"]] = {"id": prop["id"], "label": prop["label"], "verdict": "UNKNOWN",
                                            "reason": "Hết ngân sách 12 giây", "checked_depth": depth - 1}
                    continue
                solver.set(timeout=max(1, min(2000, int(remaining * 1000))))
                solver.push()
                solver.add(z3.Not(encode(prop["expression"], states[-1], {})))
                outcome = solver.check()
                if outcome == z3.sat:
                    model = solver.model()
                    trace = [{"step": 0, "event": "initial", "inputs": {}, "state": decoded(model, states[0])}]
                    for index, event_symbol in enumerate(events):
                        event_index = model.eval(event_symbol).as_long()
                        event = "stutter" if event_index == -1 else spec["transitions"][event_index]["event"]
                        trace.append({"step": index + 1, "event": event,
                                      "inputs": decoded(model, inputs[index]),
                                      "state": decoded(model, states[index + 1])})
                    results[prop["id"]] = {"id": prop["id"], "label": prop["label"],
                                            "verdict": "VIOLATED", "depth": depth, "trace": trace}
                elif outcome == z3.unknown:
                    results[prop["id"]] = {"id": prop["id"], "label": prop["label"], "verdict": "UNKNOWN",
                                            "reason": solver.reason_unknown(), "checked_depth": depth - 1}
                solver.pop()
            if len(results) == len(spec["properties"]):
                break
        return {"spec_hash": spec_hash(spec), "bound": bound, "solver": f"Z3 {z3.get_version_string()}",
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "scope": "Safety BMC; không chứng minh an toàn vô hạn hoặc liveness",
                "results": [results.get(p["id"], {"id": p["id"], "label": p["label"],
                            "verdict": "BOUNDED_SAFE", "checked_depth": bound}) for p in spec["properties"]]}
