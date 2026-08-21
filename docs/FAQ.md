# Frequently Asked Questions (FAQ & Comparison)

---

### 1. How does AegisFlow differ from Spring Statemachine?
* **Spring Statemachine** is a **runtime execution engine** that transitions application state when triggered by business events. It does not formally prove whether a `DEADLOCK` state is mathematically reachable or whether temporal invariants could be violated across edge-case variable combinations.
* **AegisFlow** is a **Static & Formal Verification Framework**: It analyzes state graphs, applies SMT Solvers (Z3), and Bounded Model Checking to mathematically prove correctness before deploying to production.

---

### 2. How does AegisFlow differ from Hibernate Validator (JSR-380)?
* **Hibernate Validator** validates field-level data at a **single point in time** (e.g., `@NotNull`, `@Min(18)`).
* **AegisFlow** enforces **temporal workflow-level constraints across state transitions**:
  * Temporal state delta tracking: `balance == old(balance) - amount`.
  * Inter-state dependency constraints: `isShipping ==> isPaid`.
  * Multi-state invariant preservation: `!(isDelivered && isCancelled)`.

---

### 3. How does AegisFlow differ from ArchUnit?
* **ArchUnit** validates code package and class dependency structures (e.g., Controllers must not call Repositories directly).
* **AegisFlow** verifies **Domain Logic & Business Rules** (state machine reachability, arithmetic contracts, and business invariants).

---

### 4. Do I need to install native Z3 binaries locally?
* Not required for general development. In upcoming releases, `aegis-flow-smt` will bundle cross-platform Z3 native binaries for Linux, macOS, and Windows.
* The core engine `aegis-flow-core` and `aegis-flow-spring-boot-starter` operate entirely on **standard Java 21 LTS** with zero native dependencies.

---

### 5. How should `fail-on-error` be used in CI/CD pipelines?
In CI/CD environments (GitHub Actions, GitLab CI), enable `aegisflow.verification.fail-on-error: true` or execute `mvn test`. If any invariant or rule is violated, the build fails immediately and produces actionable counter-example traces for developers.
