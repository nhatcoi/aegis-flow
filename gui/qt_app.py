"""Desktop GUI for AegisFlow.

Every analysis goes through ``core.pipeline.run_pipeline`` (run on a worker
thread), so the GUI shows exactly what the CLI exports to ``results/``.

Layout: one-line toolbar (spec picker, chapter stepper, run/export) · requirement
and test-case sidebar · chapter tabs · detail inspector · collapsible log.
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

import qdarktheme
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFontDatabase, QTextCursor, QTextFormat
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.codegen import GeneratedFunction, format_code_with_line_numbers, generate_all_functions
from core.kripke import KripkeStructure
from core.pipeline import PipelineReport, run_pipeline
from core.reporter import BMC_VI, STATUS_VI, generate_markdown_report, write_results
from core.spec_loader import Specification, load_specification

from .theme import TOKENS, stylesheet

BASE_DIR = Path(__file__).resolve().parent.parent
SPEC_DIRS = [BASE_DIR / "dataset" / "specs_excel", BASE_DIR / "dataset" / "specs"]
DEFAULT_SPEC = BASE_DIR / "dataset" / "specs_excel" / "payment_gateway_v0_spec.xlsx"
STEPS = [("ch1", "Kripke/CTL"), ("ch2", "Sinh mã + C"), ("ch3", "SMT/BMC"), ("ch4", "Fuzzing"), ("cwe", "CWE")]


class PipelineWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, spec: Specification, seed: int, budget: int):
        super().__init__()
        self.spec, self.seed, self.budget = spec, seed, budget

    def run(self) -> None:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                rep = run_pipeline(self.spec, self.seed, self.budget, workdir=Path(tmp))
            self.finished.emit(rep)
        except Exception:  # noqa: BLE001 - reported to the user in the log panel
            self.failed.emit(traceback.format_exc())


def _table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setWordWrap(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def _section(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("section")
    return lbl


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AegisFlow")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.mode = "dark"
        self.spec: Specification | None = None
        self.functions: list[GeneratedFunction] = []
        self.report: PipelineReport | None = None
        self.model: KripkeStructure | None = None
        self.thread: QThread | None = None
        self.mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

        self._build_toolbar()
        self._build_body()
        self.statusBar().showMessage("Sẵn sàng")
        self._populate_specs()

    # ------------------------------------------------------------------ layout
    def _build_toolbar(self) -> None:
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        brand = QLabel("◆ AegisFlow")
        brand.setObjectName("brand")
        tb.addWidget(brand)

        self.cbo_spec = QComboBox()
        self.cbo_spec.setMinimumWidth(230)
        self.cbo_spec.currentIndexChanged.connect(self._on_spec_changed)
        tb.addWidget(self.cbo_spec)
        act_open = QAction("Mở…", self)
        act_open.triggered.connect(self._browse)
        tb.addAction(act_open)
        tb.addSeparator()

        self.step_labels: dict[str, QLabel] = {}
        for key, text in STEPS:
            lbl = QLabel()
            self.step_labels[key] = lbl
            tb.addWidget(lbl)
        self._reset_steps()

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        tb.addWidget(QLabel("Seed"))
        self.spn_seed = QSpinBox()
        self.spn_seed.setFixedWidth(64)
        self.spn_seed.setRange(0, 10_000)
        self.spn_seed.setValue(1)
        tb.addWidget(self.spn_seed)
        tb.addWidget(QLabel("Fuzz"))
        self.spn_budget = QSpinBox()
        self.spn_budget.setFixedWidth(84)
        self.spn_budget.setRange(100, 100_000)
        self.spn_budget.setSingleStep(500)
        self.spn_budget.setValue(2000)
        tb.addWidget(self.spn_budget)

        self.btn_run = QPushButton("▶  Chạy pipeline")
        self.btn_run.setObjectName("primary")
        self.btn_run.clicked.connect(self._run)
        tb.addWidget(self.btn_run)
        self.btn_export = QPushButton("Xuất…")
        self.btn_export.setToolTip("Xuất thư mục results/ (log, bảng trước/sau, hình, mã nguồn)")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export)
        tb.addWidget(self.btn_export)
        act_theme = QAction("◐", self)
        act_theme.setToolTip("Đổi giao diện sáng/tối")
        act_theme.triggered.connect(self._toggle_theme)
        tb.addAction(act_theme)

    def _build_body(self) -> None:
        outer = QSplitter(Qt.Orientation.Vertical)
        main = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(main)

        # Sidebar
        side = QWidget()
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 4, 6, 8)
        sl.setSpacing(2)
        self.lbl_spec = QLabel("—")
        self.lbl_spec.setWordWrap(True)
        self.lbl_spec.setObjectName("metric")
        sl.addWidget(_section("Đặc tả"))
        sl.addWidget(self.lbl_spec)
        sl.addWidget(_section("Yêu cầu"))
        self.lst_req = QListWidget()
        self.lst_req.itemClicked.connect(lambda it: self._inspect(it.data(Qt.ItemDataRole.UserRole)))
        sl.addWidget(self.lst_req, 3)
        sl.addWidget(_section("Test case"))
        self.lst_tc = QListWidget()
        self.lst_tc.itemClicked.connect(lambda it: self._inspect(it.data(Qt.ItemDataRole.UserRole)))
        sl.addWidget(self.lst_tc, 2)
        main.addWidget(side)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._tab_kripke(), "Ch.1 Kripke/CTL")
        self.tabs.addTab(self._tab_code(), "Ch.2 Sinh mã · Bộ nhớ")
        self.tabs.addTab(self._tab_smt(), "Ch.3 SMT/BMC")
        self.tabs.addTab(self._tab_fuzz(), "Ch.4 Fuzzing")
        self.tabs.addTab(self._tab_cwe(), "Lỗ hổng CWE")
        self.txt_report = QTextBrowser()
        self.tabs.addTab(self.txt_report, "Báo cáo")
        main.addWidget(self.tabs)

        # Inspector
        insp = QWidget()
        il = QVBoxLayout(insp)
        il.setContentsMargins(6, 4, 10, 8)
        il.addWidget(_section("Chi tiết"))
        self.inspector = QTextBrowser()
        self.inspector.setOpenExternalLinks(False)
        il.addWidget(self.inspector)
        main.addWidget(insp)
        main.setSizes([270, 900, 300])
        main.setStretchFactor(1, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(self.mono)
        outer.addWidget(self.log)
        outer.setSizes([780, 110])
        outer.setCollapsible(1, True)
        self.setCentralWidget(outer)

    def _tab_kripke(self) -> QWidget:
        w = QSplitter(Qt.Orientation.Vertical)
        self.figure = Figure(figsize=(7, 4.5), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        w.addWidget(self.canvas)
        self.tbl_ctl = _table(["Thuộc tính", "Kết quả", "Phản ví dụ"])
        self.tbl_ctl.itemSelectionChanged.connect(self._on_ctl_selected)
        w.addWidget(self.tbl_ctl)
        w.setSizes([480, 220])
        return w

    def _tab_code(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        top = QHBoxLayout()
        top.addWidget(QLabel("Hàm"))
        self.cbo_fn = QComboBox()
        self.cbo_fn.setMinimumWidth(320)
        self.cbo_fn.currentIndexChanged.connect(self._on_fn_selected)
        top.addWidget(self.cbo_fn)
        self.lbl_fn = QLabel()
        self.lbl_fn.setObjectName("metric")
        top.addWidget(self.lbl_fn)
        top.addStretch()
        lay.addLayout(top)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.txt_v0, self.txt_v1 = QPlainTextEdit(), QPlainTextEdit()
        for box, title in ((self.txt_v0, "v0 — mã sinh ra theo đặc tả (có lỗi khai báo)"),
                           (self.txt_v1, "v1 — bản đã vá")):
            box.setReadOnly(True)
            box.setFont(self.mono)
            box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            holder = QWidget()
            hl = QVBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.addWidget(_section(title))
            hl.addWidget(box)
            split.addWidget(holder)
        lay.addWidget(split, 3)
        self.tbl_mem = _table(["Hàm", "Bản", "Công cụ", "Kết quả"])
        lay.addWidget(self.tbl_mem, 2)
        return w

    def _tab_smt(self) -> QWidget:
        w = QSplitter(Qt.Orientation.Vertical)
        self.tbl_bmc = _table(["Thuộc tính (BMC)", "Kết luận", "k", "CT", "Phản ví dụ"])
        self.tbl_smt = _table(["Kiểm tra", "Tràn int32", "Model", "Wrap 32-bit", "Sau vá"])
        self.tbl_smt.itemSelectionChanged.connect(self._on_smt_selected)
        self.tbl_ast = _table(["Hàm", "Bản", "McCabe", "Lồng", "Điều kiện"])
        for t in (self.tbl_bmc, self.tbl_smt, self.tbl_ast):
            w.addWidget(t)
        return w

    def _tab_fuzz(self) -> QWidget:
        self.tbl_fuzz = _table(["Hàm", "Bản", "Chiến lược", "Lần thử", "Lỗi", "Lần đầu", "Input", "Loại"])
        self.tbl_fuzz.itemSelectionChanged.connect(self._on_fuzz_selected)
        return self.tbl_fuzz

    def _tab_cwe(self) -> QWidget:
        self.tbl_cwe = _table(["CWE", "Vị trí", "Mức", "Trạng thái", "v0", "v1", "Công cụ"])
        self.tbl_cwe.itemSelectionChanged.connect(self._on_cwe_selected)
        return self.tbl_cwe

    # ------------------------------------------------------------------ helpers
    def _color(self, key: str) -> QColor:
        return QColor(TOKENS[self.mode][key])

    def _set_step(self, key: str, state: str) -> None:
        dot = {"idle": "idle", "pass": "pass", "fail": "fail", "run": "warn"}[state]
        text = dict(STEPS)[key]
        self.step_labels[key].setText(
            f"<span style='color:{TOKENS[self.mode][dot]}'>●</span> {text}")

    def _reset_steps(self) -> None:
        for key, _ in STEPS:
            self._set_step(key, "idle")

    def _fill(self, table: QTableWidget, rows: list[list[object]], status_col: int | None = None) -> None:
        table.setRowCount(0)
        for r, row in enumerate(rows):
            table.insertRow(r)
            for c, value in enumerate(row):
                item = QTableWidgetItem("" if value is None else str(value))
                if c == status_col:
                    text = str(value).upper()
                    good = any(k in text for k in ("ĐẠT", "SAFE", "SẠCH", "CLEAN", "PASS", "UNSAT", "0 FINDING", "ĐÃ VÁ"))
                    bad = any(k in text for k in ("VI PHẠM", "UNSAFE", "DETECTED", "FAIL", "CHƯA", "SAT", "LỖI"))
                    if good:
                        item.setForeground(self._color("pass"))
                    elif bad:
                        item.setForeground(self._color("fail"))
                table.setItem(r, c, item)

    def _inspect(self, html: str | None) -> None:
        self.inspector.setHtml(html or "")

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _draw_model(self, violations: list[str] | None = None, path: list[str] | None = None) -> None:
        if self.model:
            self.model.draw_to_figure(self.figure, highlight_violations=violations, highlight_path=path,
                                      dark=self.mode == "dark")
        else:
            self.figure.clear()
        self.canvas.draw()

    # ------------------------------------------------------------------ spec loading
    def _populate_specs(self) -> None:
        self.cbo_spec.blockSignals(True)
        for folder in SPEC_DIRS:
            for f in sorted(folder.glob("*.xlsx")) + sorted(folder.glob("*.json")):
                self.cbo_spec.addItem(f"{f.stem}  ·  {f.suffix[1:]}", str(f))
        idx = self.cbo_spec.findData(str(DEFAULT_SPEC))
        self.cbo_spec.setCurrentIndex(max(idx, 0))
        self.cbo_spec.blockSignals(False)
        self._on_spec_changed()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chọn đặc tả", str(BASE_DIR), "Đặc tả (*.json *.xlsx)")
        if path:
            self.cbo_spec.addItem(f"{Path(path).stem}  ·  {Path(path).suffix[1:]}", path)
            self.cbo_spec.setCurrentIndex(self.cbo_spec.count() - 1)

    def _on_spec_changed(self) -> None:
        path = self.cbo_spec.currentData()
        if not path:
            return
        try:
            self.spec = load_specification(path)
        except Exception as e:  # noqa: BLE001 - show loader errors to the user
            QMessageBox.critical(self, "Không đọc được đặc tả", str(e))
            return
        self.report = None
        self.btn_export.setEnabled(False)
        self._reset_steps()
        for t in (self.tbl_ctl, self.tbl_mem, self.tbl_bmc, self.tbl_smt, self.tbl_ast, self.tbl_fuzz, self.tbl_cwe):
            t.setRowCount(0)
        self.txt_report.clear()
        s = self.spec
        sm = s.state_machine
        self.lbl_spec.setText(f"<b>{s.name}</b><br>{len(s.requirements)} yêu cầu · "
                              f"{len(sm.states) if sm else 0} trạng thái · {len(s.functions)} hàm · "
                              f"{len(s.arithmetic_checks)} kiểm tra số học · {len(s.test_cases)} test case")
        self.lst_req.clear()
        for r in s.requirements:
            item = QListWidgetItem(f"{r.id}  ·  {r.priority}  ·  {r.category}")
            item.setToolTip(r.text)
            item.setData(Qt.ItemDataRole.UserRole, f"<h3>{r.id}</h3><p><b>{r.category} · {r.priority}</b></p><p>{r.text}</p>")
            self.lst_req.addItem(item)
        self._fill_test_cases()
        self.model = KripkeStructure.from_state_machine(sm, s.name) if sm and sm.states else None
        self._draw_model()
        self._set_functions(generate_all_functions(s))
        self._inspect(f"<h3>{s.name}</h3><p>{s.description}</p>")
        self._log(f"Đã nạp {Path(path).name}: {s.summary()}")
        self.statusBar().showMessage(f"Đã nạp {s.name}. Bấm “Chạy pipeline”.")

    def _fill_test_cases(self) -> None:
        self.lst_tc.clear()
        results = {t.test_case.id: t for t in self.report.test_results} if self.report else {}
        for tc in self.spec.test_cases:
            res = results.get(tc.id)
            status = res.status if res else "chưa chạy"
            item = QListWidgetItem(f"{tc.id}  ·  {status}  ·  {tc.title}")
            if res:
                item.setForeground(self._color({"PASS": "pass", "FAIL": "fail"}.get(res.status, "muted")))
            steps = "".join(f"<li>{st}</li>" for st in tc.steps)
            item.setData(Qt.ItemDataRole.UserRole,
                         f"<h3>{tc.id}: {tc.title}</h3><p><b>Yêu cầu:</b> {', '.join(tc.requirement_ids)}</p>"
                         f"<p><b>Tiền điều kiện:</b> {tc.preconditions}</p><ol>{steps}</ol>"
                         f"<p><b>Mong đợi:</b> {tc.expected_result}</p>"
                         + (f"<p><b>Thực tế: {res.status}</b><br>{res.reason}</p>" if res else ""))
            self.lst_tc.addItem(item)

    # ------------------------------------------------------------------ run
    def _run(self) -> None:
        if not self.spec or self.thread:
            return
        self.btn_run.setEnabled(False)
        for key, _ in STEPS:
            self._set_step(key, "run")
        self._log(f"Chạy pipeline (seed={self.spn_seed.value()}, fuzz={self.spn_budget.value()})…")
        self.statusBar().showMessage("Đang chạy pipeline…")
        self.thread = QThread()
        self.worker = PipelineWorker(self.spec, self.spn_seed.value(), self.spn_budget.value())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self._on_thread_finished)
        self.thread.start()

    def _on_thread_finished(self) -> None:
        self.thread = None
        self.btn_run.setEnabled(True)

    def _on_failed(self, tb: str) -> None:
        self._reset_steps()
        self._log(tb)
        self.statusBar().showMessage("Pipeline lỗi — xem log.")

    def _on_done(self, rep: PipelineReport) -> None:
        self.report = rep
        self.btn_export.setEnabled(True)
        k = rep.kripke
        self._set_step("ch1", "idle" if not k else ("pass" if k.is_valid else "fail"))
        v0_static = [f for (_, v), fs in rep.static.items() if v == "v0" for f in fs]
        self._set_step("ch2", "fail" if v0_static or any(s.status == "detected" and s.version == "v0"
                                                         for s in rep.sanitizers) else "pass")
        self._set_step("ch3", "fail" if any(b.status == "unsafe" for b in rep.bmc)
                       or any(s.overflow_possible and s.patch_status != "unsat" for s in rep.smt) else "pass")
        self._set_step("ch4", "fail" if any(r.found and r.version == "v0" for r in rep.fuzz) else "pass")
        self._set_step("cwe", "fail" if rep.audit.open_findings else "pass")

        # Ch.1
        rows = []
        for r in (k.property_results if k else []):
            trace = " → ".join(r.counterexample_path)
            if r.loop_start is not None and trace:
                trace += f"  (lặp từ {r.counterexample_path[r.loop_start]})"
            rows.append([r.formula or r.title, STATUS_VI[r.status], trace or r.details.splitlines()[0]])
        self._fill(self.tbl_ctl, rows, status_col=1)
        viol = list(k.deadlock_states) + [s for r in k.property_results if r.status == "fail"
                                          for s in r.violation_states] if k else []
        self._draw_model(viol)

        # Ch.2
        self._set_functions(rep.functions)
        mem = [[n, v, "Static scanner", "; ".join(f"{f.rule} dòng {f.line}" for f in fs) or "0 finding"]
               for (n, v), fs in rep.static.items()]
        mem += [[s.function, s.version, "ASan/UBSan",
                 "; ".join(f"{kind} dòng {ln}" for kind, _, ln in s.detections) or s.status] for s in rep.sanitizers]
        self._fill(self.tbl_mem, mem, status_col=3)

        # Ch.3
        self._fill(self.tbl_bmc, [[b.property, BMC_VI[b.status], b.violation_depth if b.violation_depth is not None
                                   else "—", b.completeness_threshold, " → ".join(b.counterexample) or "—"]
                                  for b in rep.bmc], status_col=1)
        self._fill(self.tbl_smt, [[s.name, "có thể tràn" if s.overflow_possible else "không", s.overflow_values or "—",
                                   s.wrapped_value if s.bv_overflow else "—", s.patch_status.upper()]
                                  for s in rep.smt], status_col=4)
        self._fill(self.tbl_ast, [[m.name, v, m.cyclomatic, m.nesting_depth, "; ".join(m.conditions) or "—"]
                                  for v, m in rep.metrics])

        # Ch.4
        self._fill(self.tbl_fuzz, [[r.function, r.version, r.strategy, r.iterations,
                                    f"{r.hits}" + (" FAIL" if r.found else " PASS"), r.first_hit or "—",
                                    r.first_input or "—", r.finding or "—"] for r in rep.fuzz], status_col=4)

        # CWE
        self._fill(self.tbl_cwe, [[f.cwe_id, f.source_component, f.severity,
                                   f.status + ("" if f.fixed is None else (" · ĐÃ VÁ" if f.fixed else " · CHƯA VÁ")),
                                   f.before_text, f.after_text, ", ".join(f.tools)] for f in rep.audit.findings],
                   status_col=3)
        self.txt_report.setMarkdown(generate_markdown_report(rep).replace("![Kripke](figures/kripke.png)", ""))
        self._fill_test_cases()

        passed = sum(t.status == "PASS" for t in rep.test_results)
        msg = (f"Xong: {len(rep.audit.confirmed)} lỗ hổng có bằng chứng, {len(rep.audit.open_findings)} chưa vá · "
               f"test case {passed}/{len(rep.test_results)} PASS · {sum(rep.timings.values()):.1f}s")
        self.statusBar().showMessage(msg)
        self._log(rep.audit.summary_text)
        self._log(msg)

    # ------------------------------------------------------------------ selections
    def _on_ctl_selected(self) -> None:
        if not self.report or not self.report.kripke:
            return
        row = self.tbl_ctl.currentRow()
        results = self.report.kripke.property_results
        if 0 <= row < len(results):
            r = results[row]
            self._draw_model(r.violation_states, r.counterexample_path)
            warn = "".join(f"<p style='color:{TOKENS[self.mode]['warn']}'>⚠ {w}</p>" for w in r.warnings)
            details = r.details.replace("\n", "<br>")
            self._inspect(f"<h3>{r.formula or r.title}</h3><p><b>{STATUS_VI[r.status]}</b></p>"
                          f"<p>{details}</p>{warn}")

    def _set_functions(self, functions: list[GeneratedFunction]) -> None:
        keep = self.cbo_fn.currentIndex()
        self.functions = functions
        self.cbo_fn.blockSignals(True)
        self.cbo_fn.clear()
        for gf in functions:
            mark = "  ⚠" if gf.has_bug else ""
            self.cbo_fn.addItem(f"{gf.spec.name}  ·  {gf.language}  ·  {gf.spec.kind}{mark}")
        self.cbo_fn.setCurrentIndex(keep if 0 <= keep < len(functions) else 0)
        self.cbo_fn.blockSignals(False)
        if not functions:
            self.txt_v0.setPlainText("Đặc tả không khai báo hàm nào trong sheet HamSinhMa.")
            self.txt_v1.clear()
            self.lbl_fn.clear()
            return
        self._on_fn_selected()

    def _highlight(self, box: QPlainTextEdit, lines: set[int]) -> None:
        selections = []
        for n in sorted(lines):
            sel = QTextEdit.ExtraSelection()
            color = self._color("fail")
            color.setAlpha(70)
            sel.format.setBackground(color)
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            block = box.document().findBlockByLineNumber(n - 1)
            sel.cursor = QTextCursor(block)
            selections.append(sel)
        box.setExtraSelections(selections)

    def _on_fn_selected(self) -> None:
        idx = self.cbo_fn.currentIndex()
        if not 0 <= idx < len(self.functions):
            return
        gf = self.functions[idx]
        fn = gf.spec
        self.txt_v0.setPlainText(format_code_with_line_numbers(gf.code_vulnerable))
        self.txt_v1.setPlainText(format_code_with_line_numbers(gf.code_safe))
        bug = fn.bug or ("—" if fn.language == "c" else "mặc định (có lỗi)")
        self.lbl_fn.setText(f"Loi = {bug}" + (f" · bộ đệm {fn.buffer_size} byte" if fn.buffer_size else "")
                            + ("" if gf.has_bug else " · v0 = v1 (không cài lỗi)"))

        html = [f"<h3>{fn.name}</h3><p>{gf.explanation}</p>"]
        bad_lines: set[int] = set()
        if self.report:
            rep = self.report
            for version in ("v0", "v1"):
                finds = rep.static.get((fn.name, version))
                if finds is not None:
                    items = "".join(f"<li>dòng {f.line}: {f.rule} ({f.cwe})</li>" for f in finds) or "<li>0 finding</li>"
                    html.append(f"<p><b>Scanner {version}</b></p><ul>{items}</ul>")
                    if version == "v0":
                        bad_lines |= {f.line for f in finds}
            for r in rep.sanitizers:
                if r.function == fn.name:
                    det = "; ".join(f"{k} dòng {ln}" for k, _, ln in r.detections) or r.status
                    html.append(f"<p><b>ASan/UBSan {r.version}:</b> {det}</p>")
                    if r.version == "v0":
                        bad_lines |= {ln for _, _, ln in r.detections if ln}
            for r in rep.fuzz:
                if r.function == fn.name:
                    hit = f"lỗi ở lần {r.first_hit}, input {r.first_input}" if r.found else "không tìm ra lỗi"
                    html.append(f"<p><b>{r.strategy} {r.version}:</b> {r.hits}/{r.iterations} — {hit}</p>")
        else:
            html.append("<p><i>Bấm “Chạy pipeline” để quét tĩnh, chạy ASan/UBSan và fuzzing trên hàm này.</i></p>")
        self._highlight(self.txt_v0, bad_lines)
        self._inspect("".join(html))

    def _on_smt_selected(self) -> None:
        row = self.tbl_smt.currentRow()
        if self.report and 0 <= row < len(self.report.smt):
            self._inspect("<p>" + self.report.smt[row].details.replace("\n", "<br>") + "</p>")

    def _on_fuzz_selected(self) -> None:
        row = self.tbl_fuzz.currentRow()
        if self.report and 0 <= row < len(self.report.fuzz):
            r = self.report.fuzz[row]
            events = "<br>".join(r.events[:40])
            self._inspect(f"<h3>{r.function} · {r.version} · {r.strategy}</h3>"
                          f"<p>{r.hits}/{r.iterations} lần thử gây lỗi, {r.seconds * 1000:.1f} ms</p><p>{events}</p>")

    def _on_cwe_selected(self) -> None:
        row = self.tbl_cwe.currentRow()
        if self.report and 0 <= row < len(self.report.audit.findings):
            f = self.report.audit.findings[row]
            ev = "".join(f"<li>{e}</li>" for e in f.evidence)
            after = "".join(f"<li>{e}</li>" for e in f.after)
            self._inspect(f"<h3>{f.cwe_id} {f.cwe_name}</h3><p><b>{f.source_component}</b> · {f.severity} · "
                          f"{f.status}</p><p>{f.description}</p><p><b>Bằng chứng v0</b></p><ul>{ev}</ul>"
                          f"<p><b>Sau vá (v1)</b></p><ul>{after or '<li>—</li>'}</ul>"
                          f"<p><b>Khắc phục:</b> {f.remediation}</p><p><b>CVE minh họa:</b> {f.illustrative_cve}</p>")

    # ------------------------------------------------------------------ export / theme
    def _export(self) -> None:
        if not self.report:
            return
        start = BASE_DIR / "results" / self.report.spec.name
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất kết quả", str(start.parent))
        if path:
            out = write_results(self.report, Path(path) / self.report.spec.name)
            self._log(f"Đã xuất kết quả vào {out}")
            self.statusBar().showMessage(f"Đã xuất {out}")

    def _toggle_theme(self) -> None:
        self.mode = "light" if self.mode == "dark" else "dark"
        apply_theme(QApplication.instance(), self.mode)
        if self.report:
            self._on_done(self.report)
        else:
            self._reset_steps()
            self._draw_model()


def apply_theme(app: QApplication, mode: str) -> None:
    qdarktheme.setup_theme(mode, custom_colors={"primary": "#4f8cff"}, additional_qss=stylesheet(mode))


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("AegisFlow")
    apply_theme(app, "dark")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
