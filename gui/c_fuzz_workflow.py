"""Native sanitizer campaign evidence and asynchronous exact-input replay."""
from __future__ import annotations

import html
import json
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout, QWidget

from core.c_fuzzing import replay_c_input

from .fuzz_workflow import table

# Python owns worker lifetimes independently of Qt widgets. Destroying a view
# during replay must not destroy a running QThread or abort the application.
_REPLAY_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix='aegis-c-replay')


class _ReplayWorker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, gf, stdin_hex, timeout):
        super().__init__()
        self.gf, self.stdin_hex, self.timeout = gf, stdin_hex, timeout

    def run(self):
        try:
            self.finished.emit(replay_c_input(self.gf, self.stdin_hex, self.timeout))
        except Exception as exc:  # noqa: BLE001 - surfaced in the replay panel
            self.finished.emit({'error': str(exc)})


class CFuzzWorkflow(QWidget):
    replayFinished = pyqtSignal()
    exportRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report = self.result = self.current_trial = None
        self.future = self.worker = None
        layout = QVBoxLayout(self)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.timeline = table(['Lần', 'Input', 'Trạng thái', 'Sanitizer / CWE'])
        self.timeline.itemSelectionChanged.connect(self._selected)
        trials = QWidget()
        trial_layout = QVBoxLayout(trials)
        trial_layout.addWidget(self.timeline)
        self.details = QTextBrowser()
        trial_layout.addWidget(self.details, 2)
        self.tabs.addTab(trials, 'Input → Thực thi → ASan/UBSan')
        self.config = QTextBrowser()
        self.tabs.addTab(self.config, 'Cấu hình · Source · Harness')
        replay = QWidget()
        replay_layout = QVBoxLayout(replay)
        self.replay_button = QPushButton('Replay input đang chọn trên C v0/v1')
        self.replay_button.clicked.connect(self._replay)
        replay_layout.addWidget(self.replay_button)
        self.replay_output = QTextBrowser()
        replay_layout.addWidget(self.replay_output)
        self.tabs.addTab(replay, 'Replay v0/v1')
        export = QPushButton('Xuất input, source, harness và log đầy đủ')
        export.clicked.connect(self.exportRequested.emit)
        layout.addWidget(export)
        self.clear()

    def clear(self):
        self.report = self.result = self.current_trial = None
        self.timeline.setRowCount(0)
        self.details.clear()
        self.config.clear()
        self.replay_output.clear()
        self.replay_button.setEnabled(False)
        self.summary.setText('Chọn chiến dịch C · ASan/UBSan. Black-box; không đo native coverage.')

    def set_campaign(self, report, result):
        from PyQt6.QtWidgets import QTableWidgetItem

        self.clear()
        self.report, self.result = report, result
        self.summary.setText(f'{result.function} · {result.version} · {result.verdict} · '
                             f'{result.iterations}/{result.budget} lần · {result.hits} hit · '
                             f'dừng: {result.stop_reason}. {result.note}')
        self.config.setPlainText(json.dumps({'seed': result.seed, 'budget': result.budget,
                                            'timeout': result.timeout, 'command': result.command,
                                            'environment': result.environment,
                                            'source_sha256': result.source_sha256}, ensure_ascii=False, indent=2)
                                 + '\n\nBUILD LOG\n' + result.build_log
                                 + '\n\nSOURCE\n' + result.source + '\n\nHARNESS\n' + result.harness)
        self.timeline.setRowCount(len(result.trials))
        for row, trial in enumerate(result.trials):
            for col, value in enumerate([trial['iteration'], trial['input'], trial['status'],
                                         '; '.join(f'{k} / {c} / dòng {ln}' for k, c, ln in trial['detections'])]):
                self.timeline.setItem(row, col, QTableWidgetItem(str(value)))
        if result.trials:
            self.timeline.selectRow(next((i for i, t in enumerate(result.trials) if t['detections']), 0))

    def _selected(self):
        row = self.timeline.currentRow()
        if not self.result or not 0 <= row < len(self.result.trials):
            return
        self.current_trial = self.result.trials[row]
        self.details.setPlainText(json.dumps(self.current_trial, ensure_ascii=False, indent=2))
        self.replay_button.setEnabled(self.future is None)

    def _replay(self):
        if self.future is not None or self.current_trial is None:
            return
        self.pending_report, self.pending_result = self.report, self.result
        gf = next(g for g in self.report.functions if g.spec.name == self.result.function)
        self.worker = _ReplayWorker(gf, self.current_trial['stdin_hex'], self.result.timeout)
        self.worker.finished.connect(self._replayed)
        self.replay_button.setEnabled(False)
        self.replay_output.setPlainText('Đang biên dịch và replay cùng stdin trên C v0/v1…')
        self.tabs.setCurrentIndex(2)
        self.future = _REPLAY_EXECUTOR.submit(self.worker.run)

    def _replayed(self, results):
        self.pending_report.fuzz_replays.append({'scope': 'C ASan/UBSan', 'results': results})
        if self.result is self.pending_result:
            if isinstance(results, dict):
                self.replay_output.setPlainText(results['error'])
            else:
                self.replay_output.setHtml(''.join(
                    '<h3>' + html.escape(r['version'] + ': ' + r['status']) + '</h3><pre>'
                    + html.escape(json.dumps({'stop_reason': r['stop_reason'], 'source_sha256': r['source_sha256'],
                                              'build_log': r['build_log'], 'trials': r['trials']},
                                             ensure_ascii=False, indent=2)) + '</pre>' for r in results))
        self._finished()

    def _finished(self):
        self.future = self.worker = None
        self.replay_button.setEnabled(self.current_trial is not None)
        self.replayFinished.emit()
