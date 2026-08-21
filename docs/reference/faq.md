# Frequently Asked Questions (FAQ)

---

### 1. How does AegisFlow differ from Spring Statemachine?
* **Spring Statemachine** is a **runtime execution engine** that transitions state when triggered by application events. It does not perform formal verification to mathematically prove the absence of deadlocks or invariant breaches.
* **AegisFlow** is a **Static & Formal Verification Framework**: It analyzes state graphs, applies SMT Solvers (Z3) and Bounded Model Checking to mathematically prove correctness before deploying to production.

---

### 2. How does AegisFlow differ from Hibernate Validator (JSR-380)?
* **Hibernate Validator** validates field-level data at a **single point in time** (`@NotNull`, `@Min(18)`).
* **AegisFlow** enforces **temporal workflow-level constraints across state transitions**:
  * Temporal state delta tracking: `balance == old(balance) - amount`.
  * Inter-state dependency constraints: `isShipping ==> isPaid`.
  * Multi-state invariant preservation: `!(isDelivered && isCancelled)`.

---

### 3. How does AegisFlow differ from ArchUnit?
* **ArchUnit** enforces package and class dependency rules (e.g., Controllers must not call Repositories directly).
* **AegisFlow** verifies **Domain Logic & Business Rules** (state machine reachability, arithmetic contracts, and business invariants).

---

### 4. Do I need to install native Z3 binaries locally?
* Not required for general development. The `aegis-flow-smt` module packages cross-platform Z3 bindings.
* The core engine `aegis-flow-core` and `aegis-flow-spring-boot-starter` operate entirely on **standard Java 21 LTS** with zero native dependencies.

---

### 5. How should `fail-on-error` be used in CI/CD pipelines?
In CI/CD environments (GitHub Actions, GitLab CI), enable `fail-on-error: true` or run `mvn test`. If any invariant or rule is violated, the build fails immediately and produces actionable counter-example traces for developers.
