import copy
import itertools

import pytest
import z3
from atpm.engine import TransitionError, evaluate, initial_state, step
from atpm.formal import decoded, explore, input_combinations, symbol, transition_formula, verify
from atpm.specification import Specification
from pydantic import ValidationError

TRUSTED = {'provider_verified': True, 'amount_matches': True, 'currency_matches': True}


def test_safe_spec_has_no_bounded_counterexample(spec):
    result = verify(spec, 30)
    assert all(p['verdict'] == 'BOUNDED_SAFE' and p['checked_depth'] == 30 for p in result['results'])


def test_unsafe_counterexample_is_shortest_and_replayable(unsafe):
    result = verify(unsafe, 8)
    broken = next(p for p in result['results'] if p['id'] == 'no_unpaid_shipping')
    assert broken['verdict'] == 'VIOLATED'
    assert broken['depth'] == 1
    state = initial_state(unsafe)
    for entry in broken['trace'][1:]:
        state = step(unsafe, state, entry['event'], entry['inputs'])
        assert state == entry['state']
    assert state['shipped'] and state['captured_count'] == 0


def test_depth_zero_checks_initial_state(spec):
    spec['variables']['shipped']['initial'] = True
    result = verify(spec, 0)
    assert result['results'][0]['depth'] == 0
    assert result['results'][0]['verdict'] == 'VIOLATED'


def test_graph_contains_only_reachable_states_and_total_relation(spec):
    graph = explore(spec)
    assert graph['complete']
    assert len(graph['nodes']) == 6
    assert all(not n['violations'] for n in graph['nodes'])
    for node in graph['nodes']:
        assert any(e['source'] == e['target'] == node['id'] and e['event'] == 'stutter' for e in graph['edges'])
    for edge in graph['edges']:
        if edge['event'] != 'stutter':
            assert step(spec, graph['nodes'][edge['source']]['state'], edge['event'], edge['inputs']) == graph['nodes'][edge['target']]['state']


def test_graph_truncation_is_explicit(spec):
    graph = explore(spec, limit=2)
    assert not graph['complete']
    assert len(graph['nodes']) == 2


def test_symbolic_relation_matches_concrete_engine_on_reachable_states(spec):
    """Independent symbolic-vs-Python cross-check, including disabled edges and all inputs."""
    before = {n: symbol(f'b_{n}', v) for n, v in spec['variables'].items()}
    after = {n: symbol(f'a_{n}', v) for n, v in spec['variables'].items()}
    inputs = {n: symbol(f'i_{n}', v) for n, v in spec['inputs'].items()}
    event = z3.Int('event')
    solver = z3.Solver()
    solver.add(transition_formula(spec, before, after, inputs, event))
    for node, data, (index, transition) in itertools.product(
        explore(spec)['nodes'], list(input_combinations(spec)), list(enumerate(spec['transitions']))
    ):
        solver.push()
        solver.add(event == index, *(before[k] == v for k, v in node['state'].items()),
                   *(inputs[k] == v for k, v in data.items()))
        try:
            expected = step(spec, node['state'], transition['event'], data)
        except TransitionError:
            assert solver.check() == z3.unsat
        else:
            assert solver.check() == z3.sat
            assert decoded(solver.model(), after) == expected
            solver.add(z3.Or(*(after[k] != v for k, v in expected.items())))
            assert solver.check() == z3.unsat, 'A concrete input must have a unique successor'
        solver.pop()


@pytest.mark.parametrize('mutation', [
    lambda s: s['transitions'][0].update(guard={'__import__': ['os']}),
    lambda s: s['transitions'][0].update(guard={'eq': ['$missing', 1]}),
    lambda s: s['transitions'][0].update(guard={'eq': ['$captured_count', True]}),
    lambda s: s['properties'][0].update(expression='$input.provider_verified'),
    lambda s: s['variables']['captured_count'].update(initial=True),
    lambda s: s['transitions'][0]['effects'].update(status='PENDING'),
    lambda s: s['transitions'][1].update(event='start'),
    lambda s: s['transitions'][0].update(to_state='MISSING'),
])
def test_invalid_specs_rejected_before_execution(spec, mutation):
    mutation(spec)
    with pytest.raises(ValidationError):
        Specification.model_validate(spec)


def test_assignments_are_simultaneous(spec):
    spec['transitions'][0]['effects'] = {'capture_verified': True, 'shipped': '$capture_verified'}
    state = step(spec, initial_state(spec), 'start')
    assert state['capture_verified'] is True
    assert state['shipped'] is False


def test_out_of_domain_update_is_rejected(spec):
    spec['transitions'][0]['effects'] = {'captured_count': 3}
    with pytest.raises(TransitionError):
        step(spec, initial_state(spec), 'start')
    assert len(explore(spec)['nodes']) == 1


def test_input_type_is_strict(spec):
    state = step(spec, initial_state(spec), 'start')
    with pytest.raises(TransitionError):
        step(spec, state, 'confirm', dict(TRUSTED, provider_verified=1))


def test_additional_arithmetic_and_boolean_operators(spec):
    expr = {'and': [{'ne': ['$status', 'FAILED']}, {'lt': [{'sub': [3, 1]}, 3]}, {'or': [False, True]}]}
    spec['transitions'][0]['guard'] = expr
    Specification.model_validate(copy.deepcopy(spec))
    assert evaluate(expr, initial_state(spec), {}) is True
    assert step(spec, initial_state(spec), 'start')['status'] == 'PENDING'
