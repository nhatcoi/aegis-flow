# Design by Contract

The **Design by Contract (DbC)** paradigm ensures method integrity by establishing explicit contracts between callers and callees.

---

## 1. Preconditions (`@Requires`)

A precondition defines requirements the caller must satisfy before executing the method:

```java
@Requires("amount > 0")
@Requires("accountBalance >= amount")
public void transfer(long amount, Account target) {
    this.accountBalance -= amount;
    target.deposit(amount);
}
```

If preconditions are not met, the method does not proceed, and verification will alert if any execution path leads to invalid invocations.

---

## 2. Postconditions (`@Ensures`)

A postcondition guarantees the final state after the method execution completes:

```java
@Requires("amount > 0 && accountBalance >= amount")
@Ensures("accountBalance == old(accountBalance) - amount")
public void withdraw(long amount) {
    this.accountBalance -= amount;
}
```

### The `old(...)` Function
The `old(variable)` expression allows referencing a variable's value **immediately before method execution started**.

| Expression | Meaning |
| :--- | :--- |
| `balance == old(balance) - amount` | New balance must equal previous balance minus amount |
| `itemCount == old(itemCount) + 1` | Item count must increment exactly by 1 |
| `totalPrice == old(totalPrice)` | Total price must remain immutable during operation |
