"""Recorded Ch.4 workflow: inspect real campaign evidence and replay concrete inputs."""
from __future__ import annotations

import html
import json
from dataclasses import asdict

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.fuzz_evidence import STOP_LABELS, replay_input, result_label
from core.fuzzing import state_fuzz

PAGE_SIZE = 100
STAGES = [
    ("1. Chuẩn bị", "Input: hàm/mô hình, phiên bản, seed và ngân sách. Output: chiến dịch có thể chạy lại."),
    ("2. Sinh input", "Input: seed hoặc model Z3. Output: input cụ thể và nguồn sinh; chọn một dòng để xem."),
    ("3. Thực thi · Coverage", "Input: lần thử đang chọn. Output: trace, kết quả oracle và độ phủ thực tế."),
    ("4. Đường đi · Z3", "Input: đường đã chạy. Output: phủ định nhánh, SAT/UNSAT/UNKNOWN và model sinh input mới."),
    ("5. Replay · v0/v1", "Input: input lỗi hoặc lần thử đã chọn. Output: kết quả chạy lại để xác nhận."),
    ("6. Bằng chứng · Demo", "Input: chiến dịch đã chạy. Output: log đầy đủ, query/model, đồ thị và kịch bản trình bày."),
]


def pretty(value):
    return html.escape(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    widget.horizontalHeader().setStretchLastSection(True)
    widget.verticalHeader().hide()
    return widget


class FuzzWorkflow(QWidget):
    runRequested = pyqtSignal()
    exportRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report = self.result = self.generated = None
        self.is_state = False
        self.current_trial = None
        self.page = 0
        self.visible_trials = []
        layout = QVBoxLayout(self)
        self.summary = QLabel("Chọn đặc tả và Chạy pipeline; sau đó chọn một chiến dịch ở bảng phía trên.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.tabs = QTabWidget()
        self.pages = []
        for title, description in STAGES:
            page = QWidget()
            lay = QVBoxLayout(page)
            label = QLabel(description)
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            lay.addWidget(label)
            self.tabs.addTab(page, title)
            self.pages.append(lay)
        layout.addWidget(self.tabs, 1)
        nav = QHBoxLayout()
        self.previous = QPushButton("← Bước trước")
        self.next = QPushButton("Bước tiếp →")
        self.previous.clicked.connect(lambda: self.tabs.setCurrentIndex(max(0, self.tabs.currentIndex() - 1)))
        self.next.clicked.connect(lambda: self.tabs.setCurrentIndex(min(5, self.tabs.currentIndex() + 1)))
        nav.addWidget(self.previous)
        nav.addStretch()
        self.step_label = QLabel()
        nav.addWidget(self.step_label)
        nav.addWidget(self.next)
        layout.addLayout(nav)
        self.tabs.currentChanged.connect(self._step_changed)
        self.setup = QTextBrowser()
        self.pages[0].addWidget(self.setup)
        run = QPushButton("Chạy pipeline với cấu hình trên thanh công cụ")
        run.clicked.connect(lambda: self.runRequested.emit())
        self.pages[0].addWidget(run)
        self.filter = QComboBox()
        self.filter.addItems(["Tất cả lần thử", "Chỉ có lỗi / vi phạm", "Chỉ tăng coverage"])
        self.filter.currentIndexChanged.connect(self._filter_trials)
        self.pages[1].addWidget(self.filter)
        self.timeline = table(["Lần", "Input / Chuỗi trạng thái", "Nguồn sinh", "Coverage mới", "Oracle"])
        self.timeline.itemSelectionChanged.connect(self._trial_selected)
        self.pages[1].addWidget(self.timeline)
        pagination = QHBoxLayout()
        prev_page, next_page = QPushButton("← 100 trước"), QPushButton("100 tiếp →")
        prev_page.clicked.connect(lambda: self._move_page(-1))
        next_page.clicked.connect(lambda: self._move_page(1))
        self.page_label = QLabel()
        pagination.addWidget(prev_page)
        pagination.addWidget(self.page_label)
        pagination.addWidget(next_page)
        self.pages[1].addLayout(pagination)
        self.origin = QTextBrowser()
        self.origin.setMaximumHeight(125)
        self.pages[1].addWidget(self.origin)
        trace_split = QSplitter()
        self.execution = QTextBrowser()
        self.figure = Figure(figsize=(4, 2.5), tight_layout=True)
        self.coverage_canvas = FigureCanvasQTAgg(self.figure)
        trace_split.addWidget(self.execution)
        trace_split.addWidget(self.coverage_canvas)
        self.pages[2].addWidget(trace_split)
        graph_split = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Cây sinh input / khám phá mô hình", "Kết quả"])
        self.tree.currentItemChanged.connect(self._tree_selected)
        self.query = QTextBrowser()
        graph_split.addWidget(self.tree)
        graph_split.addWidget(self.query)
        graph_split.setSizes([450, 550])
        self.pages[3].addWidget(graph_split)
        self.replay_intro = QLabel("Chọn input ở bước 2 rồi bấm Replay; cùng input sẽ chạy trên v0 và v1.")
        self.replay_intro.setWordWrap(True)
        self.replay_intro.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pages[4].addWidget(self.replay_intro)
        self.replay_button = QPushButton("Replay lần thử đang chọn")
        self.replay_button.clicked.connect(self._replay)
        self.pages[4].addWidget(self.replay_button)
        self.replay_output = QTextBrowser()
        self.pages[4].addWidget(self.replay_output)
        self.guide = QTextBrowser()
        self.pages[5].addWidget(self.guide)
        export = QPushButton("Xuất đầy đủ bằng chứng của pipeline")
        export.clicked.connect(lambda: self.exportRequested.emit())
        self.pages[5].addWidget(export)
        self._step_changed(0)
        self.clear()

    def _step_changed(self, index):
        self.previous.setEnabled(index > 0)
        self.next.setEnabled(index < 5)
        self.step_label.setText(f"Bước {index + 1}/6 · Xem lại bằng chứng đã chạy")

    def clear(self):
        self.report = self.result = self.generated = self.current_trial = None
        self.timeline.setRowCount(0)
        self.tree.clear()
        self.summary.setText("Chọn chiến dịch sau khi Chạy pipeline. Đây là quy trình xem lại bằng chứng thực tế.")
        for browser in [self.setup, self.origin, self.execution, self.query, self.replay_output, self.guide]:
            browser.clear()
        self.replay_button.setEnabled(False)
        self.figure.clear()
        self.coverage_canvas.draw_idle()

    def set_campaign(self, report, result, *, is_state=False):
        self.report, self.result, self.is_state = report, result, is_state
        self.generated = None if is_state else next(g for g in report.functions if g.spec.name == result.function)
        self.current_trial = None
        self.replay_output.clear()
        self.replay_button.setEnabled(False)
        self.summary.setText(
            f"Khám phá mô hình đặc tả · {result.strategy.upper()} · {result.paths_explored}/{result.budget} chuỗi"
            if is_state else
            f"{result.function} · {result.version} · {result.strategy} · {result_label(result)} · "
            f"{result.iterations}/{result.budget} lần · {result.hits} hit / {result.unique_findings} nhóm lỗi"
        )
        if is_state:
            setup = {"đối tượng": "Mô hình đặc tả; không gọi hệ thống thanh toán thật",
                     "seed": result.seed, "budget": result.budget,
                     "độ sâu tối đa (số cạnh)": result.max_depth, "giới hạn thăm lại": "BFS/DFS: tối đa 2 lần/state/path",
                     "oracle": "Nhãn vi phạm, invariant thanh toán/khóa và deadlock",
                     "kết thúc": STOP_LABELS.get(result.stop_reason, result.stop_reason)}
        else:
            setup = {"đối tượng": "Thực thi hàm Python sinh từ đặc tả", "hàm": result.function,
                     "phiên bản": result.version, "chiến lược": result.strategy,
                     "seed": result.seed, "seed corpus": [1] * len(self.generated.spec.params),
                     "miền input": "int32", "budget tối đa": result.budget,
                     "đã thực thi": result.iterations, "oracle": self.generated.spec.kind,
                     "kết thúc": STOP_LABELS.get(result.stop_reason, result.stop_reason),
                     "solver timeout (ms)": result.solver_timeout_ms if result.strategy == 'concolic' else 'không dùng'}
        self.setup.setHtml('<h3>Input của chiến dịch</h3><pre>' + pretty(setup) + '</pre>'
                           '<p>Black-box không dùng coverage để sinh input; tracer chỉ đo và ghi bằng chứng. '
                           'Coverage-guided giữ mẫu mở thêm dòng. Concolic phủ định điều kiện để sinh input bằng Z3.</p>'
                           '<p><b>Output:</b> các lần thử, trace, coverage, phát hiện và lý do dừng. '
                           'Không có lỗi trong giới hạn chạy không đồng nghĩa chứng minh an toàn.</p>')
        self._filter_trials()
        self._build_tree()
        self._plot()
        self.guide.setHtml(self._guide_html())

    def _filter_trials(self):
        if self.result is None:
            return
        trials = self.result.trials
        if self.filter.currentIndex() == 1:
            trials = [t for t in trials if (t.get('findings') if self.is_state else t['finding'])]
        elif self.filter.currentIndex() == 2:
            trials = [t for t in trials if (
                t.get('new_states', 0) or t.get('new_transitions', 0)
                if self.is_state else t['new_lines'])]
        self.visible_trials, self.page = trials, 0
        self._fill_page()

    def _move_page(self, delta):
        last = max(0, (len(self.visible_trials) - 1) // PAGE_SIZE)
        self.page = max(0, min(last, self.page + delta))
        self._fill_page()

    def _fill_page(self):
        rows = self.visible_trials[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]
        self.timeline.setRowCount(0)
        self.timeline.setRowCount(len(rows))
        for row, t in enumerate(rows):
            if self.is_state:
                values = [t['iteration'], ' → '.join(t['path']), self.result.strategy.upper(),
                          f"+{t['new_states']} state / +{t['new_transitions']} cạnh",
                          ', '.join(f['kind'] for f in t['findings']) or 'không vi phạm']
            else:
                mutation = t.get('mutation', {}).get('operator')
                values = [t['iteration'], t['input'], mutation or t.get('origin', ''),
                          f"+{len(t['new_lines'])} dòng", t['finding'] or 'không lỗi']
            for col, value in enumerate(values):
                self.timeline.setItem(row, col, QTableWidgetItem(str(value)))
        total = len(self.visible_trials)
        self.page_label.setText(f"{self.page * PAGE_SIZE + 1 if total else 0}–"
                                f"{min((self.page + 1) * PAGE_SIZE, total)} / {total} lần thử")
        if rows:
            self.timeline.selectRow(0)
        else:
            self.current_trial = None
            self.replay_button.setEnabled(False)
            self.origin.setPlainText('Không có lần thử khớp bộ lọc. Đổi bộ lọc để chọn input.')
            self.execution.clear()

    def _trial_selected(self):
        row = self.timeline.currentRow()
        index = self.page * PAGE_SIZE + row
        if row < 0 or index >= len(self.visible_trials):
            return
        t = self.current_trial = self.visible_trials[index]
        self.replay_button.setEnabled(True)
        self.replay_output.clear()
        if self.is_state:
            self.origin.setHtml('<pre>' + pretty(t) + '</pre>')
            self.execution.setHtml('<h3>Chuỗi được đánh giá trên mô hình</h3><p>'
                                   + html.escape(' → '.join(t['path'])) + '</p><pre>' + pretty(t) + '</pre>')
            self.replay_intro.setText(f"Replay chuỗi #{t['iteration']} trên mô hình đặc tả, không gọi mã thanh toán thật.")
        else:
            self.origin.setHtml('<pre>' + pretty({k: t[k] for k in (
                'input', 'origin', 'parent_iteration', 'parent_input', 'mutation', 'query_id',
                'kept_in_corpus', 'corpus_size') if k in t}) + '</pre>')
            code = self.generated.code_vulnerable if self.result.version == 'v0' else self.generated.code_safe
            lines = []
            for n, line in enumerate(code.splitlines(), 1):
                style = 'background-color:rgba(65,205,82,0.18)' if n in t['lines'] else ''
                lines.append(f'<span style="{style}">{n:3} {html.escape(line)}</span>')
            self.execution.setHtml('<h3>Mã đã chạy (dòng tô màu)</h3><pre>' + '\n'.join(lines)
                                   + '</pre><p><b>Thứ tự dòng:</b> ' + html.escape(str(t['trace']))
                                   + '</p><p><b>Output:</b> ' + html.escape(str(t['value']))
                                   + ' · <b>Oracle:</b> ' + html.escape(t['finding'] or 'không lỗi')
                                   + '</p><pre>' + html.escape(t['traceback']) + '</pre>')
            self.replay_intro.setText(f"Replay lần #{t['iteration']}: input {t['input']} trên cả v0 và v1.")

    def _plot(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        trials = self.result.trials
        if self.is_state:
            ax.plot([t['iteration'] for t in trials], [t['states_evaluated'] for t in trials], label='States')
            ax.plot([t['iteration'] for t in trials], [t['transitions_evaluated'] for t in trials], label='Transitions')
        else:
            seen, counts = set(), []
            for trial in trials:
                seen.update(trial['lines'])
                counts.append(len(seen))
            ax.plot([t['iteration'] for t in trials], counts, label='Executed lines')
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Coverage count')
        ax.grid(alpha=0.2)
        if trials:
            ax.legend()
        self.coverage_canvas.draw_idle()

    def _build_tree(self):
        self.tree.clear()
        if self.is_state:
            nodes = {}
            for trial in self.result.trials:
                for end in range(1, len(trial['path']) + 1):
                    key = tuple(trial['path'][:end])
                    if key not in nodes:
                        item = QTreeWidgetItem([key[-1], f'{end - 1} cạnh'])
                        item.setData(0, Qt.ItemDataRole.UserRole, {'path': list(key), 'scope': 'specification model'})
                        parent = nodes.get(key[:-1])
                        parent.addChild(item) if parent else self.tree.addTopLevelItem(item)
                        nodes[key] = item
            self.query.setPlainText('Đây là cây các tiền tố chuỗi đã đánh giá trên mô hình, không sinh input bằng Z3.')
        else:
            trials, queries = {}, {}
            for t in self.result.trials:
                item = QTreeWidgetItem([f"#{t['iteration']} {t['input']}", t['finding'] or 'đã chạy'])
                item.setData(0, Qt.ItemDataRole.UserRole, t)
                trials[t['iteration']] = item
            for t in self.result.trials:
                item = trials[t['iteration']]
                parent = queries.get(t.get('query_id')) or trials.get(t.get('parent_iteration'))
                parent.addChild(item) if parent else self.tree.addTopLevelItem(item)
                for q in self.result.queries:
                    if q['iteration'] == t['iteration']:
                        child = QTreeWidgetItem([f"{q['id']} phủ định nhánh {q['negated_branch'] + 1}", q['status'].upper()])
                        child.setData(0, Qt.ItemDataRole.UserRole, q)
                        item.addChild(child)
                        queries[q['id']] = child
                        if q['generated_input'] is not None and not any(
                                x.get('query_id') == q['id'] for x in self.result.trials):
                            pending = QTreeWidgetItem([str(q['generated_input']), 'SAT · chưa thực thi'])
                            pending.setData(0, Qt.ItemDataRole.UserRole, q)
                            child.addChild(pending)
            self.query.setPlainText('Chọn input hoặc truy vấn. Model Z3 là phép gán sinh input, không phải đặc tả Kripke mới. '
                                    'Đường UNSAT chỉ bất khả thi trong ràng buộc đã mã hóa.' if self.result.queries else
                                    'Chiến lược này không gọi Z3; xem nguồn đột biến và trace tại bước 2–3.')
        if not self.is_state and len(self.result.trials) < 50:
            self.tree.expandAll()
            candidate = next((queries[q["id"]] for q in self.result.queries
                              if q.get("generated_input") == list(self.result.first_input or ())), None)
            if candidate is not None:
                self.tree.setCurrentItem(candidate)
        else:
            self.tree.expandToDepth(1)
        self.tree.resizeColumnToContents(0)

    def _tree_selected(self, item, previous):
        if item is None:
            return
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if value is not None:
            details = {k: v for k, v in value.items() if k != 'smt2'}
            text = '<h3>Bằng chứng chi tiết</h3><pre>' + pretty(details) + '</pre>'
            if 'smt2' in value:
                text += '<h3>Truy vấn SMT-LIB có thể chạy lại</h3><pre>' + html.escape(value['smt2']) + '</pre>'
            self.query.setHtml(text)

    def _replay(self):
        if self.current_trial is None:
            return
        try:
            if self.is_state:
                path = self.current_trial['path']
                replay = state_fuzz(self.report.spec.state_machine, strategy='bfs', seed_paths=[path],
                                    max_depth=len(path) - 1, budget=1,
                                    known_deadlocks=set(self.report.kripke.deadlock_states) if self.report.kripke else None)
                value = {'scope': 'specification model only', 'path': path,
                         'findings': [asdict(c) for c in replay.crashes]}
            else:
                value = replay_input(self.generated, self.current_trial['input'])
            self.report.fuzz_replays.append(value)
            self.replay_output.setHtml('<h3>Output chạy lại</h3><pre>' + pretty(value) + '</pre>'
                                       '<p>Kết quả thuộc input này và môi trường hiện tại; chưa kết luận mọi input đều an toàn.</p>')
        except Exception as exc:  # noqa: BLE001 - keep replay failures visible without losing the campaign
            self.replay_output.setPlainText(f'Replay không hoàn tất: {exc}')

    def _guide_html(self):
        return '''<h3>Cách trình bày Chương 4 trong 6–7 phút</h3>
        <ol><li><b>Chuẩn bị:</b> chỉ target, mã v0/v1, seed, ngân sách và oracle ở bước 1.</li>
        <li><b>Input → output:</b> chọn refund_ratio; lọc lần thử có lỗi, chỉ mẫu số bằng 0,
        trace và ZeroDivisionError ở bước 2–3.</li>
        <li><b>Coverage:</b> chọn coverage-guided; chỉ input cha, phép đột biến,
        dòng mới và quyết định giữ input trong corpus.</li>
        <li><b>Magic value:</b> chọn webhook_bypass_token/concolic. Ở bước 4, mở query,
        điều kiện phủ định, SAT và model sinh cặp token. Chọn input được sinh để xem kết quả thực thi.</li>
        <li><b>Replay:</b> ở bước 5, chạy cùng input trên v0/v1 và đọc output thật.</li>
        <li><b>Chuỗi trạng thái:</b> chọn BFS/DFS ở bảng mô hình; phân biệt duyệt đặc tả
        với thực thi mã. Độ sâu đếm số cạnh, không đếm số node.</li>
        <li><b>Kết thúc:</b> xuất bằng chứng. Nêu lý do dừng và giới hạn; UNSUPPORTED/UNKNOWN
        không phải an toàn. Fuzzing chưa thấy lỗi không thay thế chứng minh CTL/SMT.</li></ol>
        <h3>File xuất</h3><p>Mỗi lần xuất có thư mục <code>fuzz_runs/&lt;run_id&gt;/</code> riêng:
        manifest và hash mã; từng chiến dịch có target.py, campaign.json, events.jsonl đầy đủ,
        corpus.json, crashes.json, coverage.json, inputs.dot và queries/*.smt2/*.json.
        state_exploration.json lưu toàn bộ chuỗi; replay_results.json lưu các lần replay đã bấm.</p>
        <p>Timeline phân trang 100 lần thử; file xuất không cắt log.</p>'''
