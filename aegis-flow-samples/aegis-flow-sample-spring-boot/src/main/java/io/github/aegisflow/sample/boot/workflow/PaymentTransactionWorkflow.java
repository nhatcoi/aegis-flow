package io.github.aegisflow.sample.boot.workflow;

import io.github.aegisflow.core.annotation.*;
import org.springframework.stereotype.Component;

/**
 * Business Workflow for secure payment transactions and settlements.
 */
@Component
@BusinessWorkflow(
        name = "PaymentTransactionWorkflow",
        version = "1.0.0",
        description = "Handles banking authorization, capture, settlement and refund flows"
)
@Invariant(value = "accountBalance >= 0", description = "Account balance cannot be negative")
@Rule(id = "RULE-REFUND-01", description = "Refund amount must not exceed captured amount", expression = "refundAmount <= capturedAmount")
public class PaymentTransactionWorkflow {

    public enum PaymentState {
        @InitialState
        INITIATED,

        AUTHORIZED,

        CAPTURED,

        @TerminalState
        SETTLED,

        @TerminalState
        REFUNDED,

        @TerminalState
        FAILED
    }

    private PaymentState state = PaymentState.INITIATED;
    private long accountBalance = 1000;
    private long capturedAmount = 0;
    private long refundAmount = 0;

    public PaymentState getState() {
        return state;
    }

    public long getAccountBalance() {
        return accountBalance;
    }

    public long getCapturedAmount() {
        return capturedAmount;
    }

    public long getRefundAmount() {
        return refundAmount;
    }

    @Transition(from = "INITIATED", to = "AUTHORIZED", trigger = "authorize")
    @Requires("amount > 0 && amount <= accountBalance")
    public void authorize(long amount) {
        if (amount <= 0 || amount > accountBalance) {
            this.state = PaymentState.FAILED;
            throw new IllegalArgumentException("Insufficient funds for authorization");
        }
        this.state = PaymentState.AUTHORIZED;
    }

    @Transition(from = "AUTHORIZED", to = "CAPTURED", trigger = "capture")
    @Requires("amount > 0")
    @Ensures("accountBalance == old(accountBalance) - amount")
    public void capture(long amount) {
        if (this.state != PaymentState.AUTHORIZED) {
            throw new IllegalStateException("Transaction not authorized");
        }
        this.accountBalance -= amount;
        this.capturedAmount = amount;
        this.state = PaymentState.CAPTURED;
    }

    @Transition(from = "CAPTURED", to = "SETTLED", trigger = "settle")
    public void settle() {
        if (this.state != PaymentState.CAPTURED) {
            throw new IllegalStateException("Only captured payments can be settled");
        }
        this.state = PaymentState.SETTLED;
    }

    @Transition(from = "CAPTURED", to = "REFUNDED", trigger = "refund", guard = "refundAmount <= capturedAmount")
    @Requires("refundAmount <= capturedAmount")
    @Ensures("accountBalance == old(accountBalance) + refundAmount")
    public void refund(long refundAmount) {
        if (this.state != PaymentState.CAPTURED) {
            throw new IllegalStateException("Only captured payments can be refunded");
        }
        if (refundAmount > this.capturedAmount) {
            throw new IllegalArgumentException("Refund amount exceeds captured amount");
        }
        this.refundAmount = refundAmount;
        this.accountBalance += refundAmount;
        this.state = PaymentState.REFUNDED;
    }
}
