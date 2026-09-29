"""Tests for the C analyzer, sanitizer toolchain, SMT checks, AST metrics and fuzzers."""
import pytest

from core.arithmetic_z3 import check_arithmetic_spec
from core.c_analyzer import analyze_c_source
from core.codegen import generate_function_code
from core.fuzzing import (
    UnsafeCodeError,
    blackbox_fuzz,
    concolic_fuzz,
    coverage_guided_fuzz,
    fuzz_generated,
    load_function,
)
from core.spec_loader import ArithmeticCheck, FunctionSpec
from core.static_ast import function_metrics
from core.toolchain import compiler, run_sanitizers

C_FUNCS = {
    "buffer-overflow": FunctionSpec("parse_sig", "c", "buffer_copy", ["raw"], 32, "buffer-overflow"),
    "memory-leak": FunctionSpec("write_log", "c", "alloc_release", [], 32, "memory-leak"),
    "double-free": FunctionSpec("close_session", "c", "alloc_release", [], 16, "double-free"),
    "use-after-free": FunctionSpec("release_buf", "c", "alloc_release", [], 8, "use-after-free"),
}
EXPECTED_RULE = {"buffer-overflow": "dangerous-function", "memory-leak": "memory-leak",
                 "double-free": "double-free", "use-after-free": "use-after-free"}


# --- codegen ------------------------------------------------------------------
def test_no_declared_bug_means_no_vulnerable_variant():
    gf = generate_function_code(FunctionSpec("parse_id", "c", "buffer_copy", ["raw"], 16, None))
    assert not gf.has_bug
    assert "strcpy" not in gf.code_vulnerable


def test_magic_value_patch_is_valid_python():
    gf = generate_function_code(FunctionSpec("unlock", "python", "magic_value", ["a", "b"], magic_values=[7, 9]))
    assert load_function(gf.code_safe, "unlock")(7, 9) is False


# --- static analyzer ------------------------------------------------------------
@pytest.mark.parametrize("bug", list(C_FUNCS))
def test_static_scanner_flags_v0_and_clears_v1(bug):
    gf = generate_function_code(C_FUNCS[bug])
    v0 = analyze_c_source(gf.code_vulnerable)
    assert [f.rule for f in v0] == [EXPECTED_RULE[bug]]
    assert analyze_c_source(gf.code_safe) == []


@pytest.mark.parametrize(
    "src, rule",
    [
        ("void f(char *s){ char b[8]; sprintf(b, \"%s\", s); }", "dangerous-function"),
        ("void f(char *s){ printf(s); }", "format-string"),
        ("void f(void){ char *p = malloc(4); p[0] = 1; free(p); }", "malloc-unchecked"),
        ("void f(int n){ int *p = malloc(n * 4); if (!p) return; free(p); }", "malloc-size-overflow"),
        ("void f(void){ char *p = malloc(4); if (!p) return; p = 0; }", "memory-leak"),
    ],
)
def test_static_scanner_rules(src, rule):
    assert rule in [f.rule for f in analyze_c_source(src)]


def test_static_scanner_ignores_comments_and_strings():
    src = 'void f(void){ /* strcpy(a, b); */ puts("free(p); strcpy"); }'
    assert analyze_c_source(src) == []


def test_free_then_null_is_clean():
    src = "void f(void){ char *p = malloc(4); if (p == NULL) return; free(p); p = NULL; }"
    assert analyze_c_source(src) == []


# --- sanitizers -----------------------------------------------------------------
@pytest.mark.skipif(compiler() is None, reason="no C compiler")
@pytest.mark.parametrize("bug, cwe", [("buffer-overflow", "CWE-121"), ("double-free", "CWE-415"),
                                      ("use-after-free", "CWE-416")])
def test_asan_detects_v0_not_v1(tmp_path, bug, cwe):
    gf = generate_function_code(C_FUNCS[bug])
    v0 = run_sanitizers(gf, "v0", tmp_path)
    v1 = run_sanitizers(gf, "v1", tmp_path)
    assert v0.status == "detected" and cwe in [d[1] for d in v0.detections]
    assert v1.status == "clean"


@pytest.mark.skipif(compiler() is None, reason="no C compiler")
def test_ubsan_detects_signed_overflow(tmp_path):
    gf = generate_function_code(FunctionSpec("add", "c", "arithmetic", ["a", "b"], bug="integer-overflow"))
    assert "CWE-190" in [d[1] for d in run_sanitizers(gf, "v0", tmp_path).detections]
    assert run_sanitizers(gf, "v1", tmp_path).status == "clean"


# --- SMT ------------------------------------------------------------------------
def test_overflow_witness_respects_int32_and_condition():
    r = check_arithmetic_spec(ArithmeticCheck(
        "total", ["amount", "fee"], "amount > 0 and fee > 0 and amount > 2000000000", "amount + fee"))
    assert r.overflow_possible and r.overflow_under_condition
    assert all(-2**31 <= v <= 2**31 - 1 for v in r.overflow_values.values())
    assert r.overflow_values["amount"] > 2_000_000_000
    assert r.bv_overflow and r.wrapped_value < 0
    assert r.patch_status == "unsat"


def test_no_overflow_when_domain_is_small():
    r = check_arithmetic_spec(ArithmeticCheck("tiny", ["x"], "x >= 0 and x < 10", "x"))
    assert not r.overflow_possible
    assert not r.bv_overflow


# --- AST metrics ------------------------------------------------------------------
def test_mccabe_of_magic_value():
    gf = generate_function_code(FunctionSpec("unlock", "python", "magic_value", ["a", "b"], magic_values=[7, 9]))
    m = function_metrics(gf, "v0")
    assert m.cyclomatic == 3 and m.nesting_depth == 2
    assert m.conditions == ["a == 7", "b == 9"]


# --- fuzzing ------------------------------------------------------------------------
def test_sandbox_rejects_dangerous_code():
    with pytest.raises(UnsafeCodeError):
        load_function("import subprocess\ndef f(a):\n    return a\n", "f")
    with pytest.raises(UnsafeCodeError):
        load_function("def f(a):\n    return a.__class__\n", "f")


def test_concolic_beats_blackbox_on_magic_value():
    gf = generate_function_code(
        FunctionSpec("unlock", "python", "magic_value", ["a", "b"], magic_values=[6284, 4917]))
    f = load_function(gf.code_vulnerable, "unlock")
    assert not blackbox_fuzz(f, "magic_value", 3000, seed=1).found
    assert not coverage_guided_fuzz(f, "magic_value", 3000, seed=1).found
    c = concolic_fuzz(f, gf.code_vulnerable, "magic_value", 50)
    assert c.found and c.first_input == (6284, 4917) and c.first_hit <= 15


def test_divide_by_zero_found_and_patched():
    gf = generate_function_code(FunctionSpec("ratio", "python", "divide", ["a", "b"]))
    results = {(r.version, r.strategy): r for r in fuzz_generated(gf, 1000, seed=1)}
    assert results[("v0", "concolic")].found
    assert results[("v0", "concolic")].first_input[1] == 0
    assert results[("v0", "blackbox")].cwe == "CWE-369"
    assert not any(r.found for (v, _), r in results.items() if v == "v1")


def test_fuzzing_is_reproducible():
    gf = generate_function_code(FunctionSpec("ratio", "python", "divide", ["a", "b"]))
    f = load_function(gf.code_vulnerable, "ratio")
    a, b = blackbox_fuzz(f, "divide", 500, seed=7), blackbox_fuzz(f, "divide", 500, seed=7)
    assert (a.hits, a.first_hit, a.first_input) == (b.hits, b.first_hit, b.first_input)
