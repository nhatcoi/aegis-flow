"""Configured authentication must be modeled without treating valid credentials as bypass."""
import pytest

from core.codegen import generate_function_code
from core.fuzz_evidence import replay_input
from core.fuzzing import concolic_fuzz, fuzz_generated, load_function, run_oracle
from core.spec_loader import FunctionSpec


def auth():
    return generate_function_code(FunctionSpec('auth', 'python', 'magic_value', ['a', 'b'],
                                               magic_values=[7788, 9999]))


def test_unconfigured_patch_completes_with_explicit_fixed_environment(monkeypatch):
    monkeypatch.delenv('WEBHOOK_SECRET', raising=False)
    result = next(r for r in fuzz_generated(auth(), budget=20) if r.version == 'v1' and r.strategy == 'concolic')
    assert result.status == 'no_finding' and result.stop_reason == 'worklist_exhausted'
    assert result.assumptions and 'WEBHOOK_SECRET' in str(result.assumptions)
    assert result.queries and all(q['status'] == 'unsat' for q in result.queries)


@pytest.mark.parametrize('secret', ['7788:9999', '-2147483648:2147483647', '1:1', 'bad', '01:2', '-0:2'])
def test_configured_auth_explores_digest_result_and_replay_is_not_bypass(monkeypatch, secret):
    monkeypatch.setenv('WEBHOOK_SECRET', secret)
    gf = auth()
    result = next(r for r in fuzz_generated(gf, budget=25) if r.version == 'v1' and r.strategy == 'concolic')
    assert result.status == 'no_finding' and result.stop_reason == 'worklist_exhausted'
    assert not result.found
    for t in result.trials:
        assert t['value'] == (':'.join(map(str, t['input'])) == secret)
    if secret in {'7788:9999', '-2147483648:2147483647', '1:1'}:
        accepted = next(t for t in result.trials if t['value'] is True)
        assert any(t['value'] is False for t in result.trials)
        assert replay_input(gf, accepted['input'])[1]['finding'] is None
    else:
        assert not any(t['value'] for t in result.trials)


def test_unknown_library_operations_still_inconclusive(monkeypatch):
    monkeypatch.setenv('WEBHOOK_SECRET', '1:1')
    code = 'import os\ndef auth(a, b):\n    return os.environ.get(str(a), "")\n'
    r = concolic_fuzz(load_function(code, 'auth'), code, 'magic_value', budget=20)
    assert r.status == 'inconclusive' and r.stop_reason == 'unsupported'


def test_configured_auth_oracle_still_reports_unauthorized_success(monkeypatch):
    monkeypatch.setenv('WEBHOOK_SECRET', '3:4')
    func = load_function('def auth(a, b):\n    return True\n', 'auth')
    assert run_oracle(func, 'configured_auth', (1, 1)).finding == 'bypass'
    assert run_oracle(func, 'configured_auth', (3, 4)).finding is None


@pytest.mark.parametrize('code', [
    'import hmac\ndef auth(a,b):\n    return hmac.compare_digest(str(a), "7788") and b == 9999\n',
    'import os\ndef auth(a,b):\n    return os.environ.get(str(a), "") == "allow"\n',
    'import hmac\ndef auth(a,b):\n    return hmac.compare_digest(f"{a}:{b}", "7788:9999") and b == 9999\n',
])
def test_nested_library_calls_never_falsely_complete(code):
    result = concolic_fuzz(load_function(code, 'auth'), code, 'magic_value', budget=20)
    assert result.status == 'inconclusive' and result.stop_reason == 'unsupported'
    assert result.trials[0]['symbolic_supported'] is False
