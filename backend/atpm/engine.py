"""Portable semantics shared by graph exploration and generated Python artifacts.

No eval, network, or database access. The spec language is a typed JSON AST.
"""
from copy import deepcopy


class TransitionError(ValueError):
    pass


def evaluate(expr, state, inputs):
    if isinstance(expr, str) and expr.startswith("$"):
        name = expr[1:]
        return inputs[name[6:]] if name.startswith("input.") else state[name]
    if not isinstance(expr, dict):
        return expr
    op, args = next(iter(expr.items()))
    values = [evaluate(arg, state, inputs) for arg in args]
    if op == "and":
        return all(values)
    if op == "or":
        return any(values)
    if op == "not":
        return not values[0]
    if op == "implies":
        return not values[0] or values[1]
    a, b = values
    if op == "eq":
        return a == b
    if op == "ne":
        return a != b
    if op == "le":
        return a <= b
    if op == "lt":
        return a < b
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    raise ValueError(f"Unsupported operator: {op}")


def in_domain(value, values):
    return any(type(value) is type(item) and value == item for item in values)


def check_values(values, definitions, label):
    if set(values) != set(definitions):
        raise TransitionError(f"{label}: tên biến không khớp đặc tả")
    for key, definition in definitions.items():
        if not in_domain(values[key], definition["values"]):
            raise TransitionError(f"{label}.{key}: giá trị ngoài miền")


def initial_state(spec):
    return {key: item["initial"] for key, item in spec["variables"].items()}


def step(spec, state, event, inputs=None):
    check_values(state, spec["variables"], "state")
    inputs = dict(inputs or {})
    for name, definition in spec["inputs"].items():
        inputs.setdefault(name, definition["initial"])
    check_values(inputs, spec["inputs"], "input")
    transition = next((item for item in spec["transitions"] if item["event"] == event), None)
    if transition is None:
        raise TransitionError(f"Sự kiện không tồn tại: {event}")
    if state["status"] not in transition["from_states"]:
        raise TransitionError(f"Không thể {event} từ {state['status']}")
    if not evaluate(transition["guard"], state, inputs):
        raise TransitionError("Điều kiện chuyển trạng thái không thỏa mãn")
    updated = deepcopy(state)
    # All assignments read the OLD state (simultaneous, same as the Z3 encoding).
    for name, expr in transition["effects"].items():
        updated[name] = evaluate(expr, state, inputs)
    updated["status"] = transition["to_state"]
    check_values(updated, spec["variables"], "next_state")
    return updated


def violations(spec, state):
    return [p["id"] for p in spec["properties"] if not evaluate(p["expression"], state, {})]


class Monitor:
    """Per-execution synchronous monitor; database wrapper persists state and event IDs."""

    def __init__(self, spec, state=None, seen=None):
        self.spec = spec
        self.state = deepcopy(state) if state is not None else initial_state(spec)
        self.seen = dict(seen or {})

    def process(self, event_id, event, inputs=None, enforce=True):
        normalized = {name: definition["initial"] for name, definition in self.spec["inputs"].items()}
        normalized.update(inputs or {})
        fingerprint = {"event": event, "inputs": normalized}
        before = deepcopy(self.state)
        if event_id in self.seen:
            if self.seen[event_id] != fingerprint:
                return {"verdict": "REJECTED", "reason": "ID sự kiện được dùng lại với nội dung khác",
                        "before": before, "after": before, "violations": []}
            return {"verdict": "DUPLICATE", "reason": "Sự kiện đã xử lý; không áp dụng lần nữa",
                    "before": before, "after": before, "violations": []}
        try:
            candidate = step(self.spec, before, event, normalized)
        except TransitionError as error:
            return {"verdict": "REJECTED", "reason": str(error), "before": before,
                    "after": before, "violations": []}
        broken = violations(self.spec, candidate)
        if broken and enforce:
            return {"verdict": "BLOCKED", "reason": "Monitor chặn trước khi cập nhật trạng thái",
                    "before": before, "after": before, "candidate": candidate, "violations": broken}
        self.state = candidate
        self.seen[event_id] = fingerprint
        return {"verdict": "VIOLATED" if broken else "ACCEPTED", "before": before,
                "after": deepcopy(candidate), "violations": broken,
                "reason": "Phát hiện vi phạm sau chuyển trạng thái" if broken else "Chuyển trạng thái hợp lệ"}
