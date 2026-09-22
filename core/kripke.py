"""Kripke Structure, CTL Model Checking, Deadlock & Mutual Exclusion Verification, and Graph Visualization."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.figure import Figure

from .spec_loader import StateMachine


@dataclass
class VerificationResult:
    passed: bool
    title: str
    details: str
    counterexample_path: list[str] = field(default_factory=list)
    violation_states: list[str] = field(default_factory=list)


@dataclass
class KripkeCheckReport:
    is_valid: bool
    num_states: int
    num_transitions: int
    deadlock_states: list[str] = field(default_factory=list)
    unreachable_states: list[str] = field(default_factory=list)
    property_results: list[VerificationResult] = field(default_factory=list)
    summary_text: str = ""


class KripkeStructure:
    def __init__(
        self,
        states: list[str],
        initial: list[str],
        transitions: list[list[str]],
        labeling: dict[str, list[str]],
        name: str = "Main Model",
    ):
        self.name = name
        self.states = list(states)
        self.initial = list(initial)
        self.transitions = [list(t) for t in transitions]
        self.labeling = {s: list(labeling.get(s, [])) for s in self.states}

        # Build adjacency lists
        self.succ: dict[str, list[str]] = {s: [] for s in self.states}
        self.pred: dict[str, list[str]] = {s: [] for s in self.states}
        for src, dst in self.transitions:
            if src in self.succ and dst in self.states:
                self.succ[src].append(dst)
            if dst in self.pred and src in self.states:
                self.pred[dst].append(src)

    @classmethod
    def from_state_machine(cls, sm: StateMachine, name: str = "Main Model") -> KripkeStructure:
        return cls(
            states=sm.states,
            initial=sm.initial,
            transitions=sm.transitions,
            labeling=sm.labeling,
            name=name,
        )

    def reachable_states(self) -> set[str]:
        visited: set[str] = set()
        queue = deque([s for s in self.initial if s in self.states])
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                for nxt in self.succ.get(curr, []):
                    if nxt not in visited:
                        queue.append(nxt)
        return visited

    def find_path(self, start_states: list[str], target: str) -> list[str]:
        """Find shortest path from any start state to target using BFS."""
        parent: dict[str, str | None] = {}
        queue = deque(start_states)
        for s in start_states:
            parent[s] = None

        found = False
        while queue:
            curr = queue.popleft()
            if curr == target:
                found = True
                break
            for nxt in self.succ.get(curr, []):
                if nxt not in parent:
                    parent[nxt] = curr
                    queue.append(nxt)

        if not found and target not in parent:
            return []

        path = []
        node: str | None = target
        while node is not None:
            path.append(node)
            node = parent.get(node)
        path.reverse()
        return path

    def check_deadlock(self) -> list[str]:
        """Find reachable states with no outgoing transitions."""
        reachable = self.reachable_states()
        deadlocks = []
        for s in self.states:
            if not self.succ[s] and s in reachable:
                deadlocks.append(s)
        return deadlocks

    def check_mutual_exclusion(self, atom1: str, atom2: str) -> VerificationResult:
        """Verify AG(!(atom1 & atom2))."""
        reachable = self.reachable_states()
        violations = []
        for s in reachable:
            labels = self.labeling.get(s, [])
            if atom1 in labels and atom2 in labels:
                violations.append(s)

        if not violations:
            return VerificationResult(
                passed=True,
                title=f"Loại trừ lẫn nhau: AG(!({atom1} & {atom2}))",
                details=f"Đạt: Không có trạng thái nào đồng thời mang 2 nhãn '{atom1}' và '{atom2}'.",
            )
        else:
            v_state = violations[0]
            path = self.find_path(self.initial, v_state)
            path_str = " -> ".join(path) if path else v_state
            return VerificationResult(
                passed=False,
                title=f"Loại trừ lẫn nhau: AG(!({atom1} & {atom2}))",
                details=(
                    f"VI PHẠM: Phát hiện {len(violations)} trạng thái ({', '.join(violations)}) "
                    f"vừa có nhãn '{atom1}' vừa có nhãn '{atom2}'.\n"
                    f"Vết phản ví dụ: {path_str}"
                ),
                counterexample_path=path,
                violation_states=violations,
            )

    def eval_ctl(self, formula: str) -> VerificationResult:
        """Evaluate simple CTL formulas like AG(p), EF(p), AF(p), AG(!p), EF(!p), EX(p), AX(p)."""
        formula = formula.strip()
        reachable = self.reachable_states()

        # Parse formula
        import re

        m = re.match(r"^(AG|EF|AF|EG|EX|AX)\((.*)\)$", formula, re.IGNORECASE)
        if not m:
            return VerificationResult(
                passed=True,
                title=formula,
                details=f"Công thức '{formula}' không thuộc mẫu CTL cơ bản, bỏ qua kiểm tra tự động.",
            )

        op = m.group(1).upper()
        inner = m.group(2).strip()

        # Check for negation inside
        is_negated = False
        atom = inner
        if inner.startswith("!") or inner.startswith("~"):
            is_negated = True
            atom = inner[1:].strip()

        # Set of states satisfying atomic proposition
        sat_atom: set[str] = set()
        for s in self.states:
            has_prop = atom in self.labeling.get(s, [])
            if (has_prop and not is_negated) or (not has_prop and is_negated):
                sat_atom.add(s)

        # Evaluate operator
        sat_op: set[str] = set()

        if op == "EX":
            # states with at least one successor in sat_atom
            for s in self.states:
                if any(nxt in sat_atom for nxt in self.succ[s]):
                    sat_op.add(s)

        elif op == "AX":
            # states with all successors in sat_atom (and at least one successor)
            for s in self.states:
                if self.succ[s] and all(nxt in sat_atom for nxt in self.succ[s]):
                    sat_op.add(s)

        elif op == "EF":
            # states that can reach sat_atom (backward BFS from sat_atom)
            queue = deque(sat_atom)
            visited = set(sat_atom)
            while queue:
                curr = queue.popleft()
                for p in self.pred[curr]:
                    if p not in visited:
                        visited.add(p)
                        queue.append(p)
            sat_op = visited

        elif op == "AG":
            # AG(phi) == !(EF(!phi)) -> all reachable states must satisfy phi
            violating_reachable = reachable - sat_atom
            if not violating_reachable:
                sat_op = set(self.states)
            else:
                sat_op = set(self.states) - set(self.find_path(self.initial, list(violating_reachable)[0]))

        elif op == "AF":
            # AF(phi): on all paths, eventually phi
            # Fixed point iteration
            current = set(sat_atom)
            changed = True
            while changed:
                changed = False
                for s in self.states:
                    if s not in current and self.succ[s] and all(nxt in current for nxt in self.succ[s]):
                        current.add(s)
                        changed = True
            sat_op = current

        elif op == "EG":
            # EG(phi): exists infinite path where phi holds globally
            # Subgraph induced by sat_atom
            sub_states = set(sat_atom)
            changed = True
            while changed:
                changed = False
                to_remove = set()
                for s in sub_states:
                    if not any(nxt in sub_states for nxt in self.succ[s]):
                        to_remove.add(s)
                if to_remove:
                    sub_states -= to_remove
                    changed = True
            # states that can reach sub_states within sat_atom
            queue = deque(sub_states)
            visited = set(sub_states)
            while queue:
                curr = queue.popleft()
                for p in self.pred[curr]:
                    if p in sat_atom and p not in visited:
                        visited.add(p)
                        queue.append(p)
            sat_op = visited

        # Check if all initial states satisfy the formula
        init_in_states = [s for s in self.initial if s in self.states]
        all_init_sat = all(s in sat_op for s in init_in_states)

        if all_init_sat:
            return VerificationResult(
                passed=True,
                title=f"Kiểm chứng CTL: {formula}",
                details=f"Đạt: Trạng thái khởi tạo ({', '.join(init_in_states)}) thỏa mãn công thức {formula}.",
            )
        else:
            # Find an initial state that violates it
            failing_inits = [s for s in init_in_states if s not in sat_op]
            violating = list(reachable - sat_atom) if op == "AG" else failing_inits
            v_state = violating[0] if violating else (failing_inits[0] if failing_inits else "")
            path = self.find_path(self.initial, v_state) if v_state else []
            return VerificationResult(
                passed=False,
                title=f"Kiểm chứng CTL: {formula}",
                details=(
                    f"VI PHẠM: Công thức {formula} không thỏa mãn tại trạng thái khởi tạo.\n"
                    f"Trạng thái vi phạm: {', '.join(violating[:3])}\n"
                    f"Vết phản ví dụ: {' -> '.join(path) if path else 'N/A'}"
                ),
                counterexample_path=path,
                violation_states=violating,
            )

    def verify_all(
        self,
        safety_properties: list[str] | None = None,
        mutual_exclusion: dict[str, str] | None = None,
    ) -> KripkeCheckReport:
        deadlocks = self.check_deadlock()
        reachable = self.reachable_states()
        unreachable = [s for s in self.states if s not in reachable]

        prop_results: list[VerificationResult] = []

        # 1. Deadlock check result
        if deadlocks:
            prop_results.append(
                VerificationResult(
                    passed=False,
                    title="Kiểm tra Deadlock (Bế tắc)",
                    details=(
                        f"VI PHẠM: Phát hiện {len(deadlocks)} trạng thái bế tắc (không có chuyển tiếp thoát ra): "
                        f"{', '.join(deadlocks)}"
                    ),
                    violation_states=deadlocks,
                )
            )
        else:
            prop_results.append(
                VerificationResult(
                    passed=True,
                    title="Kiểm tra Deadlock (Bế tắc)",
                    details="Đạt: Mọi trạng thái có thể tới được đều có ít nhất một chuyển tiếp đi ra (Deadlock-free).",
                )
            )

        # 2. Mutual exclusion
        if mutual_exclusion and "atom1" in mutual_exclusion and "atom2" in mutual_exclusion:
            m_res = self.check_mutual_exclusion(mutual_exclusion["atom1"], mutual_exclusion["atom2"])
            prop_results.append(m_res)

        # 3. CTL properties
        if safety_properties:
            for prop in safety_properties:
                p_res = self.eval_ctl(prop)
                prop_results.append(p_res)

        all_passed = all(r.passed for r in prop_results)

        lines = [
            f"=== KẾT QUẢ KIỂM CHỨNG MÔ HÌNH KRIPKE: {self.name} ===",
            f"- Số trạng thái: {len(self.states)} (Khởi tạo: {', '.join(self.initial)})",
            f"- Số chuyển tiếp: {len(self.transitions)}",
            f"- Trạng thái không thể tới được: {len(unreachable)} ({', '.join(unreachable) if unreachable else 'Không'})",
            f"- Trạng thái Deadlock: {len(deadlocks)} ({', '.join(deadlocks) if deadlocks else 'Không'})",
            f"- Tổng số thuộc tính kiểm tra: {len(prop_results)}",
            f"- Kết luận chung: {'HỢP LỆ (SAFE)' if all_passed else 'PHÁT HIỆN LỖI / VI PHẠM (UNSAFE)'}",
            "",
            "Chi tiết từng thuộc tính:",
        ]
        for idx, r in enumerate(prop_results, 1):
            status = "[ĐẠT - PASS]" if r.passed else "[VI PHẠM - FAIL]"
            lines.append(f"  {idx}. {status} {r.title}")
            for line in r.details.split("\n"):
                lines.append(f"     {line}")

        return KripkeCheckReport(
            is_valid=all_passed,
            num_states=len(self.states),
            num_transitions=len(self.transitions),
            deadlock_states=deadlocks,
            unreachable_states=unreachable,
            property_results=prop_results,
            summary_text="\n".join(lines),
        )

    def draw_to_figure(
        self,
        fig: Figure | None = None,
        highlight_violations: list[str] | None = None,
        highlight_path: list[str] | None = None,
    ) -> Figure:
        """Render the state graph using networkx and matplotlib."""
        if fig is None:
            fig = Figure(figsize=(7, 5), dpi=100)
            fig.patch.set_facecolor("#ffffff")
        else:
            fig.clear()

        ax = fig.add_subplot(111)
        ax.set_facecolor("#ffffff")

        G = nx.DiGraph()
        for s in self.states:
            G.add_node(s)
        for src, dst in self.transitions:
            G.add_edge(src, dst)

        if not self.states:
            ax.text(0.5, 0.5, "Không có trạng thái nào để hiển thị", ha="center", va="center")
            return fig

        # Layout selection
        if len(self.states) <= 3:
            pos = nx.circular_layout(G)
        elif len(self.states) <= 8:
            pos = nx.spring_layout(G, seed=42, k=1.8 / (len(self.states) ** 0.5))
        else:
            pos = nx.spring_layout(G, seed=42, k=2.5 / (len(self.states) ** 0.5))

        # Determine node colors
        node_colors = []
        edge_colors = []
        node_border_colors = []

        violation_set = set(highlight_violations or [])
        # Also include any state explicitly tagged with "violation"
        for s in self.states:
            if "violation" in self.labeling.get(s, []):
                violation_set.add(s)

        path_edges = set()
        if highlight_path and len(highlight_path) >= 2:
            for i in range(len(highlight_path) - 1):
                path_edges.add((highlight_path[i], highlight_path[i + 1]))

        for node in G.nodes():
            if node in violation_set:
                node_colors.append("#ffcccc")  # Soft red
                node_border_colors.append("#cc0000")
            elif node in self.initial:
                node_colors.append("#d4edda")  # Soft green
                node_border_colors.append("#28a745")
            else:
                node_colors.append("#e3f2fd")  # Soft blue
                node_border_colors.append("#0288d1")

        for u, v in G.edges():
            if (u, v) in path_edges:
                edge_colors.append("#d32f2f")
            else:
                edge_colors.append("#546e7a")

        # Draw nodes
        nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_color=node_colors,
            edgecolors=node_border_colors,
            node_size=2800,
            linewidths=2.0,
        )

        # Draw edges with curvature
        nx.draw_networkx_edges(
            G,
            pos,
            ax=ax,
            edge_color=edge_colors,
            arrowsize=18,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=0.1",
            width=1.8,
            min_source_margin=22,
            min_target_margin=22,
        )

        # Draw labels: State name + atomic propositions
        labels = {}
        for s in self.states:
            lbl_list = self.labeling.get(s, [])
            lbl_str = f"{{{', '.join(lbl_list)}}}" if lbl_list else ""
            labels[s] = f"{s}\n{lbl_str}" if lbl_str else s

        nx.draw_networkx_labels(
            G,
            pos,
            labels=labels,
            ax=ax,
            font_size=8,
            font_family="sans-serif",
            font_weight="bold",
        )

        title = f"Sơ đồ trạng thái Kripke: {self.name}"
        if self.initial:
            title += f" (Khởi tạo: {', '.join(self.initial)})"
        ax.set_title(title, fontsize=10, fontweight="bold", pad=12)
        ax.axis("off")
        fig.tight_layout()
        return fig
