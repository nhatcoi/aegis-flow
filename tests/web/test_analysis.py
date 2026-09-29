import copy
import json
from pathlib import Path

import pytest
from atpm.advisory import advise, references
from atpm.analysis import (
    dead_guards,
    domain_escapes,
    scan_source,
    static_checks,
    unused_variables,
    vacuous_properties,
)
from atpm.generation import generate
from atpm.specification import Specification
from atpm.testing import exercise, role_of


@pytest.fixture
def refund():
    return Specification.model_validate(json.loads(Path('specs/payment_refund.json').read_text())).model_dump()


def failures(spec):
    return {item['name']: item.get('reason') for item in static_checks(spec, generate(spec))
            if item['verdict'] == 'FAIL'}


def test_reference_spec_passes_every_static_check(spec):
    assert failures(spec) == {}


def test_refund_spec_passes_every_static_check(refund):
    assert failures(refund) == {}


def test_domain_escape_detected_when_guard_stops_bounding_counter(spec):
    broken = copy.deepcopy(spec)
    confirm = next(t for t in broken['transitions'] if t['event'] == 'confirm')
    confirm['guard'] = {'and': confirm['guard']['and'][:3]}
    assert domain_escapes(broken) == ['confirm.captured_count = 3']
    assert 'Effect luôn nằm trong miền khai báo' in failures(broken)


def test_vacuous_property_detected(spec):
    broken = copy.deepcopy(spec)
    broken['properties'].append({'id': 'always', 'label': 'Luôn đúng',
                                 'expression': {'le': ['$captured_count', 9]}})
    assert vacuous_properties(broken) == ['always']


def test_unsatisfiable_guard_detected(spec):
    broken = copy.deepcopy(spec)
    retry = next(t for t in broken['transitions'] if t['event'] == 'retry')
    retry['guard'] = {'and': ['$shipped', {'not': ['$shipped']}]}
    assert dead_guards(broken) == ['retry']


def test_unreachable_status_detected(spec):
    broken = copy.deepcopy(spec)
    broken['variables']['status']['values'] = [*broken['variables']['status']['values'], 'ARCHIVED']
    assert 'ARCHIVED' in failures(broken)['Mọi trạng thái khai báo đều đạt tới được']


def test_unused_variable_detected(spec):
    broken = copy.deepcopy(spec)
    broken['variables']['spare'] = {'label': 'Không dùng', 'values': [False, True], 'initial': False}
    assert unused_variables(broken) == ['spare']
    assert unused_variables(spec) == []


@pytest.mark.parametrize('source, needle', [
    ('eval("1+1")', 'eval()'),
    ('import socket', 'socket'),
    ('from subprocess import run', 'subprocess'),
    ('x = 1', None),
])
def test_source_scan_flags_dangerous_constructs(source, needle):
    findings = scan_source('generated.py', source)
    if needle is None:
        assert findings == []
    else:
        assert any(needle in item for item in findings)


def test_generated_artifact_has_no_forbidden_construct(spec):
    artifact = generate(spec)
    for name, source in artifact['files'].items():
        if name.endswith('.py'):
            assert scan_source(name, source) == []


def test_roles_resolve_for_both_models(spec, refund):
    assert role_of(spec) == {'start': 'start', 'timeout': 'timeout', 'capture': 'confirm', 'ship': 'ship'}
    resolved = role_of(refund)
    assert resolved['capture'] == 'capture_full'
    # reconcile_refunded is a self-loop inside REFUNDED and must not take the refund role.
    assert resolved['refund'] == 'refund_full'


def test_refund_scenarios_run_on_extended_model_and_skip_on_basic(spec, refund):
    basic = {item['name']: item['verdict'] for item in exercise(spec)['results']}
    extended = {item['name']: item['verdict'] for item in exercise(refund)['results']}
    assert basic['Không hoàn tiền quá số đã thu'] == 'SKIP'
    assert extended['Không hoàn tiền quá số đã thu'] == 'PASS'
    assert extended['Không giao hàng sau khi đã hoàn tiền'] == 'PASS'
    assert 'FAIL' not in extended.values()


def test_references_collects_state_and_input_reads():
    expr = {'and': ['$shipped', {'eq': ['$input.amount_matches', True]}]}
    assert references(expr) == {'shipped', 'input.amount_matches'}


def test_advisory_marks_reference_spec_as_modelled(spec):
    report = advise(spec)
    by_id = {item['id']: item for item in report['items']}
    assert by_id['webhook_authenticity']['status'] == 'MODELED'
    assert by_id['fulfilment_gate']['status'] == 'MODELED'
    # The basic model deliberately excludes refunds and reconciliation.
    assert by_id['refund_coverage']['status'] == 'MISSING'
    assert by_id['reconciliation']['status'] == 'MISSING'
    assert report['spec_hash'] == advise(spec)['spec_hash']


def test_advisory_recognises_extended_model(refund):
    by_id = {item['id']: item for item in advise(refund)['items']}
    assert by_id['refund_coverage']['status'] == 'MODELED'
    assert by_id['reconciliation']['status'] == 'MODELED'


def test_advisory_flags_missing_fulfilment_gate(unsafe):
    by_id = {item['id']: item for item in advise(unsafe)['items']}
    assert by_id['fulfilment_gate']['status'] == 'MODELED'
    unguarded = copy.deepcopy(unsafe)
    unguarded['properties'] = [p for p in unguarded['properties']
                               if not isinstance(p['expression'], dict)
                               or next(iter(p['expression'])) != 'implies']
    flagged = {item['id']: item for item in advise(unguarded)['items']}
    assert flagged['fulfilment_gate']['status'] == 'MISSING'


def test_advisory_promotes_failed_verification_and_tests(spec):
    verification = {'results': [{'id': 'p', 'label': 'Chỉ giao khi đã thu tiền',
                                 'verdict': 'VIOLATED', 'depth': 3}]}
    tests = {'results': [{'name': 'Giao hàng sớm', 'verdict': 'FAIL'}]}
    report = advise(spec, verification, tests)
    ids = [item['id'] for item in report['items']]
    assert ids[:2] == ['verification_violated', 'tests_failed']
    assert report['severity_counts']['critical'] >= 2


def test_advisory_items_sorted_by_severity(spec):
    order = ['critical', 'high', 'medium', 'low']
    severities = [order.index(item['severity']) for item in advise(spec)['items']]
    assert severities == sorted(severities)
