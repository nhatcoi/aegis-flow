"""Desktop Application GUI for Spec Verification Lab using Tkinter, ttk, and Matplotlib."""
from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from core.arithmetic_z3 import SMTCheckResult, check_all_arithmetic
from core.codegen import GeneratedFunction, format_code_with_line_numbers, generate_all_functions
from core.cwe_analyzer import SecurityAuditReport, analyze_security_vulnerabilities
from core.kripke import KripkeCheckReport, KripkeStructure
from core.reporter import export_report, generate_markdown_report
from core.spec_loader import Specification, load_specification


class SpecVerificationLabApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Spec Verification Lab — Đặc tả → Kripke → Sinh mã → CWE/CVE")
        self.root.geometry("1280x860")
        self.root.minsize(1024, 720)

        # Application state
        self.current_spec: Specification | None = None
        self.kripke_report: KripkeCheckReport | None = None
        self.generated_functions: list[GeneratedFunction] = []
        self.smt_results: list[SMTCheckResult] = []
        self.security_audit: SecurityAuditReport | None = None
        self.current_kripke_model: KripkeStructure | None = None

        # Base directories
        self.base_dir = Path(__file__).resolve().parent.parent
        self.specs_json_dir = self.base_dir / "dataset" / "specs"
        self.specs_excel_dir = self.base_dir / "dataset" / "specs_excel"

        self._apply_theme()
        self._build_menu()
        self._build_ui()
        self._load_default_spec()

    def _apply_theme(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", font=("DejaVu Sans", 9))
        style.configure("TButton", font=("DejaVu Sans", 9, "bold"), padding=5)
        style.configure("Header.TLabel", font=("DejaVu Sans", 10, "bold"))
        style.configure("Title.TLabel", font=("DejaVu Sans", 12, "bold"), foreground="#1565c0")
        style.configure("Status.TLabel", font=("DejaVu Sans", 9))

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tệp (File)", menu=file_menu)
        file_menu.add_command(label="Nạp từ file JSON...", command=self._browse_json_file)
        file_menu.add_command(label="Nạp từ file Excel (.xlsx)...", command=self._browse_excel_file)
        file_menu.add_separator()
        file_menu.add_command(label="Xuất báo cáo tích hợp...", command=self._export_report_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Thoát", command=self.root.quit)

        # Action menu
        action_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Quy trình (Pipeline)", menu=action_menu)
        action_menu.add_command(label="1) Sinh Kripke + Kiểm chứng (Ch1)", command=self._run_ch1)
        action_menu.add_command(label="2) Sinh mã C/Python từ đặc tả (Ch2)", command=self._run_ch2)
        action_menu.add_command(label="3) Chạy TOÀN BỘ Pipeline (Ch1-4)", command=self._run_full_pipeline)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Trợ giúp", menu=help_menu)
        help_menu.add_command(
            label="Giới thiệu",
            command=lambda: messagebox.showinfo(
                "Giới thiệu",
                "Spec Verification Lab\nPhần mềm thực hành môn An Toàn Phần Mềm (Software Security)\n"
                "Quy trình: Đặc tả -> Kripke -> Sinh mã -> CWE/CVE",
            ),
        )

    def _build_ui(self):
        # Main PanedWindow (Left controls, Right content)
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Left sidebar frame (Scrollable if needed)
        left_frame = ttk.Frame(self.paned, width=380)
        self.paned.add(left_frame, weight=0)

        # Right main notebook frame
        right_frame = ttk.Frame(self.paned)
        self.paned.add(right_frame, weight=1)

        self._build_left_sidebar(left_frame)
        self._build_right_notebook(right_frame)

    def _build_left_sidebar(self, parent: ttk.Frame):
        # 1. Spec JSON group
        grp_json = ttk.LabelFrame(parent, text="Bộ đặc tả mẫu JSON (dataset/specs):", padding=4)
        grp_json.pack(fill=tk.X, padx=4, pady=2)

        self.listbox_json = tk.Listbox(grp_json, height=5, font=("DejaVu Sans", 9), selectmode=tk.SINGLE, exportselection=False)
        self.listbox_json.pack(fill=tk.X, padx=2, pady=2)
        if self.specs_json_dir.exists():
            pay_f = sorted(self.specs_json_dir.glob("payment*.json"))
            oth_f = sorted(f for f in self.specs_json_dir.glob("*.json") if not f.name.startswith("payment"))
            for f in pay_f + oth_f:
                self.listbox_json.insert(tk.END, f.name)

        btn_load_json = ttk.Button(grp_json, text="Nạp đặc tả JSON đã chọn", command=self._load_selected_json)
        btn_load_json.pack(fill=tk.X, pady=2)

        # 2. Spec Excel group
        grp_excel = ttk.LabelFrame(parent, text="Bộ đặc tả mẫu Excel (dataset/specs_excel):", padding=4)
        grp_excel.pack(fill=tk.X, padx=4, pady=2)

        self.listbox_excel = tk.Listbox(grp_excel, height=3, font=("DejaVu Sans", 9), selectmode=tk.SINGLE, exportselection=False)
        self.listbox_excel.pack(fill=tk.X, padx=2, pady=2)
        if self.specs_excel_dir.exists():
            pay_fx = sorted(self.specs_excel_dir.glob("payment*.xlsx"))
            oth_fx = sorted(f for f in self.specs_excel_dir.glob("*.xlsx") if not f.name.startswith("payment"))
            for f in pay_fx + oth_fx:
                self.listbox_excel.insert(tk.END, f.name)

        btn_load_excel = ttk.Button(grp_excel, text="Nạp đặc tả Excel đã chọn", command=self._load_selected_excel)
        btn_load_excel.pack(fill=tk.X, pady=2)

        # 3. External file buttons
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, padx=4, pady=2)
        ttk.Button(btn_row, text="Nạp file JSON khác...", command=self._browse_json_file).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
        ttk.Button(btn_row, text="Nạp file Excel khác...", command=self._browse_excel_file).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

        # 4. Requirements preview box
        grp_req = ttk.LabelFrame(parent, text="Yêu cầu (requirements) trong đặc tả:", padding=4)
        grp_req.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        self.txt_requirements = tk.Text(grp_req, wrap=tk.WORD, height=7, font=("DejaVu Sans", 9), bg="#fafafa")
        self.txt_requirements.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scroll_req = ttk.Scrollbar(grp_req, orient=tk.VERTICAL, command=self.txt_requirements.yview)
        scroll_req.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_requirements.config(yscrollcommand=scroll_req.set)

        # 5. Pipeline execution buttons
        grp_pipeline = ttk.LabelFrame(parent, text="Quy trình thực thi (Pipeline):", padding=4)
        grp_pipeline.pack(fill=tk.X, padx=4, pady=4)

        btn_ch1 = tk.Button(
            grp_pipeline,
            text="1) Sinh Kripke + kiểm chứng (Ch1)",
            font=("DejaVu Sans", 9, "bold"),
            bg="#e3f2fd",
            fg="#0d47a1",
            relief=tk.RAISED,
            command=self._run_ch1,
        )
        btn_ch1.pack(fill=tk.X, pady=2)

        btn_ch2 = tk.Button(
            grp_pipeline,
            text="2) Sinh mã C/Python từ đặc tả",
            font=("DejaVu Sans", 9, "bold"),
            bg="#e8f5e9",
            fg="#1b5e20",
            relief=tk.RAISED,
            command=self._run_ch2,
        )
        btn_ch2.pack(fill=tk.X, pady=2)

        btn_full = tk.Button(
            grp_pipeline,
            text="3) Chạy TOÀN BỘ Pipeline",
            font=("DejaVu Sans", 10, "bold"),
            bg="#ffe082",
            fg="#bf360c",
            relief=tk.RAISED,
            command=self._run_full_pipeline,
        )
        btn_full.pack(fill=tk.X, pady=3)

        btn_export = tk.Button(
            grp_pipeline,
            text="Xuất báo cáo TÍCH HỢP (Markdown/HTML)",
            font=("DejaVu Sans", 9, "bold"),
            bg="#f3e5f5",
            fg="#4a148c",
            relief=tk.RAISED,
            command=self._export_report_dialog,
        )
        btn_export.pack(fill=tk.X, pady=2)

    def _build_right_notebook(self, parent: ttk.Frame):
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Kripke Structure & Verification
        self.tab_kripke = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_kripke, text="1. Đặc tả → Kripke & Kiểm chứng")
        self._build_tab_kripke(self.tab_kripke)

        # Tab 2: Code Generation
        self.tab_code = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_code, text="2. Mã nguồn sinh ra (C/Python)")
        self._build_tab_code(self.tab_code)

        # Tab 3: Arithmetic / Z3 SMT
        self.tab_smt = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_smt, text="3. Kiểm tra số học (Z3 Solver)")
        self._build_tab_smt(self.tab_smt)

        # Tab 4: CWE/CVE Vulnerabilities
        self.tab_cwe = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_cwe, text="4. Lỗ hổng & Ánh xạ CWE/CVE")
        self._build_tab_cwe(self.tab_cwe)

        # Tab 5: Full Report
        self.tab_report = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_report, text="5. Báo cáo Tích hợp")
        self._build_tab_report(self.tab_report)

    # ------------------ Tab 1: Kripke & Graph ------------------
    def _build_tab_kripke(self, parent: ttk.Frame):
        split = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        split.pack(fill=tk.BOTH, expand=True)

        # Top half: Log of verification results
        top_frame = ttk.LabelFrame(split, text="Kết quả kiểm chứng hình thức (Model Checking Log):", padding=4)
        split.add(top_frame, weight=1)

        self.txt_kripke_log = tk.Text(top_frame, wrap=tk.WORD, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4", height=8)
        self.txt_kripke_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(top_frame, command=self.txt_kripke_log.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_kripke_log.config(yscrollcommand=scroll.set)

        # Bottom half: Visual Graph Canvas
        bottom_frame = ttk.LabelFrame(split, text="Sơ đồ chuyển trạng thái Kripke:", padding=4)
        split.add(bottom_frame, weight=2)

        # Graph flow selector bar
        bar = ttk.Frame(bottom_frame)
        bar.pack(fill=tk.X, pady=2)
        ttk.Label(bar, text="Chọn luồng hiển thị:").pack(side=tk.LEFT, padx=4)
        self.cbo_flows = ttk.Combobox(bar, state="readonly", width=35)
        self.cbo_flows.pack(side=tk.LEFT, padx=4)
        self.cbo_flows.bind("<<ComboboxSelected>>", self._on_flow_selected)

        # Matplotlib Figure and Canvas
        self.figure = Figure(figsize=(7, 4.5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=bottom_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, bottom_frame)
        self.toolbar.update()

    # ------------------ Tab 2: Generated Code ------------------
    def _build_tab_code(self, parent: ttk.Frame):
        top_bar = ttk.Frame(parent, padding=4)
        top_bar.pack(fill=tk.X)

        ttk.Label(top_bar, text="Chọn hàm:").pack(side=tk.LEFT, padx=4)
        self.cbo_funcs = ttk.Combobox(top_bar, state="readonly", width=30)
        self.cbo_funcs.pack(side=tk.LEFT, padx=4)
        self.cbo_funcs.bind("<<ComboboxSelected>>", self._on_func_selected)

        ttk.Button(top_bar, text="Sao chép mã an toàn", command=self._copy_safe_code).pack(side=tk.RIGHT, padx=4)

        # Split pane for Vulnerable vs Safe
        paned_code = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned_code.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Left: Vulnerable
        frame_vuln = ttk.LabelFrame(paned_code, text="Mã nguồn minh họa LỖ HỔNG (Vulnerable Code):", padding=4)
        paned_code.add(frame_vuln, weight=1)

        self.txt_code_vuln = tk.Text(frame_vuln, wrap=tk.NONE, font=("Consolas", 10), bg="#2d1b1b", fg="#ffcccc")
        self.txt_code_vuln.pack(fill=tk.BOTH, expand=True)

        # Right: Hardened/Safe
        frame_safe = ttk.LabelFrame(paned_code, text="Mã nguồn đã VÁ AN TOÀN (Hardened / Secure Code):", padding=4)
        paned_code.add(frame_safe, weight=1)

        self.txt_code_safe = tk.Text(frame_safe, wrap=tk.NONE, font=("Consolas", 10), bg="#1b2d1b", fg="#ccffcc")
        self.txt_code_safe.pack(fill=tk.BOTH, expand=True)

    # ------------------ Tab 3: Arithmetic / SMT ------------------
    def _build_tab_smt(self, parent: ttk.Frame):
        frame = ttk.LabelFrame(parent, text="Kết quả phân tích điều kiện & Tràn số nguyên (Z3 Solver):", padding=8)
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.txt_smt = tk.Text(frame, wrap=tk.WORD, font=("Consolas", 10), bg="#f8f9fa", fg="#212529")
        self.txt_smt.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scroll = ttk.Scrollbar(frame, command=self.txt_smt.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_smt.config(yscrollcommand=scroll.set)

    # ------------------ Tab 4: CWE/CVE Table ------------------
    def _build_tab_cwe(self, parent: ttk.Frame):
        top_frame = ttk.Frame(parent, padding=4)
        top_frame.pack(fill=tk.X)

        self.lbl_cwe_summary = ttk.Label(top_frame, text="Chưa thực hiện kiểm tra an toàn.", style="Header.TLabel")
        self.lbl_cwe_summary.pack(side=tk.LEFT, padx=4)

        # Table
        cols = ("idx", "severity", "cwe", "name", "component", "cve")
        self.tree_cwe = ttk.Treeview(parent, columns=cols, show="headings", height=8)
        self.tree_cwe.heading("idx", text="#")
        self.tree_cwe.heading("severity", text="Mức độ")
        self.tree_cwe.heading("cwe", text="Mã CWE")
        self.tree_cwe.heading("name", text="Tên lỗ hổng")
        self.tree_cwe.heading("component", text="Thành phần")
        self.tree_cwe.heading("cve", text="Ví dụ CVE thực tế")

        self.tree_cwe.column("idx", width=40, anchor=tk.CENTER)
        self.tree_cwe.column("severity", width=90, anchor=tk.CENTER)
        self.tree_cwe.column("cwe", width=90, anchor=tk.CENTER)
        self.tree_cwe.column("name", width=320)
        self.tree_cwe.column("component", width=180)
        self.tree_cwe.column("cve", width=220)

        self.tree_cwe.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.tree_cwe.bind("<<TreeviewSelect>>", self._on_cwe_selected)

        # Details box below table
        detail_frame = ttk.LabelFrame(parent, text="Chi tiết lỗ hổng và Hướng dẫn khắc phục an toàn:", padding=4)
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.txt_cwe_detail = tk.Text(detail_frame, wrap=tk.WORD, font=("Segoe UI", 9), height=7, bg="#ffffff")
        self.txt_cwe_detail.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scroll = ttk.Scrollbar(detail_frame, command=self.txt_cwe_detail.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_cwe_detail.config(yscrollcommand=scroll.set)

    # ------------------ Tab 5: Report ------------------
    def _build_tab_report(self, parent: ttk.Frame):
        bar = ttk.Frame(parent, padding=4)
        bar.pack(fill=tk.X)

        ttk.Button(bar, text="Lưu báo cáo ra file (.md)...", command=self._export_report_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Làm mới báo cáo", command=self._refresh_report_view).pack(side=tk.LEFT, padx=4)

        self.txt_report = tk.Text(parent, wrap=tk.WORD, font=("Consolas", 9), bg="#ffffff")
        self.txt_report.pack(fill=tk.BOTH, expand=True, padx=4, pady=4, side=tk.LEFT)
        scroll = ttk.Scrollbar(parent, command=self.txt_report.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_report.config(yscrollcommand=scroll.set)

    # ------------------ Handlers & Actions ------------------
    def _load_default_spec(self):
        default_file = self.specs_json_dir / "payment_ecommerce_spec.json"
        if not default_file.exists():
            default_file = self.specs_json_dir / "auth_rate_limit_spec.json"
        if default_file.exists():
            self._load_file(default_file, show_popup=False)
            # Select in listbox
            items = self.listbox_json.get(0, tk.END)
            for idx, item in enumerate(items):
                if item == default_file.name:
                    self.listbox_json.selection_set(idx)
                    break

    def _browse_json_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if path:
            self._load_file(Path(path), show_popup=True)

    def _browse_excel_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")])
        if path:
            self._load_file(Path(path), show_popup=True)

    def _load_selected_json(self):
        sel = self.listbox_json.curselection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn một file JSON từ danh sách!")
            return
        filename = self.listbox_json.get(sel[0])
        self._load_file(self.specs_json_dir / filename, show_popup=True)

    def _load_selected_excel(self):
        sel = self.listbox_excel.curselection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn một file Excel từ danh sách!")
            return
        filename = self.listbox_excel.get(sel[0])
        self._load_file(self.specs_excel_dir / filename, show_popup=True)

    def _load_file(self, filepath: Path, show_popup: bool = True):
        try:
            self.current_spec = load_specification(filepath)
            self._update_requirements_box()
            self._update_flow_combo()
            self._update_func_combo()

            # Clear previous outputs
            self.txt_kripke_log.delete("1.0", tk.END)
            self.txt_kripke_log.insert(
                tk.END,
                f"Đã nạp thành công: {self.current_spec.summary()}\n"
                f"Bấm '1) Sinh Kripke + kiểm chứng' hoặc '3) Chạy TOÀN BỘ Pipeline' để bắt đầu.\n",
            )
            # Render initial state diagram
            if self.current_spec.state_machine:
                self.current_kripke_model = KripkeStructure.from_state_machine(
                    self.current_spec.state_machine, self.current_spec.name
                )
                self.current_kripke_model.draw_to_figure(self.figure)
                self.canvas.draw()

            if show_popup:
                messagebox.showinfo("Thành công", f"Đã nạp đặc tả: {self.current_spec.name}")
        except Exception as e:
            messagebox.showerror("Lỗi nạp file", f"Không thể đọc file đặc tả: {e}")

    def _update_requirements_box(self):
        self.txt_requirements.delete("1.0", tk.END)
        if not self.current_spec:
            return
        self.txt_requirements.insert(tk.END, f"[{self.current_spec.name}]: {self.current_spec.description}\n\n")
        for req in self.current_spec.requirements:
            self.txt_requirements.insert(
                tk.END, f"[{req.priority}/{req.category}] {req.id}: {req.text}\n"
            )

    def _update_flow_combo(self):
        flows = ["Mô hình chính (Main Model)"]
        if self.current_spec and self.current_spec.additional_flows:
            for k in self.current_spec.additional_flows.keys():
                flows.append(k)
        self.cbo_flows["values"] = flows
        self.cbo_flows.current(0)

    def _update_func_combo(self):
        if not self.current_spec or not self.current_spec.functions:
            self.cbo_funcs["values"] = []
            return
        names = [f"{fn.name} ({fn.language})" for fn in self.current_spec.functions]
        self.cbo_funcs["values"] = names
        self.cbo_funcs.current(0)

    def _on_flow_selected(self, event=None):
        if not self.current_spec:
            return
        selected = self.cbo_flows.get()
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

    def _on_func_selected(self, event=None):
        if not self.generated_functions:
            return
        idx = self.cbo_funcs.current()
        if 0 <= idx < len(self.generated_functions):
            fn = self.generated_functions[idx]
            self.txt_code_vuln.delete("1.0", tk.END)
            self.txt_code_vuln.insert(tk.END, format_code_with_line_numbers(fn.code_vulnerable))
            self.txt_code_safe.delete("1.0", tk.END)
            self.txt_code_safe.insert(tk.END, format_code_with_line_numbers(fn.code_safe))

    def _copy_safe_code(self):
        idx = self.cbo_funcs.current()
        if 0 <= idx < len(self.generated_functions):
            fn = self.generated_functions[idx]
            self.root.clipboard_clear()
            self.root.clipboard_append(fn.code_safe)
            messagebox.showinfo("Đã sao chép", f"Đã sao chép mã an toàn của hàm '{fn.spec.name}' vào clipboard!")

    # ------------------ Pipeline Execution ------------------
    def _run_ch1(self):
        if not self.current_spec:
            messagebox.showwarning("Cảnh báo", "Vui lòng nạp đặc tả trước khi chạy kiểm chứng!")
            return

        if not self.current_spec.state_machine:
            messagebox.showinfo("Thông báo", "Đặc tả này không có mô hình máy trạng thái (Chương 1 bỏ qua).")
            return

        self.current_kripke_model = KripkeStructure.from_state_machine(
            self.current_spec.state_machine, self.current_spec.name
        )
        self.kripke_report = self.current_kripke_model.verify_all(
            self.current_spec.safety_properties, self.current_spec.mutual_exclusion
        )

        self.txt_kripke_log.delete("1.0", tk.END)
        self.txt_kripke_log.insert(tk.END, self.kripke_report.summary_text)

        # Highlight violations if any
        viols = []
        path = []
        for prop in self.kripke_report.property_results:
            if not prop.passed:
                viols.extend(prop.violation_states)
                if prop.counterexample_path:
                    path = prop.counterexample_path

        self.current_kripke_model.draw_to_figure(self.figure, highlight_violations=viols, highlight_path=path)
        self.canvas.draw()
        self.notebook.select(self.tab_kripke)

    def _run_ch2(self):
        if not self.current_spec:
            messagebox.showwarning("Cảnh báo", "Vui lòng nạp đặc tả trước!")
            return

        self.generated_functions = generate_all_functions(self.current_spec)
        self._update_func_combo()
        self._on_func_selected()
        self.notebook.select(self.tab_code)

    def _run_ch3(self):
        if not self.current_spec:
            return
        self.smt_results = check_all_arithmetic(self.current_spec.arithmetic_checks)
        self.txt_smt.delete("1.0", tk.END)
        if self.smt_results:
            for r in self.smt_results:
                self.txt_smt.insert(tk.END, r.details + "\n\n")
        else:
            self.txt_smt.insert(tk.END, "Không có kiểm tra số học nào được định nghĩa trong đặc tả này.")

    def _run_ch4(self):
        if not self.current_spec:
            return
        self.security_audit = analyze_security_vulnerabilities(
            self.current_spec, self.kripke_report, self.smt_results
        )
        # Update table
        for item in self.tree_cwe.get_children():
            self.tree_cwe.delete(item)

        for idx, f in enumerate(self.security_audit.findings, 1):
            self.tree_cwe.insert(
                "",
                tk.END,
                values=(idx, f.severity, f.cwe_id, f.cwe_name, f.source_component, f.illustrative_cve),
            )

        self.lbl_cwe_summary.config(
            text=(
                f"Tổng số lỗ hổng: {self.security_audit.total_findings} | "
                f"CRITICAL: {self.security_audit.critical_count} | "
                f"HIGH: {self.security_audit.high_count} | "
                f"MEDIUM: {self.security_audit.medium_count}"
            )
        )

    def _run_full_pipeline(self):
        if not self.current_spec:
            messagebox.showwarning("Cảnh báo", "Vui lòng nạp đặc tả trước!")
            return

        self._run_ch1()
        self._run_ch2()
        self._run_ch3()
        self._run_ch4()
        self._refresh_report_view()

        messagebox.showinfo(
            "Hoàn tất Pipeline",
            f"Đã chạy toàn bộ quy trình cho đặc tả '{self.current_spec.name}'!\n"
            f"- Kiểm chứng Kripke: {'HỢP LỆ' if (not self.kripke_report or self.kripke_report.is_valid) else 'PHÁT HIỆN LỖI'}\n"
            f"- Số hàm sinh mã: {len(self.generated_functions)}\n"
            f"- Số kiểm tra Z3: {len(self.smt_results)}\n"
            f"- Lỗ hổng CWE phát hiện: {self.security_audit.total_findings if self.security_audit else 0}",
        )

    def _on_cwe_selected(self, event=None):
        sel = self.tree_cwe.selection()
        if not sel or not self.security_audit:
            return
        item = self.tree_cwe.item(sel[0])
        idx = int(item["values"][0]) - 1
        if 0 <= idx < len(self.security_audit.findings):
            f = self.security_audit.findings[idx]
            self.txt_cwe_detail.delete("1.0", tk.END)
            self.txt_cwe_detail.insert(
                tk.END,
                f"[{f.severity}] {f.cwe_id} — {f.cwe_name}\n"
                f"Thành phần: {f.source_component}\n\n"
                f"MÔ TẢ LỖ HỔNG:\n{f.description}\n\n"
                f"VÍ DỤ CVE THỰC TẾ:\n{f.illustrative_cve}\n\n"
                f"HƯỚNG DẪN KHẮC PHỤC / PHÒNG CHỐNG:\n{f.remediation}\n",
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
        self.txt_report.delete("1.0", tk.END)
        self.txt_report.insert(tk.END, report_text)

    def _export_report_dialog(self):
        if not self.current_spec:
            messagebox.showwarning("Cảnh báo", "Vui lòng nạp đặc tả trước khi xuất báo cáo!")
            return

        if not self.security_audit:
            self._run_full_pipeline()

        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            initialfile=f"BaoCao_KiemChung_{self.current_spec.name}.md",
            filetypes=[("Markdown files", "*.md"), ("HTML files", "*.html"), ("All files", "*.*")],
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
                messagebox.showinfo("Thành công", f"Báo cáo đã được xuất ra:\n{path}")
            except Exception as e:
                messagebox.showerror("Lỗi xuất file", f"Không thể lưu báo cáo: {e}")


def main():
    root = tk.Tk()
    app = SpecVerificationLabApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
