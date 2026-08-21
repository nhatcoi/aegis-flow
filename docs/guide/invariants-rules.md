# Invariants & Business Rules

---

## 1. Class Invariants (`@Invariant`)

A **Class Invariant** is a boolean expression that must strictly hold:
1. Following object instantiation.
2. Before and after every valid state transition.

```java
@BusinessWorkflow(name = "BankAccountWorkflow")
@Invariant(value = "balance >= 0", description = "Account balance cannot be negative")
@Invariant(value = "overdraftLimit >= 0", description = "Overdraft limit cannot be negative")
public class BankAccountWorkflow {
    private long balance = 0;
    private long overdraftLimit = 1000;
    ...
}
```

::: warning INVARIANT BREACH DETECTION
If any state transition leads to `balance < 0`, verification engines will flag the workflow as `FAILED` and output a precise counter-example trace.
:::

---

## 2. Business Rules (`@Rule`) & Implication (`==>`)

`@Rule` models logical implications between states and properties:

$$\text{Condition A} \implies \text{Condition B}$$

Syntax: `expression = "A ==> B"` (equivalent to $\neg A \lor B$)

### Examples:

```java
@Rule(
    id = "RULE-SHIP-01",
    description = "If order is shipping, it must be paid",
    expression = "isShipping ==> isPaid"
)
@Rule(
    id = "RULE-REFUND-01",
    description = "Refund amount cannot exceed captured amount",
    expression = "refundAmount <= capturedAmount"
)
public class OrderWorkflow { ... }
```
