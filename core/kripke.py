"""Kripke Structure, CTL Model Checking, Deadlock & Mutual Exclusion Verification, and Graph Visualization."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import networkx as nx
from matplotlib.figure import Figure

from .ctl import CTLModelChecker
from .spec_loader import StateMachine


@dataclass
class VerificationResult:
    passed: bool
    title: str
    details: str
    counterexample_path: list[str] = field(default_factory=list)
    violation_states: list[str] = field(default_factory=list)
    status: str = ""  # "pass" | "fail" | "error"; derived from `passed` when empty
    kind: str = ""  # "deadlock" | "mutex" | "ctl"
    formula: str = ""
    loop_start: int | None = None
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.status:
            self.status = "pass" if self.passed else "fail"


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
                kind="mutex",
                formula=f"AG(!({atom1} & {atom2}))",
                title=f"Loại trừ lẫn nhau: AG(!({atom1} & {atom2}))",
                details=f"Đạt: Không có trạng thái nào đồng thời mang 2 nhãn '{atom1}' và '{atom2}'.",
            )
        else:
            v_state = violations[0]
            path = self.find_path(self.initial, v_state)
            path_str = " -> ".join(path) if path else v_state
            return VerificationResult(
                passed=False,
                kind="mutex",
                formula=f"AG(!({atom1} & {atom2}))",
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
        """Model-check an arbitrary CTL formula (see core.ctl for the grammar)."""
        checker = CTLModelChecker(self.states, self.initial, self.succ, self.labeling)
        res = checker.check(formula)
        details = res.details
        if res.warnings:
            details += "\n" + "\n".join(f"CẢNH BÁO: {w}" for w in res.warnings)
        return VerificationResult(
            passed=res.passed,
            title=f"Kiểm chứng CTL: {formula}",
            details=details,
            counterexample_path=res.counterexample if not res.passed else [],
            violation_states=res.violation_states,
            status=res.status,
            kind="ctl",
            formula=formula,
            loop_start=res.loop_start,
            warnings=res.warnings,
        )

    def verify_all(
        self,
        safety_properties: list[str] | None = None,
        mutual_exclusion: dict[str, str] | list[dict[str, str]] | None = None,
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
                    kind="deadlock",
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
                    kind="deadlock",
                    details="Đạt: Mọi trạng thái có thể tới được đều có ít nhất một chuyển tiếp đi ra (Deadlock-free).",
                )
            )

        # 2. Mutual exclusion
        pairs = [mutual_exclusion] if isinstance(mutual_exclusion, dict) else (mutual_exclusion or [])
        for pair in pairs:
            if pair and pair.get("atom1") and pair.get("atom2"):
                prop_results.append(self.check_mutual_exclusion(pair["atom1"], pair["atom2"]))

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
            status = {"pass": "[ĐẠT - PASS]", "fail": "[VI PHẠM - FAIL]", "error": "[LỖI - ERROR]"}[r.status]
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

    def components(self) -> list[list[str]]:
        """Weakly connected components, in the order of the initial states (independent sub-flows)."""
        undirected: dict[str, set[str]] = {st: set() for st in self.states}
        for a, b in self.transitions:
            if a in undirected and b in undirected:
                undirected[a].add(b)
                undirected[b].add(a)
        seen: set[str] = set()
        components: list[list[str]] = []
        for st in self.initial + self.states:
            if st in seen or st not in undirected:
                continue
            comp, queue = [], deque([st])
            seen.add(st)
            while queue:
                cur = queue.popleft()
                comp.append(cur)
                for nxt in undirected[cur]:
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append(nxt)
            components.append(comp)
        return components

    def layered_layout(self) -> dict[str, tuple[float, float]]:
        """Left-to-right layout: x = BFS depth from the initial states, one band per connected component."""
        components = self.components()
        pos: dict[str, tuple[float, float]] = {}
        y_offset = 0.0
        for comp in components:
            members = set(comp)
            starts = [st for st in self.initial if st in members] or [comp[0]]
            depth = {st: 0 for st in starts}
            queue = deque(starts)
            while queue:
                cur = queue.popleft()
                for nxt in self.succ[cur]:
                    if nxt in members and nxt not in depth:
                        depth[nxt] = depth[cur] + 1
                        queue.append(nxt)
            for st in comp:
                depth.setdefault(st, max(depth.values(), default=0) + 1)
            layers: dict[int, list[str]] = {}
            for st in sorted(comp, key=self.states.index):  # keep spec order inside a layer
                layers.setdefault(depth[st], []).append(st)
            height = max(len(v) for v in layers.values())
            for d, members_at in layers.items():
                for i, st in enumerate(members_at):
                    pos[st] = (float(d), -(y_offset + i + (height - len(members_at)) / 2))
            y_offset += height + 0.6
        return pos

    def draw_to_figure(
        self,
        fig: Figure | None = None,
        highlight_violations: list[str] | None = None,
        highlight_path: list[str] | None = None,
        dark: bool = False,
        only: list[str] | None = None,
    ) -> Figure:
        """Render the state graph using networkx and matplotlib."""
        bg, fg, edge = ("#1b1d23", "#e6e8ee", "#8a93a6") if dark else ("#ffffff", "#1d2330", "#546e7a")
        if fig is None:
            fig = Figure(figsize=(7, 5), dpi=100)
        else:
            fig.clear()
        fig.patch.set_facecolor(bg)

        ax = fig.add_subplot(111)
        ax.set_facecolor(bg)

        shown = [st for st in self.states if only is None or st in only]
        G = nx.DiGraph()
        for s in shown:
            G.add_node(s)
        for src, dst in self.transitions:
            if src in G and dst in G and src != dst:
                G.add_edge(src, dst)
        self_loops = [st for st in G if st in self.succ.get(st, [])]

        if not shown:
            ax.text(0.5, 0.5, "Không có trạng thái nào để hiển thị", ha="center", va="center", color=fg)
            return fig

        pos = {st: xy for st, xy in self.layered_layout().items() if st in G}
        on_path = set(highlight_path or [])

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

        palette = {
            "viol": ("#5c2327", "#ff6b6b") if dark else ("#ffcccc", "#cc0000"),
            "init": ("#1f4030", "#4cc38a") if dark else ("#d4edda", "#28a745"),
            "node": ("#243049", "#5b8def") if dark else ("#e3f2fd", "#0288d1"),
        }
        dim = 0.3 if len(on_path) >= 2 else 1.0
        for node in G.nodes():
            key = "viol" if node in violation_set else ("init" if node in self.initial else "node")
            node_colors.append(palette[key][0])
            node_border_colors.append(palette[key][1])
        node_alpha = [1.0 if dim == 1.0 or n in on_path else dim for n in G.nodes()]

        for u, v in G.edges():
            edge_colors.append("#ff5252" if (u, v) in path_edges else edge)
        edge_alpha = [1.0 if dim == 1.0 or (u, v) in path_edges else dim for u, v in G.edges()]

        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, edgecolors=node_border_colors,
                               node_size=900, linewidths=2.0, alpha=node_alpha)
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_colors, alpha=edge_alpha, arrowsize=14,
                               arrowstyle="-|>", connectionstyle="arc3,rad=0.12",
                               width=[2.6 if e in path_edges else 1.4 for e in G.edges()],
                               min_source_margin=16, min_target_margin=16)

        # Labels go under the node: state name, then its propositions in a muted colour
        muted = "#8a93a6" if dark else "#6b7385"
        for st, (x, y) in pos.items():
            alpha = 1.0 if dim == 1.0 or st in on_path else 0.45
            ax.annotate(st, (x, y), xytext=(0, -19), textcoords="offset points", ha="center", va="top",
                        fontsize=8, fontweight="bold", color=fg, alpha=alpha)
            props = self.labeling.get(st, [])
            if props:
                ax.annotate(", ".join(props), (x, y), xytext=(0, -30), textcoords="offset points",
                            ha="center", va="top", fontsize=7, color=muted, alpha=alpha)
        for st in self_loops:  # a drawn self-loop ellipse would cover the labels; mark it instead
            x, y = pos[st]
            loop_on_path = (st, st) in path_edges
            ax.annotate("↺", (x, y), xytext=(13, 9), textcoords="offset points", fontsize=12,
                        fontweight="bold", color="#ff5252" if loop_on_path else edge,
                        alpha=1.0 if dim == 1.0 or loop_on_path else dim)
        ax.margins(x=0.08, y=0.14)

        title = f"Sơ đồ trạng thái Kripke: {self.name}"
        if self.initial:
            title += f" (Khởi tạo: {', '.join(self.initial)})"
        ax.set_title(title, fontsize=10, fontweight="bold", pad=12, color=fg)
        ax.axis("off")
        fig.tight_layout()
        return fig
