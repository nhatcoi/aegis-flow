package io.github.aegisflow.sample.boot.workflow;

import io.github.aegisflow.core.annotation.*;
import org.springframework.stereotype.Component;

/**
 * Business Workflow for processing an online order lifecycle.
 */
@Component
@BusinessWorkflow(
        name = "OrderProcessingWorkflow",
        version = "1.2.0",
        description = "Handles end-to-end e-commerce order states from placement to fulfillment or cancellation"
)
@Invariant(value = "!(isDelivered && isCancelled)", description = "An order cannot be both DELIVERED and CANCELLED")
@Rule(id = "RULE-SHIP-01", description = "Order must be PAID before shipping can take place", expression = "isShipping ==> isPaid")
public class OrderProcessingWorkflow {

    public enum OrderStatus {
        @InitialState
        CREATED,

        PAYMENT_PENDING,

        PAID,

        SHIPPING,

        @TerminalState
        DELIVERED,

        @TerminalState
        CANCELLED
    }

    private OrderStatus status = OrderStatus.CREATED;
    private long totalAmount = 250;
    private long paidAmount = 0;

    public OrderStatus getStatus() {
        return status;
    }

    public long getTotalAmount() {
        return totalAmount;
    }

    public long getPaidAmount() {
        return paidAmount;
    }

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

    @Transition(from = "CREATED", to = "PAYMENT_PENDING", trigger = "requestPayment")
    public void requestPayment() {
        if (this.status != OrderStatus.CREATED) {
            throw new IllegalStateException("Cannot request payment for order not in CREATED state");
        }
        this.status = OrderStatus.PAYMENT_PENDING;
    }

    @Transition(from = "PAYMENT_PENDING", to = "PAID", trigger = "completePayment", guard = "paidAmount >= totalAmount")
    @Requires("amount >= totalAmount")
    public void completePayment(long amount) {
        if (this.status != OrderStatus.PAYMENT_PENDING) {
            throw new IllegalStateException("Order is not awaiting payment");
        }
        this.paidAmount = amount;
        this.status = OrderStatus.PAID;
    }

    @Transition(from = "PAID", to = "SHIPPING", trigger = "dispatchShipment")
    public void dispatchShipment() {
        if (this.status != OrderStatus.PAID) {
            throw new IllegalStateException("Cannot dispatch shipment for unpaid order");
        }
        this.status = OrderStatus.SHIPPING;
    }

    @Transition(from = "SHIPPING", to = "DELIVERED", trigger = "confirmDelivery")
    public void confirmDelivery() {
        if (this.status != OrderStatus.SHIPPING) {
            throw new IllegalStateException("Cannot deliver order that is not currently in shipping");
        }
        this.status = OrderStatus.DELIVERED;
    }

    @Transition(from = "CREATED", to = "CANCELLED", trigger = "cancelOrder")
    @Transition(from = "PAYMENT_PENDING", to = "CANCELLED", trigger = "cancelOrder")
    public void cancelOrder() {
        if (this.status == OrderStatus.DELIVERED || this.status == OrderStatus.CANCELLED) {
            throw new IllegalStateException("Cannot cancel an already completed or cancelled order");
        }
        this.status = OrderStatus.CANCELLED;
    }
}
