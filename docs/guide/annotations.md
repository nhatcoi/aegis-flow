# Annotations DSL Reference

A comprehensive guide to all AegisFlow annotations.

---

## 1. Annotation Summary

| Annotation | Target | Purpose |
| :--- | :--- | :--- |
| **`@BusinessWorkflow`** | Class | Identifies a class as a verifiable business process |
| **`@InitialState`** | Enum / Field | Designates the single entry state of the workflow |
| **`@State`** | Enum / Field | Designates an intermediate workflow state |
| **`@TerminalState`** | Enum / Field | Designates a terminal completion state |
| **`@Transition`** | Method | Defines a valid transition edge (`from`, `to`, `trigger`, `guard`) |
| **`@Invariant`** | Class | Defines a condition that must always hold across all states |
| **`@Rule`** | Class | Defines an implication business rule (`==>`) |
| **`@Requires`** | Method | Defines a precondition before method invocation |
| **`@Ensures`** | Method | Defines a postcondition guaranteed upon method completion |
| **`@Verified`** | Class / Package | Activates verification triggers during test or application startup |

---

## 2. Repeatable Annotations

AegisFlow annotations natively support repetition without wrapper clutter:

::: code-group

```java [Multiple Transitions]
@Transition(from = "CREATED", to = "CANCELLED", trigger = "cancel")
@Transition(from = "PAID", to = "CANCELLED", trigger = "cancel")
public void cancel() {
    this.status = OrderStatus.CANCELLED;
}
```

```java [Multiple Invariants]
@Invariant(value = "balance >= 0", description = "Balance cannot be negative")
@Invariant(value = "!(isDelivered && isCancelled)", description = "Cannot be both delivered and cancelled")
public class AccountWorkflow { ... }
```

```java [Method Contracts]
@Requires("amount > 0")
@Requires("balance >= amount")
@Ensures("balance == old(balance) - amount")
public void withdraw(long amount) { ... }
```

:::
