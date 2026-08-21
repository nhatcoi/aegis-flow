# Overview & Problem Statement

## 1. Challenges in Enterprise Applications

In complex domains such as **E-Commerce**, **Digital Banking (Fintech)**, **Logistics**, and **Warehouse Management**, subtle logical flaws frequently lead to severe business issues:

* **Illegal State Transitions:** Orders being shipped (`SHIPPING`) before payment is completed, or delivered orders (`DELIVERED`) transitioning to cancelled (`CANCELLED`).
* **Temporal Invariant Violations:** Account balances dropping below zero after a sequence of transactions, or refund amounts exceeding captured totals.
* **Deadlocks & Unreachable States:** States that cannot be reached or workflows trapped in circular loops unable to terminate at a valid `@TerminalState`.

::: danger RISK
Traditional unit tests cannot cover all combinatorial state spaces and variable valuations, leading to edge-case bugs slipping into production.
:::

---

## 2. Market Gap Analysis

Existing Java libraries only address isolated aspects of application correctness:

| Library | Scope | Limitation for Formal Verification |
| :--- | :--- | :--- |
| **Spring Statemachine** | Runtime event-driven execution | Cannot mathematically prove absence of deadlocks or invariant breaches |
| **Hibernate Validator (JSR-380)** | Single-point field validation | Cannot enforce temporal delta constraints (`old(balance) - amount`) |
| **ArchUnit** | Package/class architectural structure | Does not verify domain logic or state machine transitions |
| **AegisFlow** | **Formal verification of domain workflows & counter-example generation** | **Mathematically guarantees correctness before deployment** |

---

## 3. Core Pillars of AegisFlow

```text
+-------------------------------------------------------------+
|                 BUSINESS WORKFLOW MODEL                     |
|                                                             |
|   1. State Machine:    @InitialState, @State, @TerminalState|
|   2. Transitions:      @Transition (from, to, trigger, guard|
|   3. Invariants:       @Invariant (must hold at all states) |
|   4. Business Rules:   @Rule (implication logic ==>)        |
|   5. Method Contracts: @Requires, @Ensures, old(...)        |
+-------------------------------------------------------------+
```

1. **State Space & Reachability Analysis:** Constructs state graphs to detect deadlocks and unreachable states.
2. **SMT Formal Verification:** Translates `@Invariant` and `@Rule` predicates into first-order logic formulas for SMT Solvers (Z3) to verify or produce counter-examples.
3. **Design by Contract:** Verifies method preconditions (`@Requires`) and postconditions (`@Ensures`) with temporal state inspection (`old(...)`).
