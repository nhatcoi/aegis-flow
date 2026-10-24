# ASan fuzzing implementation plan

**Goal:** Connect seeded input generation to real C executions instrumented with ASan/UBSan, expose campaigns and replay in Ch.4, and persist reproducing inputs and logs.

**Architecture:** A subprocess-based black-box runner compiles each target once and feeds each test over stdin in a separate process. Supported generated signatures: buffer_copy, arithmetic, alloc_release (call counts). Independent C budget defaults to 32; stop at first sanitizer finding. Python fuzzing is unchanged. This is not libFuzzer or coverage-guided native fuzzing.

**Constraints:** Preserve existing result files. No new dependencies. Missing compiler, unsupported harness, build failure, timeout and abnormal exit without sanitizer diagnosis must remain explicit. macOS leak detection remains disabled. Retain source, harness, flags, sanitizer environment, exact stdin and raw logs for reproduction. GUI replay uses the exact selected stdin on both variants.

## Tasks

- [x] Write native runner tests and observe missing-feature failure; implement deterministic inputs, compilation, isolation, classifications and replay.
- [x] Integrate separate C campaigns into pipeline, CLI, CWE evidence, summary/report and immutable fuzz evidence exports. Test real instrumented executions and exported reproduction.
- [x] Add C campaign table, trial details and replay to Ch.4; expose budget in settings. Test offscreen GUI selection and real replay.
- [x] Document usage and limits; run complete pytest, lint and CLI end-to-end with sanitizer results.

## Review focus

Build errors and absent compilers cannot pass; timeouts and non-sanitizer crashes cannot pass; safe replay must use identical bytes; each crash must retain raw input and log; no-tools must avoid native execution.

## Verification

- Full suite: `uv run pytest -q` — 137 passed; one existing TestCase collection warning.
- `uv run ruff check core gui tests scripts main.py` and `git diff --check` — clean.
- CLI run: payment_gateway_v0, Python budget 200, C budget 8, seed 1, output `results/asan_fuzz_demo/`.
- 12 native campaigns; v0 detected stack overflow, double free, use after free and signed integer overflow. All six v1 campaigns completed 8 inputs without detection. macOS leak checking remains unavailable.
- Exported source/harness hashes verified; rebuilding from the exported command and replaying exported stdin reproduced the stack overflow.
- Review regressions cover deletion during asynchronous replay, incomplete summary-card status, native findings in test-case grading and exclusion of clean inputs from concrete crash expectations.
