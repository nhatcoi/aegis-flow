"""Modern Desktop Application GUI for Spec Verification Lab using PyQt6 and qdarktheme."""
from __future__ import annotations

import sys
from pathlib import Path
import qdarktheme

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QColor, QKeySequence, QShortcut
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
    QTextEdit,
    QComboBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QToolBar,
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
        self.setWindowTitle("Spec Verification Lab — Đặc tả → Kripke → Sinh mã → CWE/CVE")
        self.resize(1360, 900)
        self.setMinimumSize(1080, 720)

        # Base paths
        self.base_dir = Path(__file__).resolve().parent.parent
        self.specs_json_dir = self.base_dir / "dataset" / "specs"
        self.specs_excel_dir = self.base_dir / "dataset" / "specs_excel"

        # State
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
        # Central widget and root layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # Top Bar (Header & Actions)
        top_bar = self._create_top_bar()
        root_layout.addWidget(top_bar)

        # Main Splitter (Left Sidebar vs Right Notebook)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(self.main_splitter, stretch=1)

        # Left Sidebar (Width ~ 380px)
        sidebar = self._create_sidebar()
        self.main_splitter.addWidget(sidebar)

        # Right Content (Tab Notebook)
        content_tabs = self._create_content_tabs()
        self.main_splitter.addWidget(content_tabs)

        # Set initial splitter proportions
        self.main_splitter.setSizes([380, 980])

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Sẵn sàng. Vui lòng chọn đặc tả và thực thi Pipeline.")

    def _create_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFrameShape(QFrame.Shape.StyledPanel)
        bar.setStyleSheet("QFrame { background-color: rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 4px; }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)

        title_lbl = QLabel("🛡️ SPEC VERIFICATION LAB — AN TOÀN PHẦN MỀM (SOFTWARE SECURITY)")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #4fc3f7;")
        layout.addWidget(title_lbl)

        layout.addStretch()

        # Theme toggle button
        self.btn_theme = QPushButton("☀️ Giao diện Sáng/Tối")
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self._toggle_theme)
        layout.addWidget(self.btn_theme)

        # Quick file open
        btn_open = QPushButton("📂 Mở file...")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(self._browse_file)
        layout.addWidget(btn_open)

        return bar

    def _create_sidebar(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # 1. JSON Specs Box
        grp_json = QGroupBox("📁 Bộ đặc tả mẫu JSON (dataset/specs):")
        grp_json_layout = QVBoxLayout(grp_json)
        grp_json_layout.setContentsMargins(6, 6, 6, 6)

        self.list_json = QListWidget()
        self.list_json.setStyleSheet("QListWidget { font-size: 11px; }")
        self.list_json.itemDoubleClicked.connect(self._on_json_selected)
        if self.specs_json_dir.exists():
            pay_f = sorted(self.specs_json_dir.glob("payment*.json"))
            oth_f = sorted(f for f in self.specs_json_dir.glob("*.json") if not f.name.startswith("payment"))
            for f in pay_f + oth_f:
                self.list_json.addItem(f.name)

        grp_json_layout.addWidget(self.list_json)
        btn_load_json = QPushButton("Nạp đặc tả JSON đã chọn")
        btn_load_json.setStyleSheet("font-weight: bold;")
        btn_load_json.clicked.connect(self._on_json_selected)
        grp_json_layout.addWidget(btn_load_json)
        layout.addWidget(grp_json)

        # 2. Excel Specs Box
        grp_excel = QGroupBox("📊 Bộ đặc tả mẫu Excel (dataset/specs_excel):")
        grp_excel_layout = QVBoxLayout(grp_excel)
        grp_excel_layout.setContentsMargins(6, 6, 6, 6)

        self.list_excel = QListWidget()
        self.list_excel.setMaximumHeight(85)
        self.list_excel.setStyleSheet("QListWidget { font-size: 11px; }")
        self.list_excel.itemDoubleClicked.connect(self._on_excel_selected)
        if self.specs_excel_dir.exists():
            pay_fx = sorted(self.specs_excel_dir.glob("payment*.xlsx"))
            oth_fx = sorted(f for f in self.specs_excel_dir.glob("*.xlsx") if not f.name.startswith("payment"))
            for f in pay_fx + oth_fx:
                self.list_excel.addItem(f.name)

        grp_excel_layout.addWidget(self.list_excel)
        btn_load_excel = QPushButton("Nạp đặc tả Excel đã chọn")
        btn_load_excel.clicked.connect(self._on_excel_selected)
        grp_excel_layout.addWidget(btn_load_excel)
        layout.addWidget(grp_excel)

        # 3. Requirements box
        grp_req = QGroupBox("📋 Yêu cầu an toàn (Requirements):")
        grp_req_layout = QVBoxLayout(grp_req)
        grp_req_layout.setContentsMargins(6, 6, 6, 6)

        self.txt_requirements = QTextEdit()
        self.txt_requirements.setReadOnly(True)
        self.txt_requirements.setStyleSheet("font-family: 'DejaVu Sans', sans-serif; font-size: 11px;")
        grp_req_layout.addWidget(self.txt_requirements)
        layout.addWidget(grp_req, stretch=1)

        # 4. Pipeline Action Buttons
        grp_actions = QGroupBox("⚡ Quy trình thực thi (Pipeline):")
        grp_actions_layout = QVBoxLayout(grp_actions)
        grp_actions_layout.setSpacing(6)

        self.btn_ch1 = QPushButton("1) Sinh Kripke + Kiểm chứng (Ch1)")
        self.btn_ch1.setStyleSheet("background-color: #1976d2; color: white; font-weight: bold; padding: 7px; border-radius: 4px;")
        self.btn_ch1.clicked.connect(self._run_ch1)
        grp_actions_layout.addWidget(self.btn_ch1)

        self.btn_ch2 = QPushButton("2) Sinh mã C/Python từ đặc tả (Ch2)")
        self.btn_ch2.setStyleSheet("background-color: #388e3c; color: white; font-weight: bold; padding: 7px; border-radius: 4px;")
        self.btn_ch2.clicked.connect(self._run_ch2)
        grp_actions_layout.addWidget(self.btn_ch2)

        self.btn_full = QPushButton("🚀 3) Chạy TOÀN BỘ Pipeline (Ch1-4)")
        self.btn_full.setStyleSheet(
            "background-color: #f57c00; color: white; font-size: 13px; font-weight: bold; padding: 10px; border-radius: 6px;"
        )
        self.btn_full.clicked.connect(self._run_full_pipeline)
        grp_actions_layout.addWidget(self.btn_full)

        self.btn_export = QPushButton("📑 Xuất Báo cáo Tích hợp (.md/.html)")
        self.btn_export.setStyleSheet("background-color: #7b1fa2; color: white; font-weight: bold; padding: 7px; border-radius: 4px;")
        self.btn_export.clicked.connect(self._export_report_dialog)
        grp_actions_layout.addWidget(self.btn_export)

        layout.addWidget(grp_actions)
        return widget

    def _create_content_tabs(self) -> QWidget:
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { font-weight: bold; padding: 8px 16px; }")

        # Tab 1: Kripke & Graph
        tab_kripke = self._create_tab_kripke()
        self.tabs.addTab(tab_kripke, "🌐 1. Kripke & Kiểm chứng")

        # Tab 2: Codegen
        tab_code = self._create_tab_codegen()
        self.tabs.addTab(tab_code, "💻 2. Mã nguồn sinh ra")

        # Tab 3: Z3 SMT
        tab_smt = self._create_tab_smt()
        self.tabs.addTab(tab_smt, "🔢 3. Kiểm tra số học (Z3)")

        # Tab 4: CWE/CVE
        tab_cwe = self._create_tab_cwe()
        self.tabs.addTab(tab_cwe, "🛡️ 4. Phân tích CWE/CVE")

        # Tab 5: Report
        tab_report = self._create_tab_report()
        self.tabs.addTab(tab_report, "📄 5. Báo cáo Tích hợp")

        return self.tabs

    # ------------------ Tab 1: Kripke ------------------
    def _create_tab_kripke(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # Log Top
        top_frame = QGroupBox("Kết quả kiểm chứng hình thức (Model Checking Log):")
        top_layout = QVBoxLayout(top_frame)
        self.txt_kripke_log = QTextEdit()
        self.txt_kripke_log.setReadOnly(True)
        self.txt_kripke_log.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px;"
        )
        top_layout.addWidget(self.txt_kripke_log)
        splitter.addWidget(top_frame)

        # Graph Bottom
        bottom_frame = QGroupBox("Sơ đồ chuyển trạng thái Kripke:")
        bottom_layout = QVBoxLayout(bottom_frame)

        # Selector bar
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Chọn luồng trạng thái hiển thị:"))
        self.cbo_flows = QComboBox()
        self.cbo_flows.setMinimumWidth(300)
        self.cbo_flows.currentIndexChanged.connect(self._on_flow_selected)
        bar.addWidget(self.cbo_flows)
        bar.addStretch()
        bottom_layout.addLayout(bar)

        # Canvas
        self.figure = Figure(figsize=(7, 4.5), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, bottom_frame)
        bottom_layout.addWidget(self.toolbar)
        bottom_layout.addWidget(self.canvas, stretch=1)

        splitter.addWidget(bottom_frame)
        splitter.setSizes([260, 500])
        return widget

    # ------------------ Tab 2: Codegen ------------------
    def _create_tab_codegen(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Chọn hàm cần xem:"))
        self.cbo_funcs = QComboBox()
        self.cbo_funcs.setMinimumWidth(280)
        self.cbo_funcs.currentIndexChanged.connect(self._on_func_selected)
        top_bar.addWidget(self.cbo_funcs)

        top_bar.addStretch()
        btn_copy = QPushButton("📋 Sao chép mã an toàn")
        btn_copy.clicked.connect(self._copy_safe_code)
        top_bar.addWidget(btn_copy)
        layout.addLayout(top_bar)

        code_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(code_splitter, stretch=1)

        # Vulnerable
        box_vuln = QGroupBox("⚠️ Mã nguồn minh họa LỖ HỔNG (Vulnerable Code):")
        box_vuln_layout = QVBoxLayout(box_vuln)
        self.txt_code_vuln = QTextEdit()
        self.txt_code_vuln.setReadOnly(True)
        self.txt_code_vuln.setStyleSheet(
            "background-color: #2b1d1d; color: #ffcdd2; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px;"
        )
        box_vuln_layout.addWidget(self.txt_code_vuln)
        code_splitter.addWidget(box_vuln)

        # Safe
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

    # ------------------ Tab 3: SMT ------------------
    def _create_tab_smt(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        grp = QGroupBox("Kết quả phân tích điều kiện & Tràn số nguyên 32-bit (Z3 SMT Solver):")
        grp_layout = QVBoxLayout(grp)

        self.txt_smt = QTextEdit()
        self.txt_smt.setReadOnly(True)
        self.txt_smt.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; font-family: 'DejaVu Sans Mono', monospace; font-size: 12px; line-height: 1.5;"
        )
        grp_layout.addWidget(self.txt_smt)
        layout.addWidget(grp)
        return widget

    # ------------------ Tab 4: CWE/CVE ------------------
    def _create_tab_cwe(self) -> QWidget:
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

    # ------------------ Tab 5: Report ------------------
    def _create_tab_report(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        bar = QHBoxLayout()
        btn_save = QPushButton("💾 Lưu báo cáo ra file...")
        btn_save.clicked.connect(self._export_report_dialog)
        bar.addWidget(btn_save)

        btn_refresh = QPushButton("🔄 Làm mới báo cáo")
        btn_refresh.clicked.connect(self._refresh_report_view)
        bar.addWidget(btn_refresh)
        bar.addStretch()
        layout.addLayout(bar)

        self.txt_report = QTextEdit()
        self.txt_report.setReadOnly(True)
        self.txt_report.setStyleSheet("font-family: 'DejaVu Sans Mono', monospace; font-size: 11px;")
        layout.addWidget(self.txt_report, stretch=1)
        return widget

    # ------------------ Theme Toggle ------------------
    def _toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        theme = "dark" if self.is_dark_theme else "light"
        qdarktheme.setup_theme(theme)
        # Re-render figure to match background
        if self.current_kripke_model:
            facecolor = "#202124" if self.is_dark_theme else "#ffffff"
            self.figure.patch.set_facecolor(facecolor)
            self.current_kripke_model.draw_to_figure(self.figure)
            self.canvas.draw()

    # ------------------ Loading Logic ------------------
    def _load_initial_spec(self):
        default_file = self.specs_json_dir / "payment_ecommerce_spec.json"
        if not default_file.exists():
            default_file = self.specs_json_dir / "auth_rate_limit_spec.json"
        if default_file.exists():
            self._load_file(default_file)
            # Select in listbox
            for i in range(self.list_json.count()):
                if self.list_json.item(i).text() == default_file.name:
                    self.list_json.setCurrentRow(i)
                    break

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file đặc tả (JSON hoặc Excel)", str(self.base_dir), "Spec Files (*.json *.xlsx *.xls)"
        )
        if path:
            self._load_file(Path(path))

    def _on_json_selected(self):
        item = self.list_json.currentItem()
        if not item:
            return
        self._load_file(self.specs_json_dir / item.text())

    def _on_excel_selected(self):
        item = self.list_excel.currentItem()
        if not item:
            return
        self._load_file(self.specs_excel_dir / item.text())

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
                f"- Số kiểm tra số học: {len(self.current_spec.arithmetic_checks)}\n\n"
                f"Bấm '1) Sinh Kripke + Kiểm chứng' hoặc '3) Chạy TOÀN BỘ Pipeline' để bắt đầu."
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
        self.tabs.setCurrentIndex(0)
        self.status_bar.showMessage("Đã hoàn tất Kiểm chứng Kripke (Ch1).")

    def _run_ch2(self):
        if not self.current_spec:
            return
        self.generated_functions = generate_all_functions(self.current_spec)
        self._on_func_selected()
        self.tabs.setCurrentIndex(1)
        self.status_bar.showMessage("Đã sinh mã nguồn C / Python (Ch2).")

    def _run_ch3(self):
        if not self.current_spec:
            return
        self.smt_results = check_all_arithmetic(self.current_spec.arithmetic_checks)
        self.txt_smt.clear()
        for r in self.smt_results:
            self.txt_smt.append(r.details + "\n")
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
            f"Tổng số lỗ hổng: {self.security_audit.total_findings} | "
            f"CRITICAL: {self.security_audit.critical_count} | "
            f"HIGH: {self.security_audit.high_count} | "
            f"MEDIUM: {self.security_audit.medium_count}"
        )

        if self.security_audit.findings:
            self.table_cwe.selectRow(0)
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


def main():
    app = QApplication(sys.argv)
    # Apply modern theme
    qdarktheme.setup_theme("dark")

    # Set application font
    font = QFont("DejaVu Sans", 10)
    app.setFont(font)

    window = ModernSpecVerificationLab()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
