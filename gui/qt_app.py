"""Modern Desktop Application GUI for Spec Verification Lab (Redesigned Ergonomic Studio Layout)."""
from __future__ import annotations

import sys
from pathlib import Path
import qdarktheme

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QComboBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QFrame,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from core.arithmetic_z3 import SMTCheckResult, check_all_arithmetic
from core.codegen import GeneratedFunction, format_code_with_line_numbers, generate_all_functions
from core.cwe_analyzer import SecurityAuditReport, analyze_security_vulnerabilities
from core.kripke import KripkeCheckReport, KripkeStructure
from core.reporter import export_report, generate_markdown_report
from core.spec_loader import Specification, load_specification


class ModernSpecVerificationLab(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Payment Security Verification Lab — Formal Methods & Vulnerability Analysis")
        self.resize(1400, 920)
        self.setMinimumSize(1100, 750)

        # Base paths
        self.base_dir = Path(__file__).resolve().parent.parent
        self.specs_json_dir = self.base_dir / "dataset" / "specs"
        self.specs_excel_dir = self.base_dir / "dataset" / "specs_excel"

        # Application state
        self.current_spec: Specification | None = None
        self.kripke_report: KripkeCheckReport | None = None
        self.generated_functions: list[GeneratedFunction] = []
        self.smt_results: list[SMTCheckResult] = []
        self.security_audit: SecurityAuditReport | None = None
        self.current_kripke_model: KripkeStructure | None = None
        self.is_dark_theme = True

        self._init_ui()
        self._load_initial_spec()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        # 1. Top Command Center Bar (Header + Pipeline Actions + Quick Select)
        top_bar = self._create_command_center()
        root_layout.addWidget(top_bar)

        # 2. Main Horizontal Splitter (Left Explorer vs Right Workspace)
        self.main_h_splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(self.main_h_splitter, stretch=1)

        # Left Panel (Spec Explorer & Requirements Card)
        left_panel = self._create_left_explorer()
        self.main_h_splitter.addWidget(left_panel)

        # Right Panel (Work Area + Bottom Output Console Dock)
        right_panel = self._create_right_workspace()
        self.main_h_splitter.addWidget(right_panel)

        # Set ratio: 320px left, remaining right
        self.main_h_splitter.setSizes([320, 1080])

        # 3. Modern Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Sẵn sàng. Đặc tả mặc định: payment_ecommerce.")

    # =========================================================================
    # 1. TOP COMMAND CENTER (Header, Quick Spec Selector, Pipeline Controls)
    # =========================================================================
    def _create_command_center(self) -> QWidget:
        bar = QFrame()
        bar.setFrameShape(QFrame.Shape.StyledPanel)
        bar.setStyleSheet(
            "QFrame { background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 4px; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # Brand / Title
        brand_lbl = QLabel("🛡️ PAYMENT SECURITY LAB")
        brand_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #4fc3f7; letter-spacing: 0.5px;")
        layout.addWidget(brand_lbl)

        # Separator line
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("color: rgba(255, 255, 255, 0.2);")
        layout.addWidget(sep1)

        # Quick Spec Switcher
        layout.addWidget(QLabel("Đặc tả hiện tại:"))
        self.cbo_quick_spec = QComboBox()
        self.cbo_quick_spec.setMinimumWidth(260)
        self.cbo_quick_spec.setStyleSheet("QComboBox { font-weight: bold; padding: 4px 8px; }")
        self.cbo_quick_spec.currentIndexChanged.connect(self._on_quick_spec_changed)
        layout.addWidget(self.cbo_quick_spec)

        btn_browse = QPushButton("📂 Duyệt file...")
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.clicked.connect(self._browse_file)
        layout.addWidget(btn_browse)

        layout.addStretch()

        # Pipeline Action Buttons
        self.btn_ch1 = QPushButton("1️⃣ Kripke (Ch1)")
        self.btn_ch1.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ch1.setStyleSheet("background-color: #0288d1; color: white; font-weight: bold; padding: 6px 12px; border-radius: 5px;")
        self.btn_ch1.clicked.connect(self._run_ch1)
        layout.addWidget(self.btn_ch1)

        self.btn_ch2 = QPushButton("2️⃣ Sinh mã (Ch2)")
        self.btn_ch2.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ch2.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 6px 12px; border-radius: 5px;")
        self.btn_ch2.clicked.connect(self._run_ch2)
        layout.addWidget(self.btn_ch2)

        self.btn_full = QPushButton("🚀 CHẠY TOÀN BỘ PIPELINE")
        self.btn_full.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_full.setStyleSheet(
            "background-color: #e65100; color: white; font-size: 12px; font-weight: bold; padding: 7px 16px; border-radius: 6px;"
        )
        self.btn_full.clicked.connect(self._run_full_pipeline)
        layout.addWidget(self.btn_full)

        self.btn_export = QPushButton("📑 Xuất Báo cáo")
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.setStyleSheet("background-color: #6a1b9a; color: white; font-weight: bold; padding: 6px 12px; border-radius: 5px;")
        self.btn_export.clicked.connect(self._export_report_dialog)
        layout.addWidget(self.btn_export)

        # Theme toggle
        self.btn_theme = QPushButton("☀️ Sáng/Tối")
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self._toggle_theme)
        layout.addWidget(self.btn_theme)

        return bar

    # =========================================================================
    # 2. LEFT PANEL: Spec Explorer & Requirements Card
    # =========================================================================
    def _create_left_explorer(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(8)

        # Project Specs Explorer
        grp_explorer = QGroupBox("📁 Quản lý Đặc tả (Project Specs):")
        grp_explorer_layout = QVBoxLayout(grp_explorer)
        grp_explorer_layout.setContentsMargins(6, 6, 6, 6)

        # Filter Tabs (Tất cả / Payment / Khác)
        self.tabs_spec_type = QTabWidget()
        self.tabs_spec_type.setStyleSheet("QTabBar::tab { padding: 4px 8px; font-size: 11px; }")

        # Tab: JSON
        self.list_specs = QListWidget()
        self.list_specs.setStyleSheet("QListWidget { font-size: 11px; }")
        self.list_specs.itemClicked.connect(self._on_spec_list_clicked)
        self.tabs_spec_type.addTab(self.list_specs, "JSON Specs")

        # Tab: Excel
        self.list_excel_specs = QListWidget()
        self.list_excel_specs.setStyleSheet("QListWidget { font-size: 11px; }")
        self.list_excel_specs.itemClicked.connect(self._on_excel_list_clicked)
        self.tabs_spec_type.addTab(self.list_excel_specs, "Excel Specs (.xlsx)")

        grp_explorer_layout.addWidget(self.tabs_spec_type)
        layout.addWidget(grp_explorer, stretch=1)

        self._populate_spec_lists()

        # Requirements Card (Bottom Left)
        grp_req = QGroupBox("📋 Thông tin & Yêu cầu an toàn:")
        grp_req_layout = QVBoxLayout(grp_req)
        grp_req_layout.setContentsMargins(6, 6, 6, 6)

        self.txt_requirements = QTextEdit()
        self.txt_requirements.setReadOnly(True)
        self.txt_requirements.setStyleSheet("font-family: 'DejaVu Sans', sans-serif; font-size: 11px;")
        grp_req_layout.addWidget(self.txt_requirements)
        layout.addWidget(grp_req, stretch=2)

        return widget

    def _populate_spec_lists(self):
        self.list_specs.clear()
        self.cbo_quick_spec.blockSignals(True)
        self.cbo_quick_spec.clear()

        # Populate JSON specs
        if self.specs_json_dir.exists():
            pay_files = sorted(self.specs_json_dir.glob("payment*.json"))
            other_files = sorted(f for f in self.specs_json_dir.glob("*.json") if not f.name.startswith("payment"))
            for f in pay_files:
                icon_text = "💳 " if "flawed" not in f.name else "⚠️ "
                item = QListWidgetItem(f"{icon_text}{f.name}")
                item.setData(Qt.ItemDataRole.UserRole, str(f))
                self.list_specs.addItem(item)
                self.cbo_quick_spec.addItem(f"{icon_text}{f.name}", str(f))

            for f in other_files:
                item = QListWidgetItem(f"📄 {f.name}")
                item.setData(Qt.ItemDataRole.UserRole, str(f))
                self.list_specs.addItem(item)
                self.cbo_quick_spec.addItem(f"📄 {f.name}", str(f))

        # Populate Excel specs
        self.list_excel_specs.clear()
        if self.specs_excel_dir.exists():
            pay_excel = sorted(self.specs_excel_dir.glob("payment*.xlsx"))
            other_excel = sorted(f for f in self.specs_excel_dir.glob("*.xlsx") if not f.name.startswith("payment"))
            for f in pay_excel + other_excel:
                item = QListWidgetItem(f"📊 {f.name}")
                item.setData(Qt.ItemDataRole.UserRole, str(f))
                self.list_excel_specs.addItem(item)

        self.cbo_quick_spec.blockSignals(False)

    # =========================================================================
    # 3. RIGHT PANEL: Work Area + Bottom Output Console Dock
    # =========================================================================
    def _create_right_workspace(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(6)

        # Vertical Splitter (Upper Work Area vs Lower Console Dock)
        self.work_splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(self.work_splitter, stretch=1)

        # Upper Area: Main Tabs (Kripke Canvas / Code Inspector / CWE Audit / Report)
        upper_tabs = self._create_upper_tabs()
        self.work_splitter.addWidget(upper_tabs)

        # Lower Area: Output Console Dock (Model Checking Log & SMT Solver Output)
        lower_dock = self._create_lower_console_dock()
        self.work_splitter.addWidget(lower_dock)

        # Set ratio: 65% upper, 35% lower dock
        self.work_splitter.setSizes([550, 270])

        return widget

    def _create_upper_tabs(self) -> QWidget:
        self.upper_tabs = QTabWidget()
        self.upper_tabs.setStyleSheet("QTabBar::tab { font-weight: bold; padding: 7px 16px; font-size: 11px; }")

        # Tab 1: Kripke State Canvas
        tab_kripke = self._create_tab_kripke_canvas()
        self.upper_tabs.addTab(tab_kripke, "🌐 Sơ đồ Trạng thái Kripke")

        # Tab 2: Code Inspector (Side-by-side)
        tab_code = self._create_tab_code_inspector()
        self.upper_tabs.addTab(tab_code, "💻 Trình duyệt Mã nguồn C / Python")

        # Tab 3: Security & CWE Audit
        tab_cwe = self._create_tab_cwe_audit()
        self.upper_tabs.addTab(tab_cwe, "🛡️ Bảng phân tích Lỗ hổng & CWE/CVE")

        # Tab 4: Full Integrated Report
        tab_report = self._create_tab_full_report()
        self.upper_tabs.addTab(tab_report, "📄 Toàn văn Báo cáo")

        return self.upper_tabs

    # ------------------ Tab 1: Kripke Canvas (Full Space) ------------------
    def _create_tab_kripke_canvas(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # Flow Selector Toolbar
        bar = QHBoxLayout()
        bar.addWidget(QLabel("<b>Luồng trạng thái:</b>"))
        self.cbo_flows = QComboBox()
        self.cbo_flows.setMinimumWidth(320)
        self.cbo_flows.currentIndexChanged.connect(self._on_flow_selected)
        bar.addWidget(self.cbo_flows)

        bar.addStretch()
        self.lbl_graph_info = QLabel("Khởi tạo: CREATED | 6 Trạng thái | 10 Chuyển tiếp")
        self.lbl_graph_info.setStyleSheet("color: #4fc3f7; font-weight: bold;")
        bar.addWidget(self.lbl_graph_info)
        layout.addLayout(bar)

        # Canvas with embedded Navigation Toolbar
        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, widget)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

        return widget

    # ------------------ Tab 2: Code Inspector (Side-by-side) ---------------
    def _create_tab_code_inspector(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("<b>Hàm được phân tích:</b>"))
        self.cbo_funcs = QComboBox()
        self.cbo_funcs.setMinimumWidth(280)
        self.cbo_funcs.currentIndexChanged.connect(self._on_func_selected)
        top_bar.addWidget(self.cbo_funcs)

        top_bar.addStretch()
        btn_copy = QPushButton("📋 Sao chép Mã an toàn")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.clicked.connect(self._copy_safe_code)
        top_bar.addWidget(btn_copy)
        layout.addLayout(top_bar)

        code_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(code_splitter, stretch=1)

        # Left: Vulnerable
        box_vuln = QGroupBox("⚠️ Mã nguồn ban đầu minh họa LỖ HỔNG (Vulnerable Code):")
        box_vuln_layout = QVBoxLayout(box_vuln)
        self.txt_code_vuln = QTextEdit()
        self.txt_code_vuln.setReadOnly(True)
        self.txt_code_vuln.setStyleSheet(
            "background-color: #2b1d1d; color: #ffcdd2; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px;"
        )
        box_vuln_layout.addWidget(self.txt_code_vuln)
        code_splitter.addWidget(box_vuln)

        # Right: Safe
        box_safe = QGroupBox("✅ Mã nguồn đã VÁ AN TOÀN (Hardened / Secure Code):")
        box_safe_layout = QVBoxLayout(box_safe)
        self.txt_code_safe = QTextEdit()
        self.txt_code_safe.setReadOnly(True)
        self.txt_code_safe.setStyleSheet(
            "background-color: #1b2e1b; color: #c8e6c9; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px;"
        )
        box_safe_layout.addWidget(self.txt_code_safe)
        code_splitter.addWidget(box_safe)

        code_splitter.setSizes([500, 500])
        return widget

    # ------------------ Tab 3: Security & CWE Audit -----------------------
    def _create_tab_cwe_audit(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        self.lbl_cwe_summary = QLabel("Chưa thực thi kiểm tra bảo mật.")
        self.lbl_cwe_summary.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffb74d;")
        layout.addWidget(self.lbl_cwe_summary)

        # Table
        self.table_cwe = QTableWidget()
        self.table_cwe.setColumnCount(6)
        self.table_cwe.setHorizontalHeaderLabels(["#", "Mức độ", "Mã CWE", "Tên lỗ hổng", "Thành phần", "Ví dụ CVE thực tế"])
        self.table_cwe.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_cwe.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_cwe.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_cwe.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_cwe.itemSelectionChanged.connect(self._on_cwe_selected)
        layout.addWidget(self.table_cwe, stretch=2)

        # Detail Box
        grp_detail = QGroupBox("Chi tiết lỗ hổng và Hướng dẫn khắc phục an toàn:")
        grp_detail_layout = QVBoxLayout(grp_detail)
        self.txt_cwe_detail = QTextEdit()
        self.txt_cwe_detail.setReadOnly(True)
        self.txt_cwe_detail.setStyleSheet("font-family: 'DejaVu Sans', sans-serif; font-size: 11px;")
        grp_detail_layout.addWidget(self.txt_cwe_detail)
        layout.addWidget(grp_detail, stretch=1)

        return widget

    # ------------------ Tab 4: Full Integrated Report ----------------------
    def _create_tab_full_report(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        bar = QHBoxLayout()
        btn_save = QPushButton("💾 Lưu báo cáo (.md)...")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._export_report_dialog)
        bar.addWidget(btn_save)

        btn_refresh = QPushButton("🔄 Cập nhật báo cáo")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self._refresh_report_view)
        bar.addWidget(btn_refresh)
        bar.addStretch()
        layout.addLayout(bar)

        self.txt_report = QTextEdit()
        self.txt_report.setReadOnly(True)
        self.txt_report.setStyleSheet("font-family: 'DejaVu Sans Mono', monospace; font-size: 11px;")
        layout.addWidget(self.txt_report, stretch=1)
        return widget

    # =========================================================================
    # 4. LOWER AREA: Output Console Dock (VS Code / IDE Terminal Style)
    # =========================================================================
    def _create_lower_console_dock(self) -> QWidget:
        box = QGroupBox("🖥️ Bảng điều khiển Kết quả (Verification Console Dock):")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)

        self.console_tabs = QTabWidget()
        self.console_tabs.setStyleSheet("QTabBar::tab { font-size: 11px; padding: 4px 12px; }")

        # Tab 1: Kripke Model Checking Output
        self.txt_kripke_log = QTextEdit()
        self.txt_kripke_log.setReadOnly(True)
        self.txt_kripke_log.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px; line-height: 1.4;"
        )
        self.console_tabs.addTab(self.txt_kripke_log, "📊 Kết quả Model Checking & CTL")

        # Tab 2: SMT Z3 Solver Output
        self.txt_smt = QTextEdit()
        self.txt_smt.setReadOnly(True)
        self.txt_smt.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px; line-height: 1.4;"
        )
        self.console_tabs.addTab(self.txt_smt, "🔢 Phân tích SMT Z3 (Integer Overflow)")

        layout.addWidget(self.console_tabs)
        return box

    # =========================================================================
    # EVENT HANDLERS & LOGIC
    # =========================================================================
    def _load_initial_spec(self):
        default_file = self.specs_json_dir / "payment_ecommerce_spec.json"
        if not default_file.exists():
            default_file = self.specs_json_dir / "auth_rate_limit_spec.json"
        if default_file.exists():
            self._load_file(default_file)
            # Sync dropdown and list selection
            for i in range(self.cbo_quick_spec.count()):
                if self.cbo_quick_spec.itemData(i) == str(default_file):
                    self.cbo_quick_spec.setCurrentIndex(i)
                    break

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file đặc tả (JSON hoặc Excel)", str(self.base_dir), "Spec Files (*.json *.xlsx *.xls)"
        )
        if path:
            self._load_file(Path(path))

    def _on_quick_spec_changed(self):
        filepath = self.cbo_quick_spec.currentData()
        if filepath and Path(filepath).exists():
            self._load_file(Path(filepath))

    def _on_spec_list_clicked(self, item: QListWidgetItem):
        filepath = item.data(Qt.ItemDataRole.UserRole)
        if filepath and Path(filepath).exists():
            self._load_file(Path(filepath))
            # Sync dropdown
            for i in range(self.cbo_quick_spec.count()):
                if self.cbo_quick_spec.itemData(i) == filepath:
                    self.cbo_quick_spec.blockSignals(True)
                    self.cbo_quick_spec.setCurrentIndex(i)
                    self.cbo_quick_spec.blockSignals(False)
                    break

    def _on_excel_list_clicked(self, item: QListWidgetItem):
        filepath = item.data(Qt.ItemDataRole.UserRole)
        if filepath and Path(filepath).exists():
            self._load_file(Path(filepath))

    def _load_file(self, filepath: Path):
        try:
            self.current_spec = load_specification(filepath)
            self.status_bar.showMessage(f"Đã nạp: {self.current_spec.name}")

            # Requirements
            self.txt_requirements.clear()
            self.txt_requirements.append(f"<b>[{self.current_spec.name}]</b>: {self.current_spec.description}\n")
            for req in self.current_spec.requirements:
                color = "#ef5350" if "HIGH" in req.priority else "#ffb74d"
                self.txt_requirements.append(
                    f"<font color='{color}'><b>[{req.priority}/{req.category}]</b></font> <b>{req.id}</b>: {req.text}"
                )

            # Flows
            self.cbo_flows.blockSignals(True)
            self.cbo_flows.clear()
            self.cbo_flows.addItem("Mô hình chính (Main Model)")
            if self.current_spec.additional_flows:
                for k in self.current_spec.additional_flows.keys():
                    self.cbo_flows.addItem(k)
            self.cbo_flows.blockSignals(False)

            # Functions combo
            self.cbo_funcs.blockSignals(True)
            self.cbo_funcs.clear()
            for fn in self.current_spec.functions:
                self.cbo_funcs.addItem(f"{fn.name} ({fn.language.upper()})")
            self.cbo_funcs.blockSignals(False)

            # Render initial diagram
            if self.current_spec.state_machine:
                num_st = len(self.current_spec.state_machine.states)
                num_tr = len(self.current_spec.state_machine.transitions)
                self.lbl_graph_info.setText(
                    f"Khởi tạo: {', '.join(self.current_spec.state_machine.initial)} | {num_st} Trạng thái | {num_tr} Chuyển tiếp"
                )
                self.current_kripke_model = KripkeStructure.from_state_machine(
                    self.current_spec.state_machine, self.current_spec.name
                )
                self.current_kripke_model.draw_to_figure(self.figure)
                self.canvas.draw()

            self.txt_kripke_log.setPlainText(
                f"Đã nạp đặc tả '{self.current_spec.name}'.\n"
                f"- Số trạng thái: {len(self.current_spec.state_machine.states) if self.current_spec.state_machine else 0}\n"
                f"- Số yêu cầu: {len(self.current_spec.requirements)}\n"
                f"- Số hàm sinh mã: {len(self.current_spec.functions)}\n"
                f"- Số kiểm tra số học Z3: {len(self.current_spec.arithmetic_checks)}\n\n"
                f"Bấm '1️⃣ Kripke' hoặc '🚀 CHẠY TOÀN BỘ PIPELINE' để bắt đầu."
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi đọc file", f"Không thể nạp đặc tả: {e}")

    def _on_flow_selected(self):
        if not self.current_spec:
            return
        selected = self.cbo_flows.currentText()
        if selected == "Mô hình chính (Main Model)":
            if self.current_spec.state_machine:
                self.current_kripke_model = KripkeStructure.from_state_machine(
                    self.current_spec.state_machine, self.current_spec.name
                )
        else:
            flow_sm = self.current_spec.additional_flows.get(selected)
            if flow_sm:
                self.current_kripke_model = KripkeStructure.from_state_machine(flow_sm, selected)

        if self.current_kripke_model:
            self.current_kripke_model.draw_to_figure(self.figure)
            self.canvas.draw()

    def _on_func_selected(self):
        if not self.generated_functions:
            return
        idx = self.cbo_funcs.currentIndex()
        if 0 <= idx < len(self.generated_functions):
            fn = self.generated_functions[idx]
            self.txt_code_vuln.setPlainText(format_code_with_line_numbers(fn.code_vulnerable))
            self.txt_code_safe.setPlainText(format_code_with_line_numbers(fn.code_safe))

    def _copy_safe_code(self):
        idx = self.cbo_funcs.currentIndex()
        if 0 <= idx < len(self.generated_functions):
            fn = self.generated_functions[idx]
            QApplication.clipboard().setText(fn.code_safe)
            QMessageBox.information(self, "Đã sao chép", f"Đã sao chép mã an toàn của hàm '{fn.spec.name}' vào clipboard!")

    # ------------------ Pipeline Execution ------------------
    def _run_ch1(self):
        if not self.current_spec or not self.current_spec.state_machine:
            return
        self.current_kripke_model = KripkeStructure.from_state_machine(
            self.current_spec.state_machine, self.current_spec.name
        )
        self.kripke_report = self.current_kripke_model.verify_all(
            self.current_spec.safety_properties, self.current_spec.mutual_exclusion
        )
        self.txt_kripke_log.setPlainText(self.kripke_report.summary_text)

        viols = []
        path = []
        for prop in self.kripke_report.property_results:
            if not prop.passed:
                viols.extend(prop.violation_states)
                if prop.counterexample_path:
                    path = prop.counterexample_path

        self.current_kripke_model.draw_to_figure(self.figure, highlight_violations=viols, highlight_path=path)
        self.canvas.draw()
        self.upper_tabs.setCurrentIndex(0)
        self.console_tabs.setCurrentIndex(0)
        self.status_bar.showMessage("Đã hoàn tất Kiểm chứng Kripke (Ch1).")

    def _run_ch2(self):
        if not self.current_spec:
            return
        self.generated_functions = generate_all_functions(self.current_spec)
        self._on_func_selected()
        self.upper_tabs.setCurrentIndex(1)
        self.status_bar.showMessage("Đã sinh mã nguồn C / Python (Ch2).")

    def _run_ch3(self):
        if not self.current_spec:
            return
        self.smt_results = check_all_arithmetic(self.current_spec.arithmetic_checks)
        self.txt_smt.clear()
        for r in self.smt_results:
            self.txt_smt.append(r.details + "\n")
        self.console_tabs.setCurrentIndex(1)
        self.status_bar.showMessage("Đã hoàn tất phân tích SMT / Z3 (Ch3).")

    def _run_ch4(self):
        if not self.current_spec:
            return
        self.security_audit = analyze_security_vulnerabilities(
            self.current_spec, self.kripke_report, self.smt_results
        )

        # Update Table
        self.table_cwe.setRowCount(0)
        for idx, f in enumerate(self.security_audit.findings, 1):
            row = self.table_cwe.rowCount()
            self.table_cwe.insertRow(row)

            item_idx = QTableWidgetItem(str(idx))
            item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_cwe.setItem(row, 0, item_idx)

            item_sev = QTableWidgetItem(f.severity)
            item_sev.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if f.severity == "CRITICAL":
                item_sev.setForeground(QColor("#e53935"))
            elif f.severity == "HIGH":
                item_sev.setForeground(QColor("#fb8c00"))
            else:
                item_sev.setForeground(QColor("#1e88e5"))
            self.table_cwe.setItem(row, 1, item_sev)

            self.table_cwe.setItem(row, 2, QTableWidgetItem(f.cwe_id))
            self.table_cwe.setItem(row, 3, QTableWidgetItem(f.cwe_name))
            self.table_cwe.setItem(row, 4, QTableWidgetItem(f.source_component))
            self.table_cwe.setItem(row, 5, QTableWidgetItem(f.illustrative_cve))

        self.lbl_cwe_summary.setText(
            f"Tổng số lỗ hổng phát hiện: {self.security_audit.total_findings} | "
            f"CRITICAL: {self.security_audit.critical_count} | "
            f"HIGH: {self.security_audit.high_count} | "
            f"MEDIUM: {self.security_audit.medium_count}"
        )

        if self.security_audit.findings:
            self.table_cwe.selectRow(0)
        self.upper_tabs.setCurrentIndex(2)
        self.status_bar.showMessage("Đã hoàn tất phân tích CWE/CVE (Ch4).")

    def _run_full_pipeline(self):
        if not self.current_spec:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nạp đặc tả trước!")
            return

        self._run_ch1()
        self._run_ch2()
        self._run_ch3()
        self._run_ch4()
        self._refresh_report_view()

        QMessageBox.information(
            self,
            "Hoàn tất Pipeline",
            f"Đã chạy toàn bộ quy trình cho đặc tả '{self.current_spec.name}'!\n\n"
            f"- Kiểm chứng Kripke: {'HỢP LỆ (SAFE)' if (not self.kripke_report or self.kripke_report.is_valid) else 'PHÁT HIỆN LỖI (UNSAFE)'}\n"
            f"- Hàm sinh mã: {len(self.generated_functions)}\n"
            f"- Kiểm tra Z3 SMT: {len(self.smt_results)}\n"
            f"- Lỗ hổng CWE phát hiện: {self.security_audit.total_findings if self.security_audit else 0}",
        )

    def _on_cwe_selected(self):
        selected_rows = self.table_cwe.selectionModel().selectedRows()
        if not selected_rows or not self.security_audit:
            return
        row = selected_rows[0].row()
        if 0 <= row < len(self.security_audit.findings):
            f = self.security_audit.findings[row]
            self.txt_cwe_detail.setHtml(
                f"<h3 style='color: #4fc3f7;'>[{f.severity}] {f.cwe_id} — {f.cwe_name}</h3>"
                f"<p><b>Thành phần:</b> <code>{f.source_component}</code></p>"
                f"<p><b>MÔ TẢ LỖ HỔNG:</b><br>{f.description}</p>"
                f"<p><b>VÍ DỤ CVE THỰC TẾ:</b><br>{f.illustrative_cve}</p>"
                f"<p style='color: #81c784;'><b>HƯỚNG DẪN KHẮC PHỤC:</b><br>{f.remediation}</p>"
            )

    def _refresh_report_view(self):
        if not self.current_spec:
            return
        report_text = generate_markdown_report(
            self.current_spec,
            self.kripke_report,
            self.generated_functions,
            self.smt_results,
            self.security_audit
            or analyze_security_vulnerabilities(self.current_spec, self.kripke_report, self.smt_results),
        )
        self.txt_report.setPlainText(report_text)

    def _export_report_dialog(self):
        if not self.current_spec:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nạp đặc tả trước khi xuất báo cáo!")
            return

        if not self.security_audit:
            self._run_full_pipeline()

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu báo cáo kiểm chứng",
            str(self.base_dir / f"BaoCao_{self.current_spec.name}.md"),
            "Markdown Files (*.md);;HTML Files (*.html);;All Files (*.*)",
        )
        if path:
            try:
                export_report(
                    path,
                    self.current_spec,
                    self.kripke_report,
                    self.generated_functions,
                    self.smt_results,
                    self.security_audit,
                )
                QMessageBox.information(self, "Thành công", f"Báo cáo đã được lưu tại:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể lưu báo cáo: {e}")

    def _toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        theme = "dark" if self.is_dark_theme else "light"
        qdarktheme.setup_theme(theme)
        if self.current_kripke_model:
            facecolor = "#202124" if self.is_dark_theme else "#ffffff"
            self.figure.patch.set_facecolor(facecolor)
            self.current_kripke_model.draw_to_figure(self.figure)
            self.canvas.draw()


def main():
    app = QApplication(sys.argv)
    qdarktheme.setup_theme("dark")

    font = QFont("DejaVu Sans", 10)
    app.setFont(font)

    window = ModernSpecVerificationLab()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
