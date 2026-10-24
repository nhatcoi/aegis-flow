# Fix concolic configured authentication

**Goal:** Finish supported v1 authentication campaigns without masking unsupported execution or valid runtime findings.

**Approach:** Preserve runtime authentication code. Model fixed-key environment reads as fixed string values and `hmac.compare_digest(f"{a}:{b}", expected)` as canonical decimal integer-pair equality. Record digest outcome as an implicit branch. Signed int32 constraints remain in every query. Emit fixed-environment and no-timing-analysis assumptions in GUI and export/report. Unknown library calls remain inconclusive.

**Oracle:** Configured-auth success is legitimate only when the exact input string matches the configured secret; unauthorized success remains a bypass. The hardcoded vulnerable variant retains its bypass oracle. Apply identical oracle policy to fuzzing and replay.

- [x] Reproduce unsupported v1 on empty/configured secrets with failing regression tests.
- [x] Implement bounded library models and explicit assumptions.
- [x] Test malformed/noncanonical strings, int32 boundaries, legitimate/unauthorized success and unsupported calls.
- [x] Update GUI expectations and docs.
- [x] Verify full suite, lint and saved v1 CLI result.

Verification: 149 tests passed (one existing TestCase collection warning); Ruff clean. Saved
`results/concolic_v1_demo/` with 6/6 concolic campaigns reporting no_finding/worklist_exhausted,
12/12 test cases PASS, and explicit fixed-environment assumptions. Review added three regressions
ensuring unsupported calls nested inside return expressions cannot falsely complete analysis.
