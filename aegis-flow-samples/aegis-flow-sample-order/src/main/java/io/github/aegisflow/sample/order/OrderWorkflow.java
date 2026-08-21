package io.github.aegisflow.sample.order;

import io.github.aegisflow.core.annotation.*;

/**
 * E-Commerce Order Workflow demonstrating AegisFlow business process modeling,
 * state transitions, invariants, and method contracts.
 */
@BusinessWorkflow(
        name = "EcommerceOrderWorkflow",
        version = "1.0.0",
        description = "Manages the lifecycle of an online store order from creation to delivery or cancellation"
)
@Invariant(value = "!(isDelivered && isCancelled)", description = "An order cannot be both DELIVERED and CANCELLED")
@Invariant(value = "balance >= 0", description = "Customer account balance cannot become negative")
@Rule(id = "RULE-SHIP-01", description = "Order must be PAID before it can be SHIPPED", expression = "isShipping ==> isPaid")
public class OrderWorkflow {

    public enum OrderState {
        @InitialState
        CREATED,

        PAID,

        SHIPPING,

        @TerminalState
        DELIVERED,

        @TerminalState
        CANCELLED
    }

    private OrderState currentState = OrderState.CREATED;
    private int balance = 1000;
    private int orderAmount = 150;

    public OrderState getCurrentState() {
        return currentState;
    }

    public int getBalance() {
        return balance;
    }

    public int getOrderAmount() {
        return orderAmount;
    }

    public boolean isPaid() {
        return currentState == OrderState.PAID || currentState == OrderState.SHIPPING || currentState == OrderState.DELIVERED;
    }

    public boolean isShipping() {
        return currentState == OrderState.SHIPPING;
    }

    public boolean isDelivered() {
        return currentState == OrderState.DELIVERED;
    }

    public boolean isCancelled() {
        return currentState == OrderState.CANCELLED;
    }

    @Transition(from = "CREATED", to = "PAID", trigger = "pay", guard = "amount > 0 && amount <= balance")
    @Requires("amount > 0")
    @Requires("balance >= amount")
    @Ensures("balance == old(balance) - amount")
    public void pay(int amount) {
        if (amount <= 0 || amount > balance) {
            throw new IllegalArgumentException("Invalid payment amount");
        }
        this.balance -= amount;
        this.currentState = OrderState.PAID;
    }

    @Transition(from = "PAID", to = "SHIPPING", trigger = "ship")
    public void ship() {
        if (this.currentState != OrderState.PAID) {
            throw new IllegalStateException("Cannot ship an unpaid order");
        }
        this.currentState = OrderState.SHIPPING;
    }

    @Transition(from = "SHIPPING", to = "DELIVERED", trigger = "deliver")
    public void deliver() {
        if (this.currentState != OrderState.SHIPPING) {
            throw new IllegalStateException("Cannot deliver an order not currently in shipping");
        }
        this.currentState = OrderState.DELIVERED;
    }

    @Transition(from = "CREATED", to = "CANCELLED", trigger = "cancel")
    @Transition(from = "PAID", to = "CANCELLED", trigger = "cancel")
    public void cancel() {
        if (this.currentState == OrderState.DELIVERED) {
            throw new IllegalStateException("Cannot cancel a delivered order");
        }
        this.currentState = OrderState.CANCELLED;
    }
}
