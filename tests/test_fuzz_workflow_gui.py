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
    assert 'CHƯA ĐỦ KẾT LUẬN' in widget.summary.text()
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
