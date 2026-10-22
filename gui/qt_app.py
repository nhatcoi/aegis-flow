"""Desktop GUI for AegisFlow.

Every analysis goes through ``core.pipeline.run_pipeline`` (run on a worker
thread), so the GUI shows exactly what the CLI exports to ``results/``.

Layout: toolbar (spec picker, run-parameter popover, run/export) · sidebar with
requirement/test-case tabs · overview + chapter tabs whose icons carry the result ·
contextual detail inspector · log hidden behind a status-bar toggle.
"""
from __future__ import annotations

import html
import re
import sys
import tempfile
import traceback
from pathlib import Path

import qdarktheme
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFontDatabase, QIcon, QPainter, QPixmap, QTextCursor, QTextFormat
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
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
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from core import ai_explain
from core.codegen import GeneratedFunction, format_code_with_line_numbers, generate_all_functions
from core.diagnosis import diagnose, related_requirements
from core.kripke import KripkeStructure
from core.pipeline import PipelineReport, run_pipeline
from core.reporter import BMC_VI, STATUS_VI, before_after_table, generate_markdown_report, write_results
from core.spec_loader import Specification, load_specification

from .spec_draft_dialog import SpecDraftDialog
from .theme import TOKENS, stylesheet

BASE_DIR = Path(__file__).resolve().parent.parent
DRAFT_DIR = BASE_DIR / "dataset" / "drafts"
SPEC_DIRS = [BASE_DIR / "dataset" / "specs_excel", BASE_DIR / "dataset" / "specs", DRAFT_DIR]
DEFAULT_SPEC = BASE_DIR / "dataset" / "specs_excel" / "payment_gateway_v0_spec.xlsx"
# step key -> (tab index, tab title); tab 0 is the overview
STEPS = {"ch1": (1, "Ch.1 Kripke"), "ch2": (2, "Ch.2 Sinh mã · Bộ nhớ"), "ch3": (3, "Ch.3 SMT/BMC"),
         "ch4": (4, "Ch.4 Fuzzing"), "cwe": (5, "CWE")}
# overview card key -> (caption, tab to open on click; None = test-case list in the sidebar)
CARDS = {"ctl": ("thuộc tính CTL vi phạm", 1), "bmc": ("thuộc tính BMC UNSAFE", 3),
         "fuzz": ("lần fuzz tìm ra lỗi trên v0", 4), "cwe": ("lỗ hổng có bằng chứng", 5),
         "tc": ("test case PASS", None)}
GUIDE = """\
## AegisFlow làm gì?

Từ **một file đặc tả**, tool chạy qua 4 chương. Mỗi lỗi báo ra đều kèm **bằng chứng do công cụ sinh ra**.
**v0** là thiết kế còn lỗi, **v1** là thiết kế đã sửa.

- **Ch.1 Kripke/CTL**: vẽ sơ đồ mọi trạng thái của đơn hàng, rồi kiểm tra trên **mọi đường đi** xem có \
vi phạm luật nào không. *Ví dụ:* timeout mà vẫn giao hàng khi chưa thu tiền.
- **(Bước chuẩn bị) Sinh mã**: từ đặc tả, sinh ra mỗi hàm 2 bản: **v0** cài sẵn lỗi, **v1** đã vá.
- **Ch.2 Bộ nhớ**: quét mã tìm lỗi bộ nhớ, rồi **chạy thật với ASan** để xác nhận. \
*Ví dụ:* tràn bộ đệm, giải phóng bộ nhớ hai lần.
- **Ch.3 SMT/BMC**: dùng **Z3 chứng minh bằng toán học**. BMC tìm đường đi lỗi trong k bước. SMT tìm giá trị \
làm tràn số, và chứng minh bản vá đúng với **mọi** đầu vào (UNSAT).
- **Ch.4 Fuzzing**: tự sinh thật nhiều input để tìm input làm hàm lỗi. Ngẫu nhiên thì không tìm ra cửa hậu, \
còn **concolic** đọc điều kiện trong code nên tìm ra ngay.

### Tham số (nút ⚙)

- **Timeout sanitizer**: thời gian tối đa cho mỗi lần chạy ASan/UBSan.
- **Độ sâu k (BMC)**: số bước tối đa Z3 được thử. *Auto* = chạy tới CT, nên kết luận chắc chắn.
- **Seed**: khởi tạo bộ sinh ngẫu nhiên của fuzzer. Cùng seed thì kết quả giống hệt.
- **Ngân sách / chiến lược**: số lần thử tối đa cho mỗi chiến lược fuzzing.

### Đọc kết quả

- Chấm trên tab: **đỏ** = có lỗi, **xanh** = đạt; số bên cạnh là số lỗi tìm được.
- Bấm một dòng để xem **phản ví dụ, chẩn đoán và log thô** ở panel Chi tiết.
- *✨ Giải thích bằng AI* chỉ để diễn giải, **không phải bằng chứng**.
"""
PARAM_DEFAULTS = {"seed": 1, "budget": 2000, "bmc": -1, "timeout": 30, "fuzz_search": "bfs"}


class PipelineWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, spec: Specification, seed: int, budget: int, **options):
        super().__init__()
        self.spec, self.seed, self.budget, self.options = spec, seed, budget, options

    def run(self) -> None:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                rep = run_pipeline(self.spec, self.seed, self.budget, workdir=Path(tmp), **self.options)
            self.finished.emit(rep)
        except Exception:  # noqa: BLE001 - reported to the user in the log panel
            self.failed.emit(traceback.format_exc())


class AIWorker(QObject):
    finished = pyqtSignal(str, str)  # (context, answer)
    failed = pyqtSignal(str)

    def __init__(self, cfg: ai_explain.AIConfig, context: str):
        super().__init__()
        self.cfg, self.context = cfg, context

    def run(self) -> None:
        try:
            self.finished.emit(self.context, ai_explain.explain(self.cfg, self.context))
        except Exception as e:  # noqa: BLE001 - shown in the AI panel
            self.failed.emit(str(e))


def _tone(text: str) -> str | None:
    """Colour key for a status cell. Bad words are checked first: "UNSAFE" contains "SAFE"."""
    t = text.upper()
    if "CHƯA ĐẠT CT" in t:
        return "warn"  # safe only up to k: not a violation, not a proof either
    if any(k in t for k in ("UNSAFE", "VI PHẠM", "DETECTED", "FAIL", "CHƯA", "LỖI", "CÓ THỂ TRÀN")):
        return "fail"
    if any(k in t for k in ("UNSAT", "ĐẠT", "SAFE", "SẠCH", "CLEAN", "PASS", "0 FINDING", "ĐÃ VÁ", "KHÔNG")):
        return "pass"
    if re.search(r"\bSAT\b", t):
        return "fail"
    return None


def _raw(text: str, limit: int = 4000) -> str:
    """Raw tool output block for the inspector."""
    text = text.strip()
    if len(text) > limit:
        text = text[:limit] + f"\n… (cắt bớt, còn {len(text) - limit} ký tự trong results/logs/)"
    return f"<p><b>Log thô</b></p><pre>{html.escape(text) or '—'}</pre>"


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


def _dot_icon(color: str) -> QIcon:
    pm = QPixmap(14, 14)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(3, 3, 8, 8)
    painter.end()
    return QIcon(pm)


def _spin(lo: int, hi: int, value: int, *, step: int = 1, suffix: str = "", tip: str = "") -> QSpinBox:
    spn = QSpinBox()
    spn.setRange(lo, hi)
    spn.setSingleStep(step)
    spn.setValue(value)
    spn.setSuffix(suffix)
    spn.setToolTip(tip)
    spn.setMinimumWidth(110)
    return spn


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
        self.highlight: tuple[list[str] | None, list[str] | None] = (None, None)
        self.ai_cfg = ai_explain.load_config()
        self.ai_thread: QThread | None = None
        self.ai_cache: dict[str, str] = {}
        self._orphan_threads: list = []  # AI requests still running after their dialog closed
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
        act_draft = QAction("✨ Đặc tả AI…", self)
        act_draft.setToolTip("Mô tả hệ thống bằng lời, AI tạo đặc tả JSON nháp để đọc lại, sửa và chạy thử")
        act_draft.triggered.connect(self._open_spec_draft)
        tb.addAction(act_draft)
        tb.addSeparator()

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.btn_params = QToolButton()
        self.btn_params.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_params.setToolTip("Tham số chạy pipeline")
        self.btn_params.setMenu(self._params_menu())
        tb.addWidget(self.btn_params)
        self._update_params_label()

        self.btn_run = QPushButton("▶  Chạy pipeline")
        self.btn_run.setObjectName("primary")
        self.btn_run.clicked.connect(self._run)
        tb.addWidget(self.btn_run)
        self.btn_export = QPushButton("Xuất…")
        self.btn_export.setToolTip("Xuất thư mục results/ (log, bảng trước/sau, hình, mã nguồn)")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export)
        tb.addWidget(self.btn_export)
        act_guide = QAction("ⓘ", self)
        act_guide.setToolTip("Hướng dẫn đọc kết quả: 4 chương làm gì")
        act_guide.triggered.connect(self._show_guide)
        tb.addAction(act_guide)
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
        self.side_tabs = QTabWidget()
        self.side_tabs.setDocumentMode(True)
        self.lst_req, self.lst_tc = QListWidget(), QListWidget()
        for lst, title in ((self.lst_req, "Yêu cầu"), (self.lst_tc, "Test case")):
            lst.setWordWrap(True)
            lst.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            lst.setResizeMode(QListWidget.ResizeMode.Adjust)
            lst.setSpacing(2)
            lst.itemClicked.connect(lambda it: self._inspect(it.data(Qt.ItemDataRole.UserRole)))
            self.side_tabs.addTab(lst, title)
        sl.addWidget(self.side_tabs, 1)
        main.addWidget(side)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._tab_overview(), "Tổng quan")
        self.tabs.addTab(self._tab_kripke(), "Ch.1 Kripke")
        self.tabs.addTab(self._tab_code(), "Ch.2 Sinh mã · Bộ nhớ")
        self.tabs.addTab(self._tab_smt(), "Ch.3 SMT/BMC")
        self.tabs.addTab(self._tab_fuzz(), "Ch.4 Fuzzing")
        self.tabs.addTab(self._tab_cwe(), "CWE")
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
        il.addWidget(self.inspector, 3)
        self.btn_ai = QPushButton("✨  Giải thích bằng AI")
        self.btn_ai.setEnabled(False)
        self.btn_ai.setToolTip(f"Gửi nội dung đang xem tới {self.ai_cfg.base_url} (model {self.ai_cfg.model}) "
                               "để diễn giải" if self.ai_cfg.enabled
                               else "Chưa cấu hình API key (AEGIS_AI_KEY / OPENAI_API_KEY trong .env)")
        self.btn_ai.clicked.connect(self._ask_ai)
        il.addWidget(self.btn_ai)
        self.ai_box = QTextBrowser()
        self.ai_box.setVisible(False)
        il.addWidget(self.ai_box, 2)
        main.addWidget(insp)
        main.setSizes([290, 900, 290])
        main.setStretchFactor(1, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(self.mono)
        outer.addWidget(self.log)
        outer.setSizes([760, 160])
        self.log.setVisible(False)
        self.setCentralWidget(outer)

        self.btn_log = QToolButton()
        self.btn_log.setText("Log")
        self.btn_log.setCheckable(True)
        self.btn_log.setToolTip("Hiện/ẩn log chi tiết")
        self.btn_log.toggled.connect(self.log.setVisible)
        self.statusBar().addPermanentWidget(self.btn_log)

    def _params_menu(self) -> QMenu:
        menu = QMenu(self)
        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(14, 10, 14, 10)
        self.spn_timeout = _spin(1, 600, PARAM_DEFAULTS["timeout"], suffix=" s",
                                 tip="Thời gian tối đa cho mỗi lần chạy harness ASan/UBSan")
        self.spn_bmc = _spin(-1, 100, PARAM_DEFAULTS["bmc"],
                             tip="Độ sâu tối đa của BMC. Auto = completeness threshold (đường kính khả đạt);\n"
                                 "k nhỏ hơn CT chỉ cho kết luận 'an toàn đến độ sâu k'.")
        self.spn_bmc.setSpecialValueText("Auto (CT)")
        self.spn_seed = _spin(0, 10_000, PARAM_DEFAULTS["seed"],
                              tip="Seed ngẫu nhiên của fuzzer black-box và coverage-guided (tái tạo kết quả)")
        self.spn_budget = _spin(100, 100_000, PARAM_DEFAULTS["budget"], step=500,
                                tip="Số vòng lặp tối đa cho mỗi chiến lược fuzzing (black-box, coverage, concolic)")
        self.cbo_fuzz_search = QComboBox()
        self.cbo_fuzz_search.addItem("BFS (chiều rộng)", "bfs")
        self.cbo_fuzz_search.addItem("DFS (chiều sâu)", "dfs")
        self.cbo_fuzz_search.setToolTip("Chiến lược duyệt cây đường đi cho Concolic Fuzzing (BFS = ngắn nhất, DFS = sâu nhất)")
        for title, label, spn in (("Ch.2 · Bộ nhớ C", "Timeout sanitizer", self.spn_timeout),
                                  ("Ch.3 · BMC", "Độ sâu k", self.spn_bmc),
                                  ("Ch.4 · Fuzzing", "Seed", self.spn_seed),
                                  (None, "Ngân sách / chiến lược", self.spn_budget)):
            if title:
                form.addRow(_section(title))
            form.addRow(label, spn)
            spn.valueChanged.connect(self._update_params_label)
        form.addRow("Duyệt Concolic", self.cbo_fuzz_search)
        self.cbo_fuzz_search.currentIndexChanged.connect(self._update_params_label)
        btn_reset = QPushButton("Khôi phục mặc định")
        btn_reset.clicked.connect(self._reset_params)
        form.addRow(btn_reset)
        action = QWidgetAction(menu)
        action.setDefaultWidget(host)
        menu.addAction(action)
        return menu

    def _open_spec_draft(self) -> None:
        dlg = SpecDraftDialog(self.ai_cfg, self.mode, self)
        dlg.saved.connect(self._on_draft_saved)
        dlg.exec()

    def _on_draft_saved(self, path: str) -> None:
        idx = self.cbo_spec.findData(path)
        if idx < 0:
            self.cbo_spec.addItem(self._spec_label(Path(path)), path)
            idx = self.cbo_spec.count() - 1
        self.cbo_spec.setCurrentIndex(idx)
        self._log(f"Đã lưu bản nháp AI: {path}")

    @staticmethod
    def _spec_label(f: Path) -> str:
        return f"{f.stem}  ·  {f.suffix[1:]}" + ("  ·  nháp AI" if f.parent == DRAFT_DIR else "")

    def _show_guide(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Hướng dẫn đọc kết quả")
        dlg.resize(640, 620)
        lay = QVBoxLayout(dlg)
        text = QTextBrowser()
        text.setMarkdown(GUIDE)
        lay.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        dlg.exec()

    def _reset_params(self) -> None:
        self.spn_seed.setValue(PARAM_DEFAULTS["seed"])
        self.spn_budget.setValue(PARAM_DEFAULTS["budget"])
        self.spn_bmc.setValue(PARAM_DEFAULTS["bmc"])
        self.spn_timeout.setValue(PARAM_DEFAULTS["timeout"])
        if hasattr(self, "cbo_fuzz_search"):
            self.cbo_fuzz_search.setCurrentIndex(0)

    def _bmc_depth(self) -> int | None:
        return None if self.spn_bmc.value() < 0 else self.spn_bmc.value()

    def _update_params_label(self) -> None:
        k = self._bmc_depth()
        strat = self.cbo_fuzz_search.currentData() if hasattr(self, "cbo_fuzz_search") else "bfs"
        self.btn_params.setText(f"⚙  seed {self.spn_seed.value()} · fuzz {self.spn_budget.value()} ({strat.upper()}) · "
                                f"k {'auto' if k is None else k} · {self.spn_timeout.value()}s")

    def _tab_overview(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 14, 16, 12)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.cards: dict[str, tuple[QLabel, QLabel]] = {}
        for key, (caption, tab) in CARDS.items():
            card = QPushButton()
            card.setObjectName("card")
            card.setMinimumHeight(92)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            cl = QVBoxLayout(card)
            value, cap = QLabel("—"), QLabel(caption)
            value.setObjectName("cardValue")
            cap.setObjectName("cardCaption")
            cap.setWordWrap(True)
            for lbl in (value, cap):
                lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                cl.addWidget(lbl)
            card.clicked.connect(lambda _=False, t=tab: self.tabs.setCurrentIndex(t) if t is not None
                                 else self.side_tabs.setCurrentIndex(1))
            row.addWidget(card)
            self.cards[key] = (value, cap)
        lay.addLayout(row)
        self.txt_overview = QTextBrowser()
        lay.addWidget(self.txt_overview, 1)
        return w

    def _set_card(self, key: str, value: str, state: str) -> None:
        lbl, _ = self.cards[key]
        lbl.setText(value)
        lbl.setStyleSheet(f"color: {TOKENS[self.mode][state]};")

    def _tab_kripke(self) -> QWidget:
        w = QSplitter(Qt.Orientation.Vertical)
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(8, 6, 8, 0)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Luồng"))
        self.cbo_flow = QComboBox()
        self.cbo_flow.setMinimumWidth(260)
        self.cbo_flow.currentIndexChanged.connect(lambda _: self._draw_model(*self.highlight))
        bar.addWidget(self.cbo_flow)
        bar.addStretch()
        tl.addLayout(bar)
        self.figure = Figure(figsize=(7, 4.5), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(340)
        tl.addWidget(self.canvas, 1)
        w.addWidget(top)
        self.tbl_ctl = _table(["Thuộc tính", "Kết quả", "Phản ví dụ"])
        self.tbl_ctl.itemSelectionChanged.connect(self._on_ctl_selected)
        w.addWidget(self.tbl_ctl)
        w.setSizes([560, 220])
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
        self.tbl_mem.itemSelectionChanged.connect(self._on_mem_selected)
        lay.addWidget(self.tbl_mem, 2)
        return w

    def _tab_smt(self) -> QWidget:
        w = QSplitter(Qt.Orientation.Vertical)
        self.tbl_bmc = _table(["Thuộc tính (BMC)", "Kết luận", "k", "CT", "Phản ví dụ"])
        self.tbl_bmc.itemSelectionChanged.connect(self._on_bmc_selected)
        self.tbl_smt = _table(["Kiểm tra", "Tràn int32", "Model", "Wrap 32-bit", "Sau vá"])
        self.tbl_smt.itemSelectionChanged.connect(self._on_smt_selected)
        self.tbl_ast = _table(["Hàm", "Bản", "McCabe", "Lồng", "Điều kiện"])
        for t in (self.tbl_bmc, self.tbl_smt, self.tbl_ast):
            w.addWidget(t)
        return w

    def _tab_fuzz(self) -> QWidget:
        w = QSplitter(Qt.Orientation.Vertical)
        w.setChildrenCollapsible(False)
        self.tbl_fuzz = _table(["Hàm", "Bản", "Chiến lược", "Lần thử", "Lỗi", "Lần đầu", "Input", "Loại"])
        self.tbl_fuzz.itemSelectionChanged.connect(self._on_fuzz_selected)
        w.addWidget(self.tbl_fuzz)
        self.tbl_state_fuzz = _table(["Fuzz chuỗi trạng thái", "Độ sâu", "Đường đi", "Phủ State", "Phủ Chuyển tiếp", "Lỗi / Crash"])
        self.tbl_state_fuzz.itemSelectionChanged.connect(self._on_state_fuzz_selected)
        w.addWidget(self.tbl_state_fuzz)
        w.setSizes([320, 240])
        return w

    def _tab_cwe(self) -> QWidget:
        self.tbl_cwe = _table(["CWE", "Vị trí", "Mức", "Trạng thái", "v0", "v1", "Công cụ"])
        self.tbl_cwe.itemSelectionChanged.connect(self._on_cwe_selected)
        return self.tbl_cwe

    # ------------------------------------------------------------------ helpers
    def _color(self, key: str) -> QColor:
        return QColor(TOKENS[self.mode][key])

    def _set_step(self, key: str, state: str, count: int | None = None) -> None:
        dot = {"idle": "idle", "pass": "pass", "fail": "fail", "run": "warn"}[state]
        idx, title = STEPS[key]
        self.tabs.setTabIcon(idx, _dot_icon(TOKENS[self.mode][dot]))
        self.tabs.setTabText(idx, f"{title}  {count}" if count else title)

    def _reset_steps(self) -> None:
        for key in STEPS:
            self._set_step(key, "idle")
        for key in CARDS:
            self._set_card(key, "—", "muted")
        self.txt_overview.setMarkdown(
            "### Chưa có kết quả\n\nChỉnh **⚙ tham số** nếu cần rồi bấm **▶ Chạy pipeline**. "
            "Sau khi chạy, trang này tóm tắt kết quả 4 chương và bảng trước/sau (v0 → v1); "
            "bấm vào một thẻ để mở chương tương ứng.")

    def _fill(self, table: QTableWidget, rows: list[list[object]], status_col: int | None = None) -> None:
        table.setRowCount(0)
        for r, row in enumerate(rows):
            table.insertRow(r)
            for c, value in enumerate(row):
                item = QTableWidgetItem("" if value is None else str(value))
                if c == status_col:
                    tone = _tone(str(value))
                    if tone:
                        item.setForeground(self._color(tone))
                table.setItem(r, c, item)

    def _inspect(self, content: str | None) -> None:
        self.inspector.setHtml(content or "")
        self.ai_box.setVisible(False)
        self.btn_ai.setEnabled(self.ai_cfg.enabled and bool(content) and self.ai_thread is None)

    def _ask_ai(self) -> None:
        spec = f"Đặc tả: {self.spec.name}. {self.spec.description}\n\n" if self.spec else ""
        context = spec + self.inspector.toPlainText()
        self.ai_box.setVisible(True)
        if context in self.ai_cache:
            self._on_ai_done(context, self.ai_cache[context])
            return
        self.ai_box.setMarkdown(f"_Đang hỏi model `{self.ai_cfg.model}`…_")
        self.btn_ai.setEnabled(False)
        self.ai_thread = QThread()
        self.ai_worker = AIWorker(self.ai_cfg, context)
        self.ai_worker.moveToThread(self.ai_thread)
        self.ai_thread.started.connect(self.ai_worker.run)
        self.ai_worker.finished.connect(self._on_ai_done)
        self.ai_worker.failed.connect(self._on_ai_failed)
        self.ai_worker.finished.connect(self.ai_thread.quit)
        self.ai_worker.failed.connect(self.ai_thread.quit)
        self.ai_thread.finished.connect(self._on_ai_thread_finished)
        self.ai_thread.start()

    def _on_ai_thread_finished(self) -> None:
        self.ai_thread = None
        self.btn_ai.setEnabled(self.ai_cfg.enabled and bool(self.inspector.toPlainText()))

    def _on_ai_done(self, context: str, answer: str) -> None:
        self.ai_cache[context] = answer
        self.ai_box.setMarkdown(f"**Diễn giải bởi AI ({self.ai_cfg.model}), không phải bằng chứng.** "
                                f"Kết luận chính thức là phần phía trên.\n\n{answer}")

    def _on_ai_failed(self, error: str) -> None:
        self.ai_box.setMarkdown(f"**Không gọi được AI.**\n\n{error}")

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _draw_model(self, violations: list[str] | None = None, path: list[str] | None = None) -> None:
        self.highlight = (violations, path)
        if self.model:
            self.model.draw_to_figure(self.figure, highlight_violations=violations, highlight_path=path,
                                      dark=self.mode == "dark", only=self.cbo_flow.currentData())
        else:
            self.figure.clear()
        self.canvas.draw()

    # ------------------------------------------------------------------ spec loading
    def _populate_specs(self) -> None:
        self.cbo_spec.blockSignals(True)
        for folder in SPEC_DIRS:
            for f in sorted(folder.glob("*.xlsx")) + sorted(folder.glob("*.json")):
                self.cbo_spec.addItem(self._spec_label(f), str(f))
        self.cbo_spec.blockSignals(False)
        idx = self.cbo_spec.findData(str(DEFAULT_SPEC))
        self.cbo_spec.setCurrentIndex(max(idx, 0))
        self.cbo_spec.blockSignals(False)
        self._on_spec_changed()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chọn đặc tả", str(BASE_DIR), "Đặc tả (*.json *.xlsx)")
        if path:
            self.cbo_spec.addItem(self._spec_label(Path(path)), path)
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
        if hasattr(self, "tbl_state_fuzz"):
            self.tbl_state_fuzz.setRowCount(0)
        self.txt_report.clear()
        s = self.spec
        sm = s.state_machine
        self.lbl_spec.setText(f"<b>{s.name}</b><br>{len(s.requirements)} yêu cầu · "
                              f"{len(sm.states) if sm else 0} trạng thái · {len(s.functions)} hàm · "
                              f"{len(s.arithmetic_checks)} kiểm tra số học · {len(s.test_cases)} test case")
        self.lst_req.clear()
        for r in s.requirements:
            item = QListWidgetItem(f"{r.id}  ·  {r.priority}  ·  {r.category}\n{r.text}")
            item.setToolTip(r.text)
            item.setData(Qt.ItemDataRole.UserRole, f"<h3>{r.id}</h3><p><b>{r.category} · {r.priority}</b></p><p>{r.text}</p>")
            self.lst_req.addItem(item)
        self._fill_test_cases()
        self.model = KripkeStructure.from_state_machine(sm, s.name) if sm and sm.states else None
        self.cbo_flow.blockSignals(True)
        self.cbo_flow.clear()
        if self.model:
            comps = sorted(self.model.components(), key=len, reverse=True)
            for comp in comps:
                self.cbo_flow.addItem(f"{comp[0]} → … ({len(comp)} trạng thái)", comp)
            if len(comps) > 1:
                self.cbo_flow.addItem("Tất cả luồng", None)
        self.cbo_flow.setEnabled(self.cbo_flow.count() > 1)
        self.cbo_flow.blockSignals(False)
        self._draw_model()
        self._fill(self.tbl_ctl, [[p, "chưa chạy", "Bấm ▶ Chạy pipeline để kiểm chứng"]
                                  for p in s.safety_properties])
        self._set_functions(generate_all_functions(s))
        self._inspect(f"<h3>{s.name}</h3><p>{s.description}</p>")
        self._log(f"Đã nạp {Path(path).name}: {s.summary()}")
        self.statusBar().showMessage(f"Đã nạp {s.name}. Bấm “Chạy pipeline”.")

    def _fill_test_cases(self) -> None:
        self.lst_tc.clear()
        results = {t.test_case.id: t for t in self.report.test_results} if self.report else {}
        for tc in self.spec.test_cases:
            res = results.get(tc.id)
            mark = {"PASS": "✓", "FAIL": "✗"}.get(res.status, "?") if res else "○"
            item = QListWidgetItem(f"{mark}  {tc.id}  {tc.title}")
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
        for key in STEPS:
            self._set_step(key, "run")
        bmc_depth = self._bmc_depth()
        fuzz_search = self.cbo_fuzz_search.currentData() if hasattr(self, "cbo_fuzz_search") else "bfs"
        self._log(f"Chạy pipeline (seed={self.spn_seed.value()}, fuzz={self.spn_budget.value()} [{fuzz_search.upper()}], "
                  f"BMC k={'auto' if bmc_depth is None else bmc_depth}, timeout={self.spn_timeout.value()}s)…")
        self.statusBar().showMessage("Đang chạy pipeline…")
        self.thread = QThread()
        self.worker = PipelineWorker(self.spec, self.spn_seed.value(), self.spn_budget.value(),
                                     bmc_depth=bmc_depth, sanitizer_timeout=self.spn_timeout.value(),
                                     fuzz_search=fuzz_search)
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
        self.btn_log.setChecked(True)
        self.statusBar().showMessage("Pipeline lỗi — xem log.")

    def _on_done(self, rep: PipelineReport) -> None:
        self.report = rep
        self.btn_export.setEnabled(True)
        k = rep.kripke
        ctl_fail = [r for r in (k.property_results if k else []) if r.status != "pass"]
        self._set_step("ch1", "idle" if not k else ("fail" if ctl_fail else "pass"), len(ctl_fail))
        v0_static = [f for (_, v), fs in rep.static.items() if v == "v0" for f in fs]
        v0_san = [s for s in rep.sanitizers if s.status == "detected" and s.version == "v0"]
        self._set_step("ch2", "fail" if v0_static or v0_san else "pass", len(v0_static) + len(v0_san))
        unsafe = [b for b in rep.bmc if b.status == "unsafe"]
        smt_open = [s for s in rep.smt if s.overflow_possible and s.patch_status != "unsat"]
        self._set_step("ch3", "fail" if unsafe or smt_open else "pass", len(unsafe) + len(smt_open))
        fuzz_hits = [r for r in rep.fuzz if r.found and r.version == "v0"]
        self._set_step("ch4", "fail" if fuzz_hits else "pass", len(fuzz_hits))
        self._set_step("cwe", "fail" if rep.audit.open_findings else "pass", len(rep.audit.confirmed))

        n_ctl = len(k.property_results) if k else 0
        passed = sum(t.status == "PASS" for t in rep.test_results)
        self._set_card("ctl", f"{len(ctl_fail)} / {n_ctl}", "fail" if ctl_fail else "pass")
        self._set_card("bmc", f"{len(unsafe)} / {len(rep.bmc)}", "fail" if unsafe else "pass")
        self._set_card("fuzz", f"{len(fuzz_hits)} / {sum(r.version == 'v0' for r in rep.fuzz)}",
                       "fail" if fuzz_hits else "pass")
        self._set_card("cwe", f"{len(rep.audit.confirmed)}", "fail" if rep.audit.open_findings else "pass")
        self._set_card("tc", f"{passed} / {len(rep.test_results)}",
                       "pass" if passed == len(rep.test_results) else "fail")
        k_text = "tự động (CT)" if rep.bmc and all(b.max_bound == b.completeness_threshold for b in rep.bmc) \
            else ", ".join(sorted({str(b.max_bound) for b in rep.bmc})) or "—"
        self.txt_overview.setMarkdown("\n".join(
            [f"### {rep.spec.name}: {len(rep.audit.open_findings)} lỗ hổng chưa vá", "",
             (f"Seed {rep.seed} · fuzz {rep.fuzz_budget}/chiến lược · BMC k = {k_text} · "
              f"chạy {sum(rep.timings.values()):.1f}s"), "", "#### Bảng trước / sau (v0 → v1)", ""]
            + before_after_table(rep)))

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
        for r in range(self.tbl_smt.rowCount()):  # the overflow column is a verdict too
            item = self.tbl_smt.item(r, 1)
            item.setForeground(self._color(_tone(item.text()) or "muted"))
        self._fill(self.tbl_ast, [[m.name, v, m.cyclomatic, m.nesting_depth, "; ".join(m.conditions) or "—"]
                                  for v, m in rep.metrics])

        # Ch.4
        self._fill(self.tbl_fuzz, [[r.function, r.version,
                                    f"{r.strategy} ({r.search_strategy.upper()})" if r.search_strategy != "none" else r.strategy,
                                    r.iterations,
                                    f"{r.hits}" + (" FAIL" if r.found else " PASS"), r.first_hit or "—",
                                    r.first_input or "—", r.finding or "—"] for r in rep.fuzz], status_col=4)
        if hasattr(self, "tbl_state_fuzz") and getattr(rep, "state_fuzz", None):
            self._fill(self.tbl_state_fuzz, [[r.strategy.upper(), r.max_depth, r.paths_explored,
                                              f"{r.state_coverage * 100:.1f}%", f"{r.transition_coverage * 100:.1f}%",
                                              f"{len(r.crashes)}" + (" FAIL" if r.has_crash else " PASS")]
                                             for r in rep.state_fuzz], status_col=5)

        # CWE
        self._fill(self.tbl_cwe, [[f.cwe_id, f.source_component, f.severity,
                                   f.status + ("" if f.fixed is None else (" · ĐÃ VÁ" if f.fixed else " · CHƯA VÁ")),
                                   f.before_text, f.after_text, ", ".join(f.tools)] for f in rep.audit.findings],
                   status_col=3)
        self.txt_report.setMarkdown(generate_markdown_report(rep).replace("![Kripke](figures/kripke.png)", ""))
        self._fill_test_cases()

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
            focus = (r.counterexample_path or r.violation_states or [None])[0]
            for i in range(self.cbo_flow.count()):
                states = self.cbo_flow.itemData(i)
                if focus and states and focus in states:
                    self.cbo_flow.blockSignals(True)
                    self.cbo_flow.setCurrentIndex(i)
                    self.cbo_flow.blockSignals(False)
                    break
            self._draw_model(r.violation_states, r.counterexample_path)
            warn = "".join(f"<p style='color:{TOKENS[self.mode]['warn']}'>⚠ {w}</p>" for w in r.warnings)
            details = r.details.replace("\n", "<br>")
            steps = "".join(
                f"<li>{st}" + (" <i>(vòng lặp bắt đầu)</i>" if i == r.loop_start else "") + "</li>"
                for i, st in enumerate(r.counterexample_path))
            trace = f"<p><b>Phản ví dụ ({len(r.counterexample_path)} bước)</b></p><ol>{steps}</ol>" if steps else ""
            diag = "".join(f"<li>{d}</li>" for d in diagnose(r, self.model))
            diag = f"<p><b>Chẩn đoán</b></p><ul>{diag}</ul>" if diag else ""
            reqs = related_requirements(r, self.spec)
            req = ("<p><b>Yêu cầu liên quan</b> (truy vết qua test case)</p><ul>"
                   + "".join(f"<li><b>{q.id}</b>: {q.text}</li>" for q in reqs) + "</ul>") if reqs else ""
            self._inspect(f"<h3>{r.formula or r.title}</h3><p><b>{STATUS_VI[r.status]}</b></p>"
                          f"{trace}{diag}{req}{warn}<p>{details}</p>")

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

    def _on_mem_selected(self) -> None:
        row = self.tbl_mem.currentRow()
        if not self.report or row < 0:
            return
        static = list(self.report.static.items())
        if row < len(static):
            (name, version), findings = static[row]
            self._show_code(name, version, [f.line for f in findings])
            items = "".join(f"<li><b>{f.rule}</b> ({f.cwe}, {f.severity}) dòng {f.line}: {html.escape(f.message)}"
                            f"<br><code>{html.escape(f.code)}</code></li>" for f in findings)
            self._inspect(f"<h3>{name} · {version} · Static scanner</h3>"
                          + (f"<ul>{items}</ul>" if items else "<p>0 finding.</p>"))
        elif row - len(static) < len(self.report.sanitizers):
            s = self.report.sanitizers[row - len(static)]
            self._show_code(s.function, s.version, [ln for _, _, ln in s.detections if ln])
            hits = "".join(f"<li>{kind} ({cwe}) dòng {ln}</li>" for kind, cwe, ln in s.detections)
            self._inspect(f"<h3>{s.function} · {s.version} · ASan/UBSan</h3><p><b>{s.status}</b> · "
                          f"mã thoát {s.returncode}</p><p><b>Input:</b> {html.escape(s.input_desc)}</p>"
                          + (f"<ul>{hits}</ul>" if hits else "") + (f"<p>{html.escape(s.note)}</p>" if s.note else "")
                          + f"<p><b>Lệnh:</b> <code>{html.escape(s.command)}</code></p>" + _raw(s.log))

    def _show_code(self, function: str, version: str, lines: list[int]) -> None:
        """Switch the code panes to `function` and highlight `lines` in the given version."""
        idx = next((i for i, gf in enumerate(self.report.functions) if gf.spec.name == function), -1)
        if idx < 0:
            return
        self.cbo_fn.blockSignals(True)
        self.cbo_fn.setCurrentIndex(idx)
        self.cbo_fn.blockSignals(False)
        gf = self.report.functions[idx]
        self.txt_v0.setPlainText(format_code_with_line_numbers(gf.code_vulnerable))
        self.txt_v1.setPlainText(format_code_with_line_numbers(gf.code_safe))
        box = self.txt_v0 if version == "v0" else self.txt_v1
        other = self.txt_v1 if box is self.txt_v0 else self.txt_v0
        other.setExtraSelections([])
        marks = []
        for ln in lines:
            block = box.document().findBlockByNumber(ln - 1)
            if not block.isValid():
                continue
            sel = QTextEdit.ExtraSelection()
            color = self._color("fail")
            color.setAlpha(70)
            sel.format.setBackground(color)
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            sel.cursor = QTextCursor(block)
            marks.append(sel)
        box.setExtraSelections(marks)
        if marks:
            box.setTextCursor(marks[0].cursor)
            box.centerCursor()

    def _on_bmc_selected(self) -> None:
        row = self.tbl_bmc.currentRow()
        if self.report and 0 <= row < len(self.report.bmc):
            b = self.report.bmc[row]
            self._inspect(f"<h3>BMC: {html.escape(b.property)}</h3><p><b>{BMC_VI[b.status]}</b></p>"
                          + _raw(b.to_text()))

    def _on_smt_selected(self) -> None:
        row = self.tbl_smt.currentRow()
        if self.report and 0 <= row < len(self.report.smt):
            s = self.report.smt[row]
            self._inspect(f"<h3>SMT: {s.name}</h3>" + _raw(s.details))

    def _on_fuzz_selected(self) -> None:
        row = self.tbl_fuzz.currentRow()
        if self.report and 0 <= row < len(self.report.fuzz):
            r = self.report.fuzz[row]
            strat = f"{r.strategy} ({r.search_strategy.upper()})" if r.search_strategy != "none" else r.strategy
            self._inspect(f"<h3>{r.function} · {r.version} · {strat}</h3>"
                          f"<p>{r.hits}/{r.iterations} lần thử gây lỗi, {r.seconds * 1000:.1f} ms</p>"
                          f"<p><b>Lần đầu:</b> {r.first_hit or '—'} · <b>Input:</b> {r.first_input or '—'} · "
                          f"<b>Loại:</b> {r.finding or '—'}</p>" + _raw("\n".join(r.events[:200])))

    def _on_state_fuzz_selected(self) -> None:
        row = self.tbl_state_fuzz.currentRow()
        if self.report and getattr(self.report, "state_fuzz", None) and 0 <= row < len(self.report.state_fuzz):
            r = self.report.state_fuzz[row]
            crashes_html = ""
            if r.crashes:
                items = "".join(f"<li><b>[{c.kind.upper()} · {c.cwe}]</b> tại <code>{c.state}</code>: {' -> '.join(c.path)}<br><i>{c.message}</i></li>"
                                for c in r.crashes)
                crashes_html = f"<p><b>Phát hiện {len(r.crashes)} Crash / Vi phạm:</b></p><ul>{items}</ul>"
            else:
                crashes_html = "<p style='color: #41cd52;'><b>✓ 0 crash: Không tìm thấy vi phạm bất biến nào trên các chuỗi trạng thái.</b></p>"
            events_text = "\n".join(r.events[:200]) if r.events else "Không có sự kiện bất thường."
            self._inspect(
                f"<h3>Fuzzing chuỗi trạng thái · {r.strategy.upper()}</h3>"
                f"<p><b>Độ sâu k:</b> {r.max_depth} · <b>Số chuỗi thử nghiệm:</b> {r.paths_explored} · "
                f"<b>Thời gian:</b> {r.seconds * 1000:.1f} ms</p>"
                f"<p><b>Độ phủ trạng thái:</b> {r.state_coverage * 100:.1f}% ({len(r.states_discovered)} states)<br>"
                f"<b>Độ phủ chuyển tiếp:</b> {r.transition_coverage * 100:.1f}% ({len(r.transitions_fired)} transitions)</p>"
                f"{crashes_html}"
                f"<p><b>Các trạng thái đã khám phá:</b><br><code>{', '.join(r.states_discovered)}</code></p>"
                + _raw(events_text)
            )

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
