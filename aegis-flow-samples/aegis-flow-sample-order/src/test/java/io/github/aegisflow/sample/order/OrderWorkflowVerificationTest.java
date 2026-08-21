package io.github.aegisflow.sample.order;

import io.github.aegisflow.core.model.WorkflowDefinition;
import io.github.aegisflow.core.pipeline.VerificationPipeline;
import io.github.aegisflow.core.report.VerificationReport;
import io.github.aegisflow.core.report.VerificationStatus;
import io.github.aegisflow.core.scanner.WorkflowScanner;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class OrderWorkflowVerificationTest {

    @Test
    void testScanOrderWorkflow() {
        WorkflowScanner scanner = new WorkflowScanner();
        WorkflowDefinition workflow = scanner.scan(OrderWorkflow.class);

        assertThat(workflow.getName()).isEqualTo("EcommerceOrderWorkflow");
        assertThat(workflow.getStates()).hasSize(5);
        assertThat(workflow.getInitialState()).isPresent();
        assertThat(workflow.getInitialState().get().getName()).isEqualTo("CREATED");
        assertThat(workflow.getTerminalStates())
                .extracting(s -> s.getName())
                .containsExactlyInAnyOrder("DELIVERED", "CANCELLED");

        assertThat(workflow.getInvariants()).hasSize(2);
        assertThat(workflow.getRules()).hasSize(1);
        assertThat(workflow.getContracts()).hasSize(1);
    }

    @Test
    void testPipelineExecutionOnOrderWorkflow() {
        VerificationPipeline pipeline = VerificationPipeline.createDefault();
        VerificationReport report = pipeline.verifyClass(OrderWorkflow.class);

        System.out.println(report.toPrettyString());
        assertThat(report.getStatus()).isEqualTo(VerificationStatus.PASSED);
        assertThat(report.hasErrors()).isFalse();
    }
}
