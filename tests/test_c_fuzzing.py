"""Native fuzzing must execute instrumented C and preserve exact reproducing inputs."""
from pathlib import Path

import pytest

from core import toolchain
from core.codegen import generate_function_code
from core.spec_loader import FunctionSpec


def buffer_target():
    return generate_function_code(FunctionSpec('copy_input', 'c', 'buffer_copy', ['data'],
                                               buffer_size=16, bug='buffer-overflow'))


def test_native_campaign_finds_overflow_and_replays_same_bytes():
    from core.c_fuzzing import fuzz_c_function, replay_c_input

    if not toolchain.compiler():
        pytest.skip('C compiler required')
    gf = buffer_target()
    result = fuzz_c_function(gf, 'v0', budget=5, seed=1)
    assert 1 < result.iterations <= 5 and result.hits > 0
    assert result.status == 'detected'
    hit = next(t for t in result.trials if t['detections'])
    assert 'AddressSanitizer' in hit['log']
    assert hit['detections'][0][0] == 'stack-buffer-overflow'
    assert len({t['stdin_hex'] for t in result.trials}) == result.iterations
    replay = replay_c_input(gf, hit['stdin_hex'])
    assert replay[0]['trials'][0]['stdin_hex'] == replay[1]['trials'][0]['stdin_hex'] == hit['stdin_hex']
    assert replay[0]['status'] == 'detected'
    assert replay[1]['status'] == 'clean'


def test_missing_compiler_is_skipped(monkeypatch):
    from core.c_fuzzing import fuzz_c_function

    monkeypatch.setattr(toolchain, 'compiler', lambda: None)
    result = fuzz_c_function(buffer_target(), 'v0', budget=3)
    assert result.status == 'skipped' and result.iterations == 0
    assert result.verdict == 'CHƯA ĐỦ KẾT LUẬN'


def test_arithmetic_fuzzer_finds_ubsan_overflow():
    from core.c_fuzzing import fuzz_c_function

    if not toolchain.compiler():
        pytest.skip('C compiler required')
    gf = generate_function_code(FunctionSpec('add', 'c', 'arithmetic', ['a', 'b'], bug='integer-overflow'))
    result = fuzz_c_function(gf, 'v0', budget=4)
    assert any(d[0] == 'signed-integer-overflow' for t in result.trials for d in t['detections'])
    assert fuzz_c_function(gf, 'v1', budget=4).status == 'clean'


def test_seeded_inputs_are_reproducible_and_timeout_is_inconclusive():
    from core.c_fuzzing import fuzz_c_function, generate_c_inputs

    gf = buffer_target()
    assert list(generate_c_inputs(gf, 8, 42)) == list(generate_c_inputs(gf, 8, 42))
    if not toolchain.compiler():
        pytest.skip('C compiler required')
    gf.code_vulnerable = 'int copy_input(const char *s) { for (;;) {} return 0; }'
    result = fuzz_c_function(gf, 'v0', budget=1, timeout=0.05)
    assert result.status == 'inconclusive'
    assert result.stop_reason == 'timeout'
    assert result.trials[0]['status'] == 'timeout'


def test_build_failure_is_inconclusive():
    from core.c_fuzzing import fuzz_c_function

    if not toolchain.compiler():
        pytest.skip('C compiler required')
    gf = buffer_target()
    gf.code_vulnerable = 'this is not valid C'
    result = fuzz_c_function(gf, 'v0', budget=1)
    assert result.status == 'build-error' and result.iterations == 0
    assert result.verdict == 'CHƯA ĐỦ KẾT LUẬN'


def test_abnormal_exit_without_sanitizer_is_not_clean():
    from core.c_fuzzing import fuzz_c_function

    if not toolchain.compiler():
        pytest.skip('C compiler required')
    gf = buffer_target()
    gf.code_vulnerable = '#include <stdlib.h>\nint copy_input(const char *s) { exit(7); }'
    result = fuzz_c_function(gf, 'v0', budget=3)
    assert result.status == 'inconclusive' and result.iterations == 1
    assert result.stop_reason == 'crash'
    assert result.trials[0]['returncode'] == 7 and not result.found


def test_unsupported_target_is_explicitly_skipped():
    from core.c_fuzzing import fuzz_c_function

    gf = generate_function_code(FunctionSpec('divide', 'python', 'divide', ['a', 'b']))
    result = fuzz_c_function(gf, 'v0', budget=3)
    assert result.status == 'skipped' and result.stop_reason == 'unsupported_harness'


@pytest.mark.parametrize('native_status,hits,expected,status', [
    ('detected', 1, 'Không crash tại parse_webhook_signature', 'FAIL'),
    ('detected', 1, 'crash tại parse_webhook_signature', 'PASS'),
    ('inconclusive', 0, 'Không crash tại parse_webhook_signature', 'NOT_EVALUATED'),
    ('skipped', 0, 'Không crash tại parse_webhook_signature', 'NOT_EVALUATED'),
    ('clean', 0, 'Không crash tại parse_webhook_signature', 'PASS'),
])
def test_testcase_evaluation_includes_native_findings(native_status, hits, expected, status):
    from core.c_fuzzing import CFuzzResult
    from core.pipeline import PipelineReport, evaluate_test_case
    from core.spec_loader import TestCase, load_specification

    spec = load_specification(Path(__file__).resolve().parent.parent /
                              'dataset/specs/payment_gateway_v0_spec.json')
    rep = PipelineReport(spec, 1, 32)
    rep.c_fuzz = [CFuzzResult('parse_webhook_signature', 'v0', 32, 1,
                              status=native_status, hits=hits, iterations=1)]
    tc = TestCase('TC-native', expected_result=expected)
    assert evaluate_test_case(tc, rep).status == status


def test_native_arithmetic_input_is_used_by_testcase_evaluation():
    from core.c_fuzzing import CFuzzResult
    from core.pipeline import PipelineReport, evaluate_test_case
    from core.spec_loader import TestCase, load_specification

    spec = load_specification(Path(__file__).resolve().parent.parent /
                              'dataset/specs/payment_gateway_v0_spec.json')
    rep = PipelineReport(spec, 1, 32)
    native = CFuzzResult('calculate_total_payment', 'v0', 32, 1, status='detected', hits=1, iterations=3)
    native.trials = [{'stdin_hex': b'0 0\n'.hex(), 'detections': []},
                     {'stdin_hex': b'2147483647 1\n'.hex(),
                      'detections': [('signed-integer-overflow', 'CWE-190', 5)]}]
    rep.c_fuzz = [native]
    tc = TestCase('TC-native-input', expected_result='crash tại calculate_total_payment với (2147483647, 1)')
    assert evaluate_test_case(tc, rep).status == 'PASS'
    clean_input = TestCase('TC-native-clean', expected_result='crash tại calculate_total_payment với (0, 0)')
    assert evaluate_test_case(clean_input, rep).status == 'FAIL'


def test_pipeline_exports_native_evidence_and_no_tools_skips_it(tmp_path):
    import json

    from core.fuzz_evidence import export_fuzz_evidence
    from core.pipeline import run_pipeline
    from core.reporter import generate_markdown_report, summary_dict
    from core.spec_loader import load_specification

    spec = load_specification(Path(__file__).resolve().parent.parent /
                              'dataset/specs/payment_gateway_v0_spec.json')
    skipped = run_pipeline(spec, run_tools=False, fuzz_budget=10)
    assert skipped.c_fuzz == []
    if not toolchain.compiler():
        pytest.skip('C compiler required')
    report = run_pipeline(spec, fuzz_budget=10, c_fuzz_budget=4)
    assert len(report.c_fuzz) == 2 * len([g for g in report.functions if g.language == 'c'])
    assert all(r.budget == 4 for r in report.c_fuzz)
    assert summary_dict(report)['c_fuzz'][0]['strategy'] == 'blackbox + ASan/UBSan'
    assert 'C · ASan/UBSan' in generate_markdown_report(report)
    assert any('Fuzzing C' in tool for f in report.audit.findings for tool in f.tools)
    root = export_fuzz_evidence(report, tmp_path)
    manifest = json.loads((root / 'manifest.json').read_text())
    native = next(c for c in manifest['campaigns'] if c.get('language') == 'c' and c['hits'])
    folder = root / native['id']
    campaign = json.loads((folder / 'campaign.json').read_text())
    assert campaign['source_sha256'] == native['source_sha256']
    assert (folder / 'harness.c').exists()
    hit = json.loads((folder / 'crashes.json').read_text())[0]
    assert (folder / f"crash_{hit['iteration']}.stdin").read_bytes().hex() == hit['stdin_hex']
    assert 'AddressSanitizer' in (folder / f"crash_{hit['iteration']}.log").read_text()
