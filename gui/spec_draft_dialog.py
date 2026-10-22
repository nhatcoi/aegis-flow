"""Dialog: describe a system in plain language, get an AI-drafted JSON spec, review, save.

The draft is validated with ``core.spec_draft.check_draft`` (same loader as hand-written
specs) and previewed as a Kripke graph before it can be saved to ``dataset/drafts/``.
"""
from __future__ import annotations

import html

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core import ai_explain, spec_draft
from core.kripke import KripkeStructure

from .theme import TOKENS

EXAMPLE = ("Hệ thống đặt vé xem phim: khách chọn ghế thì ghế bị giữ 10 phút; thanh toán thành công thì xuất vé; "
           "hết 10 phút chưa trả tiền thì nhả ghế. Thiết kế hiện tại có lỗi: khi cổng thanh toán timeout hệ thống "
           "vẫn xuất vé. Có hàm C sao chép mã ghế vào bộ đệm 16 byte bằng strcpy, và hàm Python tính tiền giảm "
           "giá chia cho số vé.")


class DraftWorker(QObject):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, cfg: ai_explain.AIConfig, prompt: str):
        super().__init__()
        self.cfg, self.prompt = cfg, prompt

    def run(self) -> None:
        try:
            self.finished.emit(spec_draft.draft_spec(self.cfg, self.prompt))
        except Exception as e:  # noqa: BLE001 - shown in the dialog
            self.failed.emit(str(e))


class SpecDraftDialog(QDialog):
    saved = pyqtSignal(str)  # path of the saved draft

    def __init__(self, cfg: ai_explain.AIConfig, mode: str, parent=None):
        super().__init__(parent)
        self.cfg, self.mode = cfg, mode
        self.thread: QThread | None = None
        self.check: spec_draft.DraftCheck | None = None
        self.setWindowTitle("Tạo đặc tả nháp bằng AI")
        self.resize(1180, 760)
        t = TOKENS[mode]
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

        root = QVBoxLayout(self)
        banner = QLabel("⚠  Bản nháp do AI tạo: đọc lại và sửa trước khi dùng. Đặc tả nộp kèm báo cáo phải do "
                        "nhóm viết và giải thích được; không dùng bản nháp này cho số liệu báo cáo.")
        banner.setWordWrap(True)
        banner.setStyleSheet(f"color: {t['warn']}; padding: 6px 2px;")
        root.addWidget(banner)

        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 6, 0)
        ll.addWidget(QLabel("<b>Mô tả hệ thống</b> (trạng thái, luật nghiệp vụ, lỗi đã biết, các hàm xử lý dữ liệu)"))
        self.txt_prompt = QPlainTextEdit()
        self.txt_prompt.setPlaceholderText(EXAMPLE)
        ll.addWidget(self.txt_prompt, 1)
        row = QHBoxLayout()
        btn_example = QPushButton("Dùng ví dụ")
        btn_example.clicked.connect(lambda: self.txt_prompt.setPlainText(EXAMPLE))
        row.addWidget(btn_example)
        row.addStretch()
        self.btn_draft = QPushButton("✨  Tạo bản nháp")
        self.btn_draft.setObjectName("primary")
        self.btn_draft.setEnabled(cfg.enabled)
        self.btn_draft.setToolTip(f"Model {cfg.model} tại {cfg.base_url}" if cfg.enabled
                                  else "Chưa cấu hình API key (OPENAI_API_KEY / AEGIS_AI_KEY trong .env)")
        self.btn_draft.clicked.connect(self._draft)
        row.addWidget(self.btn_draft)
        ll.addLayout(row)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.txt_json = QPlainTextEdit()
        self.txt_json.setFont(mono)
        self.txt_json.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.txt_json.setPlaceholderText("JSON của bản nháp sẽ hiện ở đây; có thể sửa trực tiếp rồi bấm Kiểm tra.")
        self.tabs.addTab(self.txt_json, "JSON (sửa được)")
        preview = QWidget()
        pl = QVBoxLayout(preview)
        pl.setContentsMargins(0, 4, 0, 0)
        self.txt_summary = QTextBrowser()
        self.txt_summary.setMaximumHeight(170)
        pl.addWidget(self.txt_summary)
        self.figure = Figure(figsize=(7, 4), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        pl.addWidget(self.canvas, 1)
        self.tabs.addTab(preview, "Xem trước")
        rl.addWidget(self.tabs, 3)
        self.txt_check = QTextBrowser()
        self.txt_check.setMaximumHeight(150)
        rl.addWidget(self.txt_check, 1)
        split.addWidget(right)
        split.setSizes([360, 820])
        root.addWidget(split, 1)

        buttons = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {t['muted']};")
        buttons.addWidget(self.lbl_status, 1)
        btn_check = QPushButton("Kiểm tra")
        btn_check.clicked.connect(self._check)
        buttons.addWidget(btn_check)
        self.btn_save = QPushButton("Lưu và mở")
        self.btn_save.setEnabled(False)
        self.btn_save.setToolTip(f"Lưu vào {spec_draft.DRAFT_DIR.relative_to(spec_draft.ROOT)}/ rồi nạp vào app")
        self.btn_save.clicked.connect(self._save)
        buttons.addWidget(self.btn_save)
        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.reject)
        buttons.addWidget(btn_close)
        root.addLayout(buttons)
        self.txt_json.textChanged.connect(lambda: self.btn_save.setEnabled(False))

    # ------------------------------------------------------------------ AI round trip
    def _draft(self) -> None:
        prompt = self.txt_prompt.toPlainText().strip()
        if not prompt or self.thread:
            return
        self.btn_draft.setEnabled(False)
        self.lbl_status.setText(f"Đang hỏi model {self.cfg.model}… (thường 10–30 giây)")
        self.thread = QThread()
        self.worker = DraftWorker(self.cfg, prompt)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_draft)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self._on_thread_finished)
        self.thread.start()

    def _on_thread_finished(self) -> None:
        self.thread = None
        self.btn_draft.setEnabled(self.cfg.enabled)

    def _on_draft(self, text: str) -> None:
        self.lbl_status.setText("Đã nhận bản nháp.")
        self.txt_json.setPlainText(text)
        self._check()

    def _on_failed(self, error: str) -> None:
        self.lbl_status.setText("Không tạo được bản nháp.")
        self.txt_check.setHtml(f"<p style='color:{TOKENS[self.mode]['fail']}'><b>Lỗi:</b> {html.escape(error)}</p>")

    # ------------------------------------------------------------------ validation / preview
    def _check(self) -> None:
        t = TOKENS[self.mode]
        self.check = spec_draft.check_draft(self.txt_json.toPlainText())
        c = self.check
        parts = []
        if c.errors:
            parts.append(f"<p style='color:{t['fail']}'><b>✗ {len(c.errors)} lỗi, cần sửa trước khi lưu</b></p><ul>"
                         + "".join(f"<li>{html.escape(e)}</li>" for e in c.errors) + "</ul>")
        if c.warnings:
            parts.append(f"<p style='color:{t['warn']}'><b>⚠ {len(c.warnings)} cảnh báo, nên đọc lại</b></p><ul>"
                         + "".join(f"<li>{html.escape(w)}</li>" for w in c.warnings) + "</ul>")
        if c.ok:
            parts.insert(0, f"<p style='color:{t['pass']}'><b>✓ Bộ nạp đặc tả chấp nhận bản nháp.</b> "
                            "Kiểm tra cú pháp không thay cho việc đọc lại nội dung.</p>")
        self.txt_check.setHtml("".join(parts))
        self.btn_save.setEnabled(c.ok)
        self._preview()

    def _preview(self) -> None:
        spec = self.check.spec if self.check else None
        self.figure.clear()
        if not spec:
            self.txt_summary.clear()
            self.canvas.draw()
            return
        reqs = "".join(f"<li><b>{r.id}</b> ({r.category}): {html.escape(r.text)}</li>" for r in spec.requirements)
        props = "".join(f"<li><code>{html.escape(p)}</code></li>" for p in spec.safety_properties)
        fns = ", ".join(f"{f.name} ({f.language}/{f.kind}{', ' + f.bug if f.bug else ''})" for f in spec.functions)
        self.txt_summary.setHtml(f"<p><b>{html.escape(spec.name)}</b>: {html.escape(spec.summary())}</p>"
                                 f"<p>{html.escape(spec.description)}</p><p><b>Yêu cầu</b></p><ul>{reqs}</ul>"
                                 f"<p><b>Luật CTL</b></p><ul>{props or '<li>—</li>'}</ul>"
                                 f"<p><b>Hàm sinh mã:</b> {html.escape(fns) or '—'}</p>")
        sm = spec.state_machine
        if sm and sm.states and not self.check.errors:
            KripkeStructure.from_state_machine(sm, spec.name).draw_to_figure(self.figure, dark=self.mode == "dark")
        self.canvas.draw()

    def _save(self) -> None:
        if not self.check or not self.check.ok:
            return
        path = spec_draft.save_draft(self.check, self.txt_prompt.toPlainText(), self.cfg.model)
        self.saved.emit(str(path))
        self.accept()

    def done(self, result: int) -> None:
        if self.thread:  # closed mid-request: let it finish in the background and drop the answer
            for sig in (self.worker.finished, self.worker.failed, self.thread.finished):
                sig.disconnect()
            self.worker.finished.connect(self.thread.quit)
            self.worker.failed.connect(self.thread.quit)
            orphans = getattr(self.parent(), "_orphan_threads", None)
            if orphans is not None:
                orphans.append((self.thread, self.worker))
            self.thread = None
        super().done(result)
