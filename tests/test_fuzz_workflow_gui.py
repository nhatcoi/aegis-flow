"""Exercise the recorded workflow without opening a native window on the user's desktop."""
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication

from core.pipeline import run_pipeline
from core.spec_loader import load_specification
from gui.fuzz_workflow import FuzzWorkflow


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope='module')
def report():
    path = Path(__file__).resolve().parent.parent / 'dataset/specs_excel/payment_gateway_v0_spec.xlsx'
    return run_pipeline(load_specification(path), fuzz_budget=120, run_tools=False)


def test_workflow_pagination_solver_details_and_real_replay(app, report, monkeypatch):
    monkeypatch.delenv('WEBHOOK_SECRET', raising=False)
    widget = FuzzWorkflow()
    blackbox = next(r for r in report.fuzz if r.strategy == 'blackbox')
    widget.set_campaign(report, blackbox)
    assert widget.timeline.rowCount() == 100
    widget._move_page(1)
    assert widget.timeline.rowCount() == 20
    assert widget.current_trial['iteration'] == 101
    concolic = next(r for r in report.fuzz if r.function == 'webhook_bypass_token'
                    and r.version == 'v0' and r.strategy == 'concolic')
    widget.set_campaign(report, concolic)
    assert '7788' in widget.query.toPlainText() and '9999' in widget.query.toPlainText()
    widget.filter.setCurrentIndex(1)
    assert widget.current_trial['finding'] == 'bypass'
    widget._replay()
    assert report.fuzz_replays[-1][0]['finding'] == 'bypass'
    assert report.fuzz_replays[-1][1]['finding'] is None
    assert 'Output chạy lại' in widget.replay_output.toPlainText()
    patched = next(r for r in report.fuzz if r.function == 'webhook_bypass_token'
                   and r.version == 'v1' and r.strategy == 'concolic')
    widget.set_campaign(report, patched)
    assert 'CHƯA THẤY LỖI TRONG PHẠM VI CHẠY' in widget.summary.text()
    assert 'WEBHOOK_SECRET' in widget.setup.toPlainText()
    assert widget.current_trial is None  # the hit-only filter has no matching input
    assert not widget.replay_button.isEnabled()
    widget.close()


def test_state_replay_remains_explicitly_a_model_evaluation(app, report):
    widget = FuzzWorkflow()
    widget.set_campaign(report, report.state_fuzz[0], is_state=True)
    widget.filter.setCurrentIndex(1)
    assert widget.current_trial['findings']
    widget._replay()
    assert report.fuzz_replays[-1]['scope'] == 'specification model only'
    assert report.fuzz_replays[-1]['findings']
    widget.clear()
    assert widget.timeline.rowCount() == 0 and widget.current_trial is None
    assert not widget.replay_button.isEnabled()
    widget.close()


def test_native_fuzz_view_shows_exact_input_log_and_replay(app, report):
    from PyQt6.QtCore import QEventLoop, QTimer

    from core.c_fuzzing import fuzz_c_function
    from core.toolchain import compiler
    from gui.c_fuzz_workflow import CFuzzWorkflow

    if not compiler():
        pytest.skip('C compiler required')
    gf = next(g for g in report.functions if g.spec.kind == 'buffer_copy' and g.has_bug)
    result = fuzz_c_function(gf, 'v0', budget=3)
    widget = CFuzzWorkflow()
    widget.set_campaign(report, result)
    widget.timeline.selectRow(result.iterations - 1)
    assert 'AddressSanitizer' in widget.details.toPlainText()
    assert result.trials[-1]['stdin_hex'] in widget.details.toPlainText()
    count = len(report.fuzz_replays)
    loop = QEventLoop()
    widget.replayFinished.connect(loop.quit)
    QTimer.singleShot(60000, loop.quit)
    widget._replay()
    loop.exec()
    assert len(report.fuzz_replays) == count + 1
    replay = report.fuzz_replays[-1]
    assert replay['scope'] == 'C ASan/UBSan'
    assert replay['results'][0]['status'] == 'detected'
    assert replay['results'][1]['status'] == 'clean'
    assert 'v1' in widget.replay_output.toPlainText()
    widget.clear()
    assert widget.timeline.rowCount() == 0 and not widget.replay_button.isEnabled()
    widget.close()


def test_main_window_switches_native_campaign_and_budget_settings(app, report):
    from core.c_fuzzing import CFuzzResult
    from gui.qt_app import MainWindow
    from gui.theme import TOKENS

    gf = next(g for g in report.functions if g.language == 'c')
    result = CFuzzResult(gf.spec.name, 'v0', 32, 1, status='skipped', stop_reason='compiler_missing')
    previous = report.c_fuzz
    previous_python = report.fuzz
    report.fuzz = []
    report.c_fuzz = [result]
    window = MainWindow()
    window._on_done(report)
    window.fuzz_campaigns.setCurrentIndex(2)
    assert window.fuzz_views.currentWidget() is window.c_fuzz_workflow
    assert window.c_fuzz_workflow.result is result
    assert window.tbl_c_fuzz.item(0, 5).text() == 'CHƯA ĐỦ KẾT LUẬN'
    assert window.cards['fuzz'][0].styleSheet() == f"color: {TOKENS[window.mode]['warn']};"
    window.spn_c_fuzz.setValue(7)
    assert 'C 7' in window.btn_params.text()
    window._reset_params()
    assert window.spn_c_fuzz.value() == 32
    window.fuzz_campaigns.setCurrentIndex(0)
    assert window.fuzz_views.currentWidget() is window.fuzz_workflow
    report.c_fuzz = previous
    report.fuzz = previous_python
    window.close()


def test_deleting_native_view_during_replay_does_not_abort():
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent('''
        import time
        from types import SimpleNamespace
        from PyQt6.QtWidgets import QApplication
        from PyQt6 import sip
        import gui.c_fuzz_workflow as view
        from core.c_fuzzing import CFuzzResult
        from core.codegen import generate_function_code
        from core.spec_loader import FunctionSpec
        app = QApplication([])
        view.replay_c_input = lambda *args: (time.sleep(0.2) or [])
        gf = generate_function_code(FunctionSpec('copy_input', 'c', 'buffer_copy', ['data']))
        report = SimpleNamespace(functions=[gf], fuzz_replays=[])
        r = CFuzzResult('copy_input', 'v0', 1, 1)
        r.trials = [dict(iteration=1, input='empty', stdin_hex='', detections=[], status='clean', log='')]
        widget = view.CFuzzWorkflow()
        widget.set_campaign(report, r)
        widget._replay()
        sip.delete(widget)
        time.sleep(0.4)
        app.processEvents()
    ''')
    proc = subprocess.run([sys.executable, '-c', script], capture_output=True, timeout=10, check=False)
    assert proc.returncode == 0, proc.stderr.decode(errors='replace')
