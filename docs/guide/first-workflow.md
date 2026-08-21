# Your First Workflow

Here is a practical e-commerce order workflow demonstrating the full annotation suite of AegisFlow.

---

## 1. Defining `OrderWorkflow`

```java
package io.github.aegisflow.sample.order;

import io.github.aegisflow.core.annotation.*;

@BusinessWorkflow(
    name = "OrderWorkflow",
    version = "1.0.0",
    description = "Manages online order lifecycle states"
)
@Invariant(value = "!(isDelivered && isCancelled)", description = "An order cannot be both delivered and cancelled")
@Invariant(value = "balance >= 0", description = "Account balance cannot become negative")
@Rule(id = "RULE-SHIP-01", description = "Order must be paid before shipping", expression = "isShipping ==> isPaid")
public class OrderWorkflow {

    public enum OrderStatus {
        @InitialState
        CREATED,

        PAID,

        SHIPPING,

        @TerminalState
        DELIVERED,

        @TerminalState
        CANCELLED
    }

    private OrderStatus status = OrderStatus.CREATED;
    private long balance = 1000;
    private long totalAmount = 250;

    public boolean isPaid() {
        return status == OrderStatus.PAID || status == OrderStatus.SHIPPING || status == OrderStatus.DELIVERED;
    }

    public boolean isShipping() {
        return status == OrderStatus.SHIPPING;
    }

    public boolean isDelivered() {
        return status == OrderStatus.DELIVERED;
    }

    public boolean isCancelled() {
        return status == OrderStatus.CANCELLED;
    }

    @Transition(from = "CREATED", to = "PAID", trigger = "pay", guard = "amount > 0 && amount <= balance")
    @Requires("amount > 0 && amount <= balance")
    @Ensures("balance == old(balance) - amount")
    public void pay(long amount) {
        if (amount <= 0 || amount > balance) {
            throw new IllegalArgumentException("Invalid payment amount");
        }
        this.balance -= amount;
        this.status = OrderStatus.PAID;
    }

    @Transition(from = "PAID", to = "SHIPPING", trigger = "ship")
    public void ship() {
        this.status = OrderStatus.SHIPPING;
    }

    @Transition(from = "SHIPPING", to = "DELIVERED", trigger = "deliver")
    public void deliver() {
        this.status = OrderStatus.DELIVERED;
    }

    @Transition(from = "CREATED", to = "CANCELLED", trigger = "cancel")
    @Transition(from = "PAID", to = "CANCELLED", trigger = "cancel")
    public void cancel() {
        this.status = OrderStatus.CANCELLED;
    }
}
```

---

## 2. Key Components Explained

1. **`@BusinessWorkflow`**: Marks the class as a verifiable workflow entity.
2. **`@InitialState` & `@TerminalState`**: Defines entry (`CREATED`) and terminal exit points (`DELIVERED`, `CANCELLED`).
3. **`@Transition`**: Declares valid state edges. Supports repeatable declarations on a single method.
4. **`@Invariant`**: Conditions guaranteed to hold across all states (`balance >= 0`).
5. **`@Requires` & `@Ensures`**: Preconditions and postconditions using temporal state tracking (`old(balance)`).
