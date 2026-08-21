# Changelog

All notable changes to the **AegisFlow** project will be documented in this section.

---

## [0.1.0-SNAPSHOT] - 2026-08-21

### Core Engine & Architecture (`aegis-flow-core`)
* **Annotation Suite:** Added `@BusinessWorkflow`, `@InitialState`, `@State`, `@TerminalState`, `@Transition`, `@Invariant`, `@Rule`, `@Requires`, `@Ensures`, `@Verified`.
* **Mini Expression DSL:** Custom Recursive Descent AST Parser with arithmetic, boolean logic, implication (`==>`), and temporal evaluation (`old(...)`).
* **Micro-Kernel Pipeline:** Engine coordination pipeline with Java ServiceLoader SPI support and counter-example diagnostic generation.

### Spring Boot 3 Integration (`aegis-flow-spring-boot-starter`)
* **AutoConfiguration:** Native Spring Boot 3 Starter enabled via `@EnableBusinessVerification`.
* **Lifecycle Runner:** Automated workflow verification during application startup with console dashboard reporting.
* **REST & Management Service:** `VerificationService` exposing runtime verification reports for monitoring and CI/CD pipelines.

### Documentation & Internationalization
* Multi-language documentation site powered by VitePress with English and Vietnamese.
* MIT License and comprehensive architectural specifications.

---

## Upcoming Releases

### [0.2.0] - In Progress
* **SMT Engine (`aegis-flow-smt`):** Integration with Microsoft Z3 Theorem Prover.
* **BMC Engine (`aegis-flow-bmc`):** State reachability analysis and deadlock detection algorithms.
* **Fuzzing Engine (`aegis-flow-fuzz`):** Multi-threaded state transition permutation fuzzer.
