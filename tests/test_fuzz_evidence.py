"""Ch.4 evidence must reproduce executions and solver models, not just show totals."""
import json
from pathlib import Path

import z3

from core.codegen import generate_function_code
from core.fuzz_evidence import export_fuzz_evidence, replay_input
from core.fuzzing import blackbox_fuzz, concolic_fuzz, load_function, state_fuzz
from core.pipeline import run_pipeline
from core.spec_loader import FunctionSpec, StateMachine, load_specification

SPECS = Path(__file__).resolve().parent.parent / 'dataset/specs_excel'


def magic():
    return generate_function_code(FunctionSpec('unlock', 'python', 'magic_value', ['a', 'b'],
                                               magic_values=[6284, 4917]))


def test_every_input_and_hit_is_recorded_without_truncation():
    gf = generate_function_code(FunctionSpec('ratio', 'python', 'divide', ['a', 'b']))
    result = blackbox_fuzz(load_function(gf.code_vulnerable, 'ratio'), 'divide', 250, seed=1)
    assert len(result.trials) == result.iterations == 250
    assert sum(t['finding'] is not None for t in result.trials) == result.hits
    assert all(t['trace'] and t['input'] for t in result.trials)
    assert result.unique_findings == 1
    assert result.stop_reason == 'budget_exhausted'


def test_solver_models_replay_and_queries_are_valid_smtlib(monkeypatch):
    monkeypatch.delenv('WEBHOOK_SECRET', raising=False)
    gf = magic()
    result = concolic_fuzz(load_function(gf.code_vulnerable, 'unlock'), gf.code_vulnerable,
                          'magic_value', budget=30)
    assert result.found
    for query in result.queries:
        solver = z3.Solver()
        solver.add(z3.parse_smt2_string(query['smt2']))
        assert str(solver.check()) == query['status']
        if query['model'] is not None:
            solver.add(*[z3.Int(k) == v for k, v in query['model'].items()])
            assert solver.check() == z3.sat
    finding = next(t for t in result.trials if t['finding'])
    parent_query = next(q for q in result.queries if q['id'] == finding['query_id'])
    assert parent_query['generated_input'] == finding['input']
    replay = replay_input(gf, finding['input'])
    assert replay[0]['finding'] == 'bypass' and replay[1]['finding'] is None
    assert replay[0]['code_sha256'] != replay[1]['code_sha256']


def test_unsat_and_unsupported_remain_distinct(monkeypatch):
    code = 'def f(x):\n    if x > 10:\n        if x < 5:\n            return True\n    return False\n'
    result = concolic_fuzz(load_function(code, 'f'), code, 'magic_value', 30)
    assert not result.found
    assert any(q['status'] == 'unsat' and q['generated_input'] is None for q in result.queries)
    monkeypatch.delenv('WEBHOOK_SECRET', raising=False)
    code = 'import os\ndef f(x):\n    return os.environ.get(str(x), "")\n'
    unsupported = concolic_fuzz(load_function(code, 'f'), code, 'magic_value', 10)
    assert unsupported.status == 'inconclusive'
    assert unsupported.stop_reason == 'unsupported'
    assert unsupported.iterations == 1


def test_state_coverage_counts_evaluated_paths_not_queued_neighbors():
    sm = StateMachine(states=['S0', 'S1', 'S2'], initial=['S0'],
                      transitions=[['S0', 'S1'], ['S1', 'S2']], labeling={})
    result = state_fuzz(sm, 'bfs', budget=1, max_depth=5)
    assert result.states_discovered == ['S0']
    assert result.transition_coverage == 0
    assert result.trials[0]['depth'] == 0
    result = state_fuzz(sm, 'bfs', budget=10, max_depth=1)
    assert result.states_discovered == ['S0', 'S1']
    assert max(t['depth'] for t in result.trials) == 1
    # A suggestive state name is not itself a violated invariant.
    safe = StateMachine(states=['duplicate_review'], initial=['duplicate_review'],
                        transitions=[['duplicate_review', 'duplicate_review']], labeling={})
    assert not state_fuzz(safe, 'bfs', budget=10).has_crash


def test_export_keeps_full_events_smt_and_previous_runs(tmp_path):
    report = run_pipeline(load_specification(SPECS / 'payment_gateway_v0_spec.xlsx'),
                          fuzz_budget=70, run_tools=False)
    first = export_fuzz_evidence(report, tmp_path)
    second = export_fuzz_evidence(report, tmp_path)
    assert first != second and first.exists()
    manifest = json.loads((second / 'manifest.json').read_text())
    assert len(manifest['campaigns']) == len(report.fuzz)
    assert manifest['spec_sha256']
    for campaign, result in zip(manifest['campaigns'], report.fuzz):
        folder = second / campaign['id']
        events = [json.loads(line) for line in (folder / 'events.jsonl').read_text().splitlines()]
        assert sum(e['event'] == 'execution' for e in events) == result.iterations
        assert sum(e['event'] == 'solver' for e in events) == len(result.queries)
        for query in result.queries:
            assert (folder / 'queries' / f"{query['id']}.smt2").exists()
        assert (folder / 'inputs.dot').read_text().startswith('digraph inputs')
    states = json.loads((second / 'state_exploration.json').read_text())
    assert len(states[0]['trials']) == report.state_fuzz[0].paths_explored
