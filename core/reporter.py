"""Evidence export: markdown report, before/after table, raw logs, sources and figures.

``write_results(report, out_dir)`` produces the folder that is submitted with
the written report (results/ in the BTL submission layout)::

    report.md  before_after.md  summary.json  environment.txt
    logs/      ctl.txt bmc.txt scan.txt scan.json sanitizer_*.log cppcheck.txt
               ast.csv z3.txt fuzz.csv fuzz_events.txt tests.csv
    source/    <function>_v0.{c,py}  <function>_v1.{c,py}
    figures/   kripke.png  kripke.tex
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure

if TYPE_CHECKING:
    from .pipeline import PipelineReport

STATUS_VI = {"pass": "ĐẠT", "fail": "VI PHẠM", "error": "LỖI"}
BMC_VI = {"unsafe": "UNSAFE", "safe_complete": "SAFE (đạt CT)", "safe_bounded": "SAFE đến k (chưa đạt CT)",
          "error": "LỖI"}


def _md_cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _table(header: list[str], rows: list[list[object]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(_md_cell(c) for c in row) + " |" for row in rows]
    return out + [""]


def _ext(lang: str) -> str:
    return "c" if lang == "c" else "py"


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------
def before_after_table(rep: PipelineReport) -> list[str]:
    rows = [[f.cwe_id, f.source_component, f.before_text, f.after_text, ", ".join(f.tools) or "—"]
            for f in rep.audit.findings]
    return _table(["CWE", "Vị trí", "Trạng thái v0", "Trạng thái v1", "Công cụ xác minh"], rows)


def generate_markdown_report(rep: PipelineReport) -> str:
    spec = rep.spec
    L: list[str] = [f"# Kết quả kiểm chứng: `{spec.name}`", "", spec.description or "", ""]
    L += ["## Môi trường chạy", ""] + _table(["Mục", "Giá trị"], [[k, v] for k, v in rep.environment.items()])

    L += ["## 1. Đặc tả", ""]
    L += _table(["ID", "Danh mục", "Ưu tiên", "Nội dung"],
                [[r.id, r.category, r.priority, r.text] for r in spec.requirements])

    # --- Chương 1 -------------------------------------------------------------------
    L += ["## 2. Chương 1 — Kripke và CTL", ""]
    if rep.kripke:
        k = rep.kripke
        L += [(f"- |S| = {k.num_states}, |R| = {k.num_transitions}, "
               f"S0 = {', '.join(spec.state_machine.initial)}"),
              f"- Trạng thái không đạt tới: {', '.join(k.unreachable_states) or 'không'}",
              f"- Deadlock: {', '.join(k.deadlock_states) or 'không'}", ""]
        rows = []
        for r in k.property_results:
            trace = " → ".join(r.counterexample_path) if r.counterexample_path else ""
            if r.loop_start is not None and trace:
                trace += f" (lặp từ {r.counterexample_path[r.loop_start]})"
            rows.append([r.formula or r.title, STATUS_VI[r.status], trace or r.details.splitlines()[0]])
        L += _table(["Thuộc tính", "Kết quả", "Phản ví dụ / ghi chú"], rows)
        warns = [w for r in k.property_results for w in r.warnings]
        if warns:
            L += ["**Cảnh báo:**", ""] + [f"- {w}" for w in dict.fromkeys(warns)] + [""]
        L += ["![Kripke](figures/kripke.png)", ""]
    else:
        L += ["*Đặc tả không có mô hình trạng thái.*", ""]
    for name, fr in rep.flows.items():
        L += [f"**Luồng phụ `{name}`:** {'hợp lệ' if fr.is_valid else 'có vi phạm'}", ""]

    L += ["### Bounded Model Checking (Z3)", ""]
    if rep.bmc:
        L += _table(["Thuộc tính", "Kết luận", "k vi phạm", "CT", "Phản ví dụ"],
                    [[b.property, BMC_VI[b.status], b.violation_depth if b.violation_depth is not None else "—",
                      b.completeness_threshold, " → ".join(b.counterexample) or "—"] for b in rep.bmc])
    else:
        L += ["*Không có thuộc tính an toàn dạng AG(φ) để chạy BMC.*", ""]

    # --- Chương 2 -------------------------------------------------------------------
    L += ["## 3. Chương 2 — Phân tích bộ nhớ trên mã C sinh ra", ""]
    rows = []
    for (name, version), findings in rep.static.items():
        desc = "; ".join(f"{f.rule} (dòng {f.line})" for f in findings) or "0 finding"
        rows.append([name, version, desc])
    L += ["**Static scanner:**", ""] + (_table(["Hàm", "Bản", "Finding"], rows) if rows else ["*Không có hàm C.*", ""])
    if rep.sanitizers:
        L += ["**AddressSanitizer / UBSan:**", ""]
        L += _table(["Hàm", "Bản", "Input", "Kết quả", "Phát hiện"],
                    [[s.function, s.version, s.input_desc or "—", s.status,
                      "; ".join(f"{k} ({c}) dòng {ln}" for k, c, ln in s.detections) or "—"] for s in rep.sanitizers])
        notes = {s.note for s in rep.sanitizers if s.note}
        L += [f"> {n}" for n in notes] + ([""] if notes else [])
    if rep.cppcheck:
        L += ["**cppcheck:** xem `logs/cppcheck.txt`.", ""]

    # --- Chương 3 -------------------------------------------------------------------
    L += ["## 4. Chương 3 — AST và SMT", ""]
    L += _table(["Hàm", "Bản", "Biến", "Điều kiện", "McCabe V(G)", "Độ sâu lồng"],
                [[m.name, v, ", ".join(m.variables), "; ".join(m.conditions) or "—", m.cyclomatic, m.nesting_depth]
                 for v, m in rep.metrics])
    for s in rep.smt:
        L += [f"**{s.name}**", "", "```text", s.details, "```", ""]

    # --- Chương 4 -------------------------------------------------------------------
    L += ["## 5. Chương 4 — Fuzzing", ""]
    if rep.fuzz:
        L += _table(["Hàm", "Bản", "Chiến lược", "Lần thử", "Số lỗi", "Lần đầu tìm thấy", "Input", "Loại", "Thời gian"],
                    [[r.function, r.version, r.strategy, r.iterations, r.hits, r.first_hit or "—",
                      r.first_input or "—", r.finding or "—", f"{r.seconds * 1000:.1f} ms"] for r in rep.fuzz])
    else:
        L += ["*Không có hàm Python để fuzz.*", ""]

    # --- CWE ------------------------------------------------------------------------
    L += ["## 6. Phân tích từng lỗ hổng", ""]
    by_name = {gf.spec.name: gf for gf in rep.functions}
    for i, f in enumerate(rep.audit.findings, 1):
        L += [f"### 6.{i}. {f.cwe_id} ({f.cwe_name}) tại `{f.source_component}` — {f.status}", "",
              f"1. **Vị trí:** {f.source_component} {f.location}".rstrip()
              + (f"; truy vết {', '.join(f.requirement_ids)}" if f.requirement_ids else ""),
              f"2. **Nguyên nhân:** {f.description}",
              "3. **Bằng chứng lỗi tồn tại:**"]
        L += [f"   - {e}" for e in f.evidence]
        L += [f"4. **Cách vá:** {f.remediation}"]
        gf = by_name.get(f.source_component)
        if gf and gf.has_bug:
            L += ["", f"```{gf.language}", "/* v0 */" if gf.language == "c" else "# v0", gf.code_vulnerable.strip(),
                  "```", f"```{gf.language}", "/* v1 */" if gf.language == "c" else "# v1", gf.code_safe.strip(), "```"]
        L += [f"5. **Bằng chứng đã vá:** {f.after_text}", f"   - Ví dụ CVE: {f.illustrative_cve}", ""]

    L += ["## 7. Bảng tổng hợp trước/sau", ""] + before_after_table(rep)

    L += ["## 8. Truy vết test case", ""]
    L += _table(["ID", "Yêu cầu", "Tiêu đề", "Kết quả mong đợi", "Thực tế", "Lý do"],
                [[t.test_case.id, ", ".join(t.test_case.requirement_ids), t.test_case.title,
                  t.test_case.expected_result, t.status, t.reason] for t in rep.test_results])
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def _failing_trace(rep: PipelineReport) -> tuple[list[str], list[str]]:
    if not rep.kripke:
        return [], []
    violations: list[str] = list(rep.kripke.deadlock_states)
    path: list[str] = []
    for r in rep.kripke.property_results:
        if r.status == "fail":
            violations += r.violation_states
            if not path and r.counterexample_path:
                path = r.counterexample_path
    return list(dict.fromkeys(violations)), path


def save_kripke_png(rep: PipelineReport, path: Path) -> None:
    violations, trace = _failing_trace(rep)
    fig = Figure(figsize=(8, 5.5), dpi=150)
    rep.kripke_model.draw_to_figure(fig, highlight_violations=violations, highlight_path=trace)
    fig.savefig(path, bbox_inches="tight")


def kripke_tikz(rep: PipelineReport) -> str:
    model = rep.kripke_model
    violations, trace = _failing_trace(rep)
    trace_edges = set(pairwise(trace))
    pos = model.layered_layout()
    sx, sy = 3.6, 1.35  # cm per BFS layer / per row

    def nid(s: str) -> str:
        return "n_" + "".join(ch if ch.isalnum() else "_" for ch in s)

    def tex(s: str) -> str:
        return s.replace("_", r"\_")

    out = [f"% Kripke: {tex(model.name)} (sinh tự động bởi core.reporter)",
           (r"\begin{tikzpicture}[->,>=stealth,semithick,every node/.style={draw,rounded corners=2pt,"
            r"align=center,font=\scriptsize,inner sep=3pt,minimum width=18mm}]")]
    for s in model.states:
        style = "fill=red!20,draw=red" if s in violations else ("fill=blue!12" if s in model.initial else "fill=white")
        x, y = pos[s]
        labels = ", ".join(tex(lbl) for lbl in model.labeling.get(s, []))
        out.append(f"  \\node[{style}] ({nid(s)}) at ({x * sx:.2f},{y * sy:.2f}) "
                   f"{{\\textbf{{{tex(s)}}}\\\\{{\\tiny \\{{{labels}\\}}}}}};")
    for a, b in model.transitions:
        color = ",red,very thick" if (a, b) in trace_edges else ""
        if a == b:
            out.append(f"  \\draw[{color.lstrip(',')}] ({nid(a)}) edge[loop right] ({nid(a)});")
        else:
            bend = ",bend left=12" if [b, a] in model.transitions else ""
            out.append(f"  \\draw[{(color + bend).lstrip(',')}] ({nid(a)}) to ({nid(b)});")
    out.append(r"\end{tikzpicture}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Results folder
# ---------------------------------------------------------------------------
def summary_dict(rep: PipelineReport) -> dict:
    return {
        "spec": rep.spec.name,
        "environment": rep.environment,
        "timings_seconds": {k: round(v, 4) for k, v in rep.timings.items()},
        "kripke": None if not rep.kripke else {
            "valid": rep.kripke.is_valid, "states": rep.kripke.num_states,
            "transitions": rep.kripke.num_transitions, "deadlocks": rep.kripke.deadlock_states,
            "properties": [{"formula": r.formula or r.title, "status": r.status,
                            "counterexample": r.counterexample_path, "loop_start": r.loop_start}
                           for r in rep.kripke.property_results]},
        "bmc": [{"property": b.property, "status": b.status, "depth": b.violation_depth,
                 "completeness_threshold": b.completeness_threshold, "counterexample": b.counterexample}
                for b in rep.bmc],
        "static": {f"{n}/{v}": [f.to_dict() for f in fs] for (n, v), fs in rep.static.items()},
        "sanitizers": [{"function": s.function, "version": s.version, "status": s.status,
                        "detections": s.detections} for s in rep.sanitizers],
        "smt": [{"name": s.name, "condition_sat": s.condition_sat, "overflow": s.overflow_possible,
                 "model": s.overflow_values, "exact_value": s.overflow_evaluated, "bv_wrapped": s.wrapped_value,
                 "patch": s.patch_status} for s in rep.smt],
        "fuzz": [{k: v for k, v in asdict(r).items() if k != "events"} for r in rep.fuzz],
        "findings": [{"cwe": f.cwe_id, "name": f.cwe_name, "severity": f.severity, "component": f.source_component,
                      "status": f.status, "tools": f.tools, "before": f.evidence, "after": f.after,
                      "fixed": f.fixed, "requirements": f.requirement_ids} for f in rep.audit.findings],
        "test_cases": [{"id": t.test_case.id, "status": t.status, "reason": t.reason} for t in rep.test_results],
    }


def write_results(rep: PipelineReport, out: Path) -> Path:
    out = Path(out)
    logs, source, figures = out / "logs", out / "source", out / "figures"
    for d in (logs, source, figures):
        d.mkdir(parents=True, exist_ok=True)

    (out / "report.md").write_text(generate_markdown_report(rep), encoding="utf-8")
    (out / "before_after.md").write_text("\n".join(["# Bảng tổng hợp trước/sau", ""] + before_after_table(rep)),
                                         encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary_dict(rep), ensure_ascii=False, indent=2, default=str),
                                      encoding="utf-8")
    (out / "environment.txt").write_text("\n".join(f"{k}: {v}" for k, v in rep.environment.items()) + "\n",
                                         encoding="utf-8")

    # Chương 1
    ctl = [rep.kripke.summary_text] if rep.kripke else ["(không có mô hình)"]
    ctl += [f"\n--- Luồng phụ: {n} ---\n{r.summary_text}" for n, r in rep.flows.items()]
    (logs / "ctl.txt").write_text("\n".join(ctl) + "\n", encoding="utf-8")
    (logs / "bmc.txt").write_text("\n\n".join(b.to_text() for b in rep.bmc) + "\n", encoding="utf-8")
    if rep.kripke_model:
        save_kripke_png(rep, figures / "kripke.png")
        (figures / "kripke.tex").write_text(kripke_tikz(rep), encoding="utf-8")

    # Chương 2
    scan_lines = []
    for (name, version), findings in rep.static.items():
        scan_lines.append(f"== {name}_{version}.c: {len(findings)} finding")
        scan_lines += [f"  {name}_{version}.c:{f.line}: [{f.severity}] {f.rule} {f.cwe}: {f.message}" for f in findings]
    (logs / "scan.txt").write_text("\n".join(scan_lines) + "\n", encoding="utf-8")
    (logs / "scan.json").write_text(json.dumps({f"{n}/{v}": [f.to_dict() for f in fs]
                                                for (n, v), fs in rep.static.items()},
                                               ensure_ascii=False, indent=2), encoding="utf-8")
    for s in rep.sanitizers:
        (logs / f"sanitizer_{s.function}_{s.version}.log").write_text(
            f"$ {s.command}\n# input: {s.input_desc}\n# exit code: {s.returncode}\n# status: {s.status}\n"
            + (f"# note: {s.note}\n" if s.note else "") + "\n" + s.log, encoding="utf-8")
    if rep.cppcheck:
        (logs / "cppcheck.txt").write_text("\n".join(f"== {n}_{v}.c\n{o}" for (n, v), o in rep.cppcheck.items()),
                                           encoding="utf-8")
    for gf in rep.functions:
        (source / f"{gf.spec.name}_v0.{_ext(gf.language)}").write_text(gf.code_vulnerable, encoding="utf-8")
        (source / f"{gf.spec.name}_v1.{_ext(gf.language)}").write_text(gf.code_safe, encoding="utf-8")

    # Chương 3
    with open(logs / "ast.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["function", "version", "language", "variables", "conditions", "loops", "cyclomatic",
                    "nesting_depth", "loc"])
        for v, m in rep.metrics:
            w.writerow([m.name, v, m.language, ";".join(m.variables), " ; ".join(m.conditions),
                        " ; ".join(m.loops), m.cyclomatic, m.nesting_depth, m.lines_of_code])
    (logs / "z3.txt").write_text("\n\n".join(s.details for s in rep.smt) + "\n", encoding="utf-8")

    # Chương 4
    with open(logs / "fuzz.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["function", "version", "strategy", "budget", "iterations", "hits", "first_hit",
                    "first_input", "finding", "cwe", "seconds", "lines_covered"])
        for r in rep.fuzz:
            w.writerow([r.function, r.version, r.strategy, r.budget, r.iterations, r.hits, r.first_hit,
                        r.first_input, r.finding, r.cwe, f"{r.seconds:.6f}", r.lines_covered])
    events = []
    for r in rep.fuzz:
        events.append(f"== {r.function} {r.version} {r.strategy}")
        events += [f"  {e}" for e in r.events[:50]]
    (logs / "fuzz_events.txt").write_text("\n".join(events) + "\n", encoding="utf-8")

    with open(logs / "tests.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "requirements", "title", "expected", "status", "reason"])
        for t in rep.test_results:
            w.writerow([t.test_case.id, ",".join(t.test_case.requirement_ids), t.test_case.title,
                        t.test_case.expected_result, t.status, t.reason])
    return out


def comparison_markdown(before: PipelineReport, after: PipelineReport) -> str:
    """Design-level before/after: the same properties and test cases on the flawed and fixed spec."""
    L = [f"# So sánh thiết kế: `{before.spec.name}` → `{after.spec.name}`", ""]
    b_props = {r.formula or r.title: r for r in (before.kripke.property_results if before.kripke else [])}
    a_props = {r.formula or r.title: r for r in (after.kripke.property_results if after.kripke else [])}
    b_bmc = {b.property: b for b in before.bmc}
    a_bmc = {b.property: b for b in after.bmc}
    rows = []
    for name, r in b_props.items():
        a = a_props.get(name)
        bmc_b, bmc_a = b_bmc.get(r.formula), a_bmc.get(r.formula)
        trace = " → ".join(r.counterexample_path)
        rows.append([name, STATUS_VI[r.status] + (f" ({trace})" if trace and not r.passed else ""),
                     STATUS_VI[a.status] if a else "—",
                     f"{BMC_VI[bmc_b.status]} → {BMC_VI[bmc_a.status]}" if bmc_b and bmc_a else "—"])
    L += ["## Thuộc tính trên mô hình Kripke", ""]
    L += _table(["Thuộc tính", before.spec.name, after.spec.name, "BMC"], rows)

    b_tc = {t.test_case.id: t for t in before.test_results}
    L += ["## Test case", ""]
    L += _table(["ID", "Tiêu đề", before.spec.name, after.spec.name],
                [[t.test_case.id, t.test_case.title, b_tc[t.test_case.id].status if t.test_case.id in b_tc else "—",
                  t.status] for t in after.test_results])

    def count(rep: PipelineReport) -> list[object]:
        a = rep.audit
        return [len(a.confirmed), len(a.open_findings), len(a.declared_only),
                f"{sum(t.status == 'PASS' for t in rep.test_results)}/{len(rep.test_results)}"]
    L += ["## Tổng hợp", ""]
    L += _table(["Đặc tả", "Lỗ hổng có bằng chứng", "Chưa vá", "Chỉ khai báo", "Test case PASS"],
                [[before.spec.name, *count(before)], [after.spec.name, *count(after)]])
    return "\n".join(L)


def export_report(filepath: str | Path, rep: PipelineReport) -> Path:
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_markdown_report(rep), encoding="utf-8")
    return path
