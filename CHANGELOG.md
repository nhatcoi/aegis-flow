# Changelog

All notable changes to the **AegisFlow** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0-SNAPSHOT] - 2026-08-21

### Added
* **Core Architecture (`aegis-flow-core`)**:
  * Rich Annotation DSL: `@BusinessWorkflow`, `@InitialState`, `@State`, `@TerminalState`, `@Transition`, `@Invariant`, `@Rule`, `@Requires`, `@Ensures`, `@Verified`.
  * Complete Recursive Descent Expression Parser (`MiniExpressionParser`) supporting arithmetic, boolean logic, implication (`==>`), and temporal evaluation (`old(...)`).
  * AST Data Structures (`BinaryOpNode`, `UnaryOpNode`, `FunctionCallNode`, `IdentifierNode`, `LiteralNode`).
  * Scanner Engine (`WorkflowScanner`) to parse workflow classes into Intermediate Representation (`WorkflowDefinition`).
  * SPI Specification (`VerificationEngine`, `VerificationContext`, `EngineResult`) for modular plug-and-play verification engines.
  * Verification Pipeline (`VerificationPipeline`) with diagnostic logging and ASCII dashboard reporter (`VerificationReport`).
* **Spring Boot 3 Starter (`aegis-flow-spring-boot-starter`)**:
  * AutoConfiguration integration with `@EnableBusinessVerification`.
  * Automatic workflow bean discovery and startup verification runner (`BusinessVerificationRunner`).
  * Centralized report registry service (`VerificationService`).
  * Configurable failure policies via `aegisflow.verification.fail-on-error`.
* **Samples (`aegis-flow-samples`)**:
  * `aegis-flow-sample-order`: Pure Java Order Lifecycle verification sample.
  * `aegis-flow-sample-spring-boot`: Spring Boot 3 Web sample demonstrating REST controllers, multi-step workflows, and `@SpringBootTest` integration.
* **Documentation & Multi-Language Support**:
  * Modern VitePress documentation with full English (`/`) and Vietnamese (`/vi/`) support.
  * Standard MIT License added.

---

## [Roadmap - Future Releases]

### [0.2.0] - Planned
* **SMT Engine (`aegis-flow-smt`)**:
  * Native Z3 Java bindings packaging.
  * First-order logic translation for complex multi-variable state transitions.
* **Bounded Model Checking (`aegis-flow-bmc`)**:
  * Finite state graph traversal with deadlock detection and unreachable state alerts.
* **Fuzzing Engine (`aegis-flow-fuzz`)**:
  * Property-based fuzz testing and randomized transition path exploration.
