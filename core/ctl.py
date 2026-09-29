"""CTL parser and explicit-state model checker (Chương 1.5).

Grammar (lowest to highest precedence)::

    formula := implies
    implies := or ( ("->" | "=>") implies )?          right associative
    iff     := implies ( "<->" implies )*
    or      := and ( ("|" | "||") and )*
    and     := unary ( ("&" | "&&") unary )*
    unary   := ("!" | "~") unary
             | ("AG" | "AF" | "AX" | "EG" | "EF" | "EX") unary
             | ("A" | "E") "[" formula "U" formula "]"
             | "(" formula ")" | "true" | "false" | ATOM

Semantics follow the standard labelling algorithm: EX, EU and EG are computed
by fixpoint iteration, every other operator is derived from them. CTL assumes
a total transition relation; states without successors are given a stutter
self-loop for evaluation only (deadlocks are still reported separately).
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field

TEMPORAL_UNARY = ("AG", "AF", "AX", "EG", "EF", "EX")


class CTLSyntaxError(ValueError):
    pass


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Node:
    op: str  # "atom", "true", "false", "not", "and", "or", "implies", "iff", AG.., "EU", "AU"
    args: tuple = ()
    name: str = ""

    def __str__(self) -> str:
        if self.op == "atom":
            return self.name
        if self.op in ("true", "false"):
            return self.op
        if self.op == "not":
            return f"!{_wrap(self.args[0])}"
        if self.op in ("and", "or", "implies", "iff"):
            sym = {"and": " & ", "or": " | ", "implies": " -> ", "iff": " <-> "}[self.op]
            return sym.join(_wrap(a) for a in self.args)
        if self.op in TEMPORAL_UNARY:
            return f"{self.op}({self.args[0]})"
        if self.op in ("EU", "AU"):
            return f"{self.op[0]}[{self.args[0]} U {self.args[1]}]"
        return self.op

    def atoms(self) -> set[str]:
        if self.op == "atom":
            return {self.name}
        out: set[str] = set()
        for a in self.args:
            out |= a.atoms()
        return out


def _wrap(n: Node) -> str:
    return f"({n})" if n.op in ("and", "or", "implies", "iff") else str(n)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(
    r"\s*(?:(<->|->|=>|&&|\|\||[()!~&|\[\]])|([A-Za-z_][A-Za-z0-9_]*))"
)


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise CTLSyntaxError(f"Ký tự không hợp lệ tại vị trí {pos}: '{text[pos:pos + 10]}'")
        tokens.append(m.group(1) or m.group(2))
        pos = m.end()
    return tokens


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.tokens = _tokenize(text)
        self.i = 0

    def peek(self, k: int = 0) -> str | None:
        j = self.i + k
        return self.tokens[j] if j < len(self.tokens) else None

    def take(self, expected: str | None = None) -> str:
        tok = self.peek()
        if tok is None:
            raise CTLSyntaxError(f"Công thức kết thúc sớm, cần '{expected or 'biểu thức'}'")
        if expected is not None and tok != expected:
            raise CTLSyntaxError(f"Cần '{expected}' nhưng gặp '{tok}'")
        self.i += 1
        return tok

    def parse(self) -> Node:
        if not self.tokens:
            raise CTLSyntaxError("Công thức rỗng")
        node = self.iff()
        if self.peek() is not None:
            raise CTLSyntaxError(f"Thừa ký hiệu '{self.peek()}' ở cuối công thức")
        return node

    def iff(self) -> Node:
        left = self.implies()
        while self.peek() == "<->":
            self.take()
            left = Node("iff", (left, self.implies()))
        return left

    def implies(self) -> Node:
        left = self.or_()
        if self.peek() in ("->", "=>"):
            self.take()
            return Node("implies", (left, self.implies()))
        return left

    def or_(self) -> Node:
        left = self.and_()
        while self.peek() in ("|", "||"):
            self.take()
            left = Node("or", (left, self.and_()))
        return left

    def and_(self) -> Node:
        left = self.unary()
        while self.peek() in ("&", "&&"):
            self.take()
            left = Node("and", (left, self.unary()))
        return left

    def unary(self) -> Node:
        tok = self.peek()
        if tok is None:
            raise CTLSyntaxError("Công thức kết thúc sớm")
        if tok in ("!", "~"):
            self.take()
            return Node("not", (self.unary(),))
        if tok in TEMPORAL_UNARY:
            self.take()
            return Node(tok, (self.unary(),))
        if tok in ("A", "E") and self.peek(1) == "[":
            self.take()
            self.take("[")
            left = self.iff()
            self.take("U")
            right = self.iff()
            self.take("]")
            return Node(f"{tok}U", (left, right))
        if tok == "(":
            self.take()
            node = self.iff()
            self.take(")")
            return node
        if tok in (")", "[", "]", "&", "&&", "|", "||", "->", "=>", "<->"):
            raise CTLSyntaxError(f"Không mong đợi '{tok}'")
        self.take()
        if tok.lower() == "true":
            return Node("true")
        if tok.lower() == "false":
            return Node("false")
        return Node("atom", name=tok)


def parse_ctl(text: str) -> Node:
    """Parse a CTL formula; raises CTLSyntaxError on malformed input."""
    return _Parser(text).parse()


# ---------------------------------------------------------------------------
# Model checker
# ---------------------------------------------------------------------------
@dataclass
class CTLResult:
    formula: str
    status: str  # "pass" | "fail" | "error"
    details: str
    counterexample: list[str] = field(default_factory=list)
    loop_start: int | None = None  # index in counterexample where a lasso loop starts
    violation_states: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "pass"


class CTLModelChecker:
    def __init__(self, states, initial, succ, labeling):
        self.states = list(states)
        self.initial = [s for s in initial if s in succ]
        self.labeling = labeling
        # Totalize: a state without successors stutters on itself.
        self.succ = {s: (list(dict.fromkeys(succ[s])) or [s]) for s in self.states}
        self.pred: dict[str, list[str]] = {s: [] for s in self.states}
        for s, nxts in self.succ.items():
            for t in nxts:
                self.pred[t].append(s)
        self.all_labels = {lbl for s in self.states for lbl in labeling.get(s, [])}
        self._cache: dict[Node, frozenset[str]] = {}

    # --- labelling algorithm -------------------------------------------------
    def sat(self, n: Node) -> frozenset[str]:
        if n in self._cache:
            return self._cache[n]
        S = frozenset(self.states)
        op, a = n.op, n.args
        if op == "true":
            r = S
        elif op == "false":
            r = frozenset()
        elif op == "atom":
            r = frozenset(s for s in self.states if n.name in self.labeling.get(s, []))
        elif op == "not":
            r = S - self.sat(a[0])
        elif op == "and":
            r = self.sat(a[0]) & self.sat(a[1])
        elif op == "or":
            r = self.sat(a[0]) | self.sat(a[1])
        elif op == "implies":
            r = (S - self.sat(a[0])) | self.sat(a[1])
        elif op == "iff":
            x, y = self.sat(a[0]), self.sat(a[1])
            r = (x & y) | ((S - x) & (S - y))
        elif op == "EX":
            r = self._ex(self.sat(a[0]))
        elif op == "AX":
            r = S - self._ex(S - self.sat(a[0]))
        elif op == "EF":
            r = self._eu(S, self.sat(a[0]))
        elif op == "AG":
            r = S - self._eu(S, S - self.sat(a[0]))
        elif op == "EG":
            r = self._eg(self.sat(a[0]))
        elif op == "AF":
            r = S - self._eg(S - self.sat(a[0]))
        elif op == "EU":
            r = self._eu(self.sat(a[0]), self.sat(a[1]))
        elif op == "AU":
            p, q = self.sat(a[0]), self.sat(a[1])
            not_q = S - q
            r = S - (self._eu(not_q, not_q & (S - p)) | self._eg(not_q))
        else:  # pragma: no cover - parser never produces other ops
            raise ValueError(op)
        self._cache[n] = r
        return r

    def _ex(self, target: frozenset[str]) -> frozenset[str]:
        return frozenset(s for s in self.states if any(t in target for t in self.succ[s]))

    def _eu(self, p: frozenset[str], q: frozenset[str]) -> frozenset[str]:
        result = set(q)
        queue = deque(q)
        while queue:
            t = queue.popleft()
            for s in self.pred[t]:
                if s not in result and s in p:
                    result.add(s)
                    queue.append(s)
        return frozenset(result)

    def _eg(self, p: frozenset[str]) -> frozenset[str]:
        current = set(p)
        changed = True
        while changed:
            changed = False
            for s in list(current):
                if not any(t in current for t in self.succ[s]):
                    current.discard(s)
                    changed = True
        return frozenset(current)

    # --- paths ---------------------------------------------------------------
    def _path(self, start: str, targets: frozenset[str], within: frozenset[str] | None = None) -> list[str]:
        """Shortest path from start to any target, staying inside `within` before the target."""
        if start in targets:
            return [start]
        parent: dict[str, str | None] = {start: None}
        queue = deque([start])
        while queue:
            s = queue.popleft()
            for t in self.succ[s]:
                if t in parent:
                    continue
                if t in targets:
                    path = [t, s]
                    node = parent[s]
                    while node is not None:
                        path.append(node)
                        node = parent[node]
                    return path[::-1]
                if within is None or t in within:
                    parent[t] = s
                    queue.append(t)
        return [start]

    def _lasso(self, start: str, region: frozenset[str]) -> tuple[list[str], int | None]:
        """Walk inside `region` (an EG-closed set) until a state repeats."""
        path, seen = [start], {start: 0}
        s = start
        while True:
            nxt = next((t for t in self.succ[s] if t in region), None)
            if nxt is None:
                return path, None
            if nxt in seen:
                path.append(nxt)
                return path, seen[nxt]
            seen[nxt] = len(path)
            path.append(nxt)
            s = nxt

    def explain_false(self, n: Node, s: str) -> tuple[list[str], int | None]:
        S = frozenset(self.states)
        op, a = n.op, n.args
        if op == "AG":
            bad = S - self.sat(a[0])
            prefix = self._path(s, bad)
            tail, loop = self.explain_false(a[0], prefix[-1])
            return prefix[:-1] + tail, None if loop is None else loop + len(prefix) - 1
        if op == "AF":
            return self._lasso(s, self._eg(S - self.sat(a[0])))
        if op == "AX":
            t = next((t for t in self.succ[s] if t not in self.sat(a[0])), s)
            return [s, t], None
        if op == "AU":
            q = self.sat(a[1])
            eg = self._eg(S - q)
            if s in eg:
                return self._lasso(s, eg)
            bad = (S - q) & (S - self.sat(a[0]))
            return self._path(s, bad, S - q), None
        if op == "implies":
            return self.explain_false(a[1], s)
        if op == "and":
            first = a[0] if s not in self.sat(a[0]) else a[1]
            return self.explain_false(first, s)
        if op == "not":
            return self.explain_true(a[0], s)
        return [s], None

    def explain_true(self, n: Node, s: str) -> tuple[list[str], int | None]:
        op, a = n.op, n.args
        if op == "EF":
            return self._path(s, self.sat(a[0])), None
        if op == "EX":
            t = next((t for t in self.succ[s] if t in self.sat(a[0])), s)
            return [s, t], None
        if op == "EG":
            return self._lasso(s, self.sat(n))
        if op == "EU":
            return self._path(s, self.sat(a[1]), self.sat(a[0])), None
        if op == "or":
            first = a[0] if s in self.sat(a[0]) else a[1]
            return self.explain_true(first, s)
        if op == "not":
            return self.explain_false(a[0], s)
        return [s], None

    # --- entry point ---------------------------------------------------------
    def check(self, text: str) -> CTLResult:
        try:
            node = parse_ctl(text)
        except CTLSyntaxError as e:
            return CTLResult(text, "error", f"LỖI CÚ PHÁP: {e}. Công thức KHÔNG được kiểm chứng.")

        warnings = [
            f"Nhãn '{atom}' không xuất hiện ở bất kỳ trạng thái nào (sai chính tả?) — được coi là luôn sai."
            for atom in sorted(node.atoms() - self.all_labels)
        ]
        if not self.initial:
            return CTLResult(text, "error", "Mô hình không có trạng thái khởi tạo.", warnings=warnings)

        sat = self.sat(node)
        failing = [s for s in self.initial if s not in sat]
        if not failing:
            witness: list[str] = []
            if node.op in ("EF", "EU", "EG", "EX"):
                witness, _ = self.explain_true(node, self.initial[0])
            details = f"ĐẠT: mọi trạng thái khởi tạo ({', '.join(self.initial)}) thỏa {node}."
            if len(witness) > 1:
                details += f"\nĐường minh chứng: {' -> '.join(witness)}"
            return CTLResult(text, "pass", details, counterexample=witness, warnings=warnings)

        path, loop = self.explain_false(node, failing[0])
        trace = " -> ".join(path)
        if loop is not None:
            trace += f"  (lặp lại từ {path[loop]})"
        details = (
            f"VI PHẠM: trạng thái khởi tạo {', '.join(failing)} không thỏa {node}.\n"
            f"Phản ví dụ: {trace}"
        )
        return CTLResult(
            text, "fail", details, counterexample=path, loop_start=loop,
            violation_states=[path[-1]] if path else failing, warnings=warnings,
        )
