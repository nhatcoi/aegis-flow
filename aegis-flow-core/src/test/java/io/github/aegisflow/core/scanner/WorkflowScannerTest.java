package io.github.aegisflow.core.scanner;

import io.github.aegisflow.core.annotation.*;
import io.github.aegisflow.core.model.StateNode;
import io.github.aegisflow.core.model.TransitionEdge;
import io.github.aegisflow.core.model.WorkflowDefinition;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class WorkflowScannerTest {

    private WorkflowScanner scanner;

    @BeforeEach
    void setUp() {
        scanner = new WorkflowScanner();
    }

    @BusinessWorkflow(name = "OrderPaymentWorkflow", version = "2.0.0", description = "Test workflow for e-commerce order")
    @Invariant(value = "balance >= 0", description = "Balance cannot be negative")
    @Invariant(value = "!(isDelivered && isCancelled)", description = "Delivered order cannot be cancelled")
    @Rule(id = "BR-001", description = "Shipping requires payment", expression = "isShipping ==> isPaid")
    static class SampleOrderWorkflow {

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

        @Transition(from = "CREATED", to = "PAID", trigger = "pay", guard = "amount > 0 && amount <= balance")
        @Requires("amount > 0")
        @Requires("balance >= amount")
        @Ensures("balance == old(balance) - amount")
        public void pay(int amount, int balance) {
            // business logic
        }

        @Transition(from = "PAID", to = "SHIPPING", trigger = "ship")
        public void ship() {
            // business logic
        }

        @Transition(from = "SHIPPING", to = "DELIVERED", trigger = "deliver")
        public void deliver() {
            // business logic
        }

        @Transition(from = "CREATED", to = "CANCELLED", trigger = "cancel")
        @Transition(from = "PAID", to = "CANCELLED", trigger = "cancel")
        public void cancel() {
            // business logic
        }
    }

    @Test
    void testScanWorkflowMetadata() {
        WorkflowDefinition workflow = scanner.scan(SampleOrderWorkflow.class);

        assertThat(workflow.getName()).isEqualTo("OrderPaymentWorkflow");
        assertThat(workflow.getVersion()).isEqualTo("2.0.0");
        assertThat(workflow.getDescription()).isEqualTo("Test workflow for e-commerce order");
        assertThat(workflow.getTargetClass()).isEqualTo(SampleOrderWorkflow.class);
    }

    @Test
    void testScanStates() {
        WorkflowDefinition workflow = scanner.scan(SampleOrderWorkflow.class);

        assertThat(workflow.getStates()).hasSize(5);
        assertThat(workflow.getState("CREATED")).isPresent();
        assertThat(workflow.getState("DELIVERED")).isPresent();

        StateNode initial = workflow.getInitialState().orElseThrow();
        assertThat(initial.getName()).isEqualTo("CREATED");
        assertThat(initial.isInitial()).isTrue();

        assertThat(workflow.getTerminalStates())
                .extracting(StateNode::getName)
                .containsExactlyInAnyOrder("DELIVERED", "CANCELLED");
    }

    @Test
    void testScanTransitions() {
        WorkflowDefinition workflow = scanner.scan(SampleOrderWorkflow.class);

        assertThat(workflow.getTransitions()).hasSize(5);

        TransitionEdge payEdge = workflow.getTransitions().stream()
                .filter(t -> t.getTrigger().equals("pay"))
                .findFirst().orElseThrow();
        assertThat(payEdge.getFromState()).isEqualTo("CREATED");
        assertThat(payEdge.getToState()).isEqualTo("PAID");
        assertThat(payEdge.getGuardRaw()).isEqualTo("amount > 0 && amount <= balance");
        assertThat(payEdge.getGuardAst()).isNotNull();

        assertThat(workflow.getTransitionsFrom("PAID"))
                .extracting(TransitionEdge::getToState)
                .containsExactlyInAnyOrder("SHIPPING", "CANCELLED");
    }

    @Test
    void testScanInvariantsAndRules() {
        WorkflowDefinition workflow = scanner.scan(SampleOrderWorkflow.class);

        assertThat(workflow.getInvariants()).hasSize(2);
        assertThat(workflow.getInvariants().get(0).getRawExpression()).isEqualTo("balance >= 0");
        assertThat(workflow.getInvariants().get(0).getAst()).isNotNull();

        assertThat(workflow.getRules()).hasSize(1);
        assertThat(workflow.getRules().get(0).getId()).isEqualTo("BR-001");
        assertThat(workflow.getRules().get(0).getRawExpression()).isEqualTo("isShipping ==> isPaid");
        assertThat(workflow.getRules().get(0).getAst()).isNotNull();
    }

    @Test
    void testScanContracts() {
        WorkflowDefinition workflow = scanner.scan(SampleOrderWorkflow.class);

        assertThat(workflow.getContracts()).hasSize(1);
        var contract = workflow.getContracts().get(0);
        assertThat(contract.getMethodName()).isEqualTo("pay");
        assertThat(contract.getPreconditions()).hasSize(2);
        assertThat(contract.getPostconditions()).hasSize(1);
        assertThat(contract.getPostconditions().get(0).getRawExpression())
                .isEqualTo("balance == old(balance) - amount");
    }
}
