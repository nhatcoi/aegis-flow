# Comprehensive User Guide

This user guide provides a complete overview of all verification concepts, annotation DSLs, and pipeline coordination within **AegisFlow**.

---

## 1. Core Architectural Pillars

AegisFlow verifies business applications across three complementary pillars:

```text
+-------------------------------------------------------------+
|                 AEGISFLOW VERIFICATION MODEL                |
|                                                             |
|   1. Finite State Machine (@InitialState, @State, @Terminal)|
|   2. Class Invariants (@Invariant, @Rule)                   |
|   3. Method Contracts (@Requires, @Ensures, old(...))       |
+-------------------------------------------------------------+
```

---

## 2. Defining Method Contracts with Temporal Tracking

```java
@Transition(from = "CREATED", to = "PAID", trigger = "pay")
@Requires("amount > 0 && accountBalance >= amount")
@Ensures("accountBalance == old(accountBalance) - amount")
public void pay(long amount) {
    this.accountBalance -= amount;
    this.state = OrderState.PAID;
}
```

* **`@Requires`**: Caller must guarantee that `amount > 0` and `accountBalance >= amount`.
* **`@Ensures`**: Guarantees that the new balance strictly equals the balance before invocation minus `amount`.
* **`old(x)`**: Evaluates variable $x$ at method entry.

---

## 3. Mini DSL Expression Syntax

AegisFlow incorporates a standalone recursive descent parser supporting standard operator precedence:

| Operator Category | Syntax | Example |
| :--- | :--- | :--- |
| **Implication** | `==>` | `isShipping ==> isPaid` |
| **Logical OR / AND** | `\|\|`, `&&` | `balance >= 0 && status != null` |
| **Equality / Relational** | `==`, `!=`, `<`, `<=`, `>`, `>=` | `amount <= balance` |
| **Arithmetic** | `+`, `-`, `*`, `/`, `%` | `balance - amount` |
| **Temporal Functions** | `old(var)` | `balance == old(balance) - amount` |

---

## 4. Verification Execution & Diagnostic Dashboard

```java
VerificationPipeline pipeline = VerificationPipeline.createDefault();
VerificationReport report = pipeline.verifyClass(OrderWorkflow.class);

System.out.println(report.toPrettyString());
```

```text
+==========================================================================+
|  AEGISFLOW VERIFICATION REPORT: OrderWorkflow                            |
+==========================================================================+
|  Overall Status: PASSED            Total Time: 2      ms                 |
+==========================================================================+
|  ENGINES SUMMARY:                                                        |
|    (No engines were executed)                                            |
+==========================================================================+
```
