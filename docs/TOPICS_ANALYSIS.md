# Topics Analysis & Transition to a Software Engineering Framework

This document analyzes the academic foundations of **Software Security, Formal Verification, and Testing**, and establishes the rationale for building the **AegisFlow (`aegis-flow`)** industrial framework.

---

## 1. Academic Foundations

Traditional academic courses in Formal Verification and Software Security are typically structured around four theoretical pillars:

1. **Pillar 1:** System Modeling & State Verification (Kripke Structures, Temporal Logic LTL/CTL, Bounded Model Checking - BMC).
2. **Pillar 2:** Software Security Auditing & Memory Safety (Static Analysis, Dataflow Taint Analysis).
3. **Pillar 3:** Propositional & First-Order Formal Proofs (Design by Contract, SMT Solvers such as Z3, Theorem Provers).
4. **Pillar 4:** Dynamic Testing & Fuzzing (Mutation Fuzzing, Coverage-guided Testing).

---

## 2. Software Engineering Market Opportunity

Existing developer tools only solve fragmented parts of application safety:

* **Spring Modulith / ArchUnit:** Enforces package and class dependency boundaries. Does not evaluate domain business logic or state machine transitions.
* **Jakarta Bean Validation (Hibernate Validator):** Evaluates static single-point field validations (`@NotNull`, `@Size`), incapable of proving temporal transitions (`CREATED -> PAID -> DELIVERED`) or multi-variable arithmetic constraints.

👉 **AegisFlow's Value Proposition:**  
Serving as the premier **Business Domain Verification Guard** for Java & Spring enterprise systems.

---

## 3. Modular Micro-Kernel Architecture

Each academic pillar maps to a dedicated, decoupled engine module:

```text
Pillar 1 (Kripke + BMC)    ──► aegis-flow-bmc      (State Graph & BMC Path Checker)
Pillar 2 (Static Analysis) ──► aegis-flow-core     (AST Type & Semantic Validator)
Pillar 3 (SMT / Z3)        ──► aegis-flow-smt      (Formal Contract & SMT Solver)
Pillar 4 (Fuzzing)         ──► aegis-flow-fuzz     (Business Workflow Mutation Fuzzer)
Ecosystem Integration      ──► aegis-flow-spring-boot-starter
```
