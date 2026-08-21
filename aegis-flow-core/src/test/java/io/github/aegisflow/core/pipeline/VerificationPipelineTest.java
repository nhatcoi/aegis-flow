package io.github.aegisflow.core.pipeline;

import io.github.aegisflow.core.annotation.BusinessWorkflow;
import io.github.aegisflow.core.annotation.InitialState;
import io.github.aegisflow.core.annotation.TerminalState;
import io.github.aegisflow.core.annotation.Transition;
import io.github.aegisflow.core.model.WorkflowDefinition;
import io.github.aegisflow.core.report.CounterExample;
import io.github.aegisflow.core.report.Diagnostic;
import io.github.aegisflow.core.report.VerificationReport;
import io.github.aegisflow.core.report.VerificationStatus;
import io.github.aegisflow.core.spi.EngineResult;
import io.github.aegisflow.core.spi.VerificationContext;
import io.github.aegisflow.core.spi.VerificationEngine;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class VerificationPipelineTest {

    private VerificationPipeline pipeline;

    @BeforeEach
    void setUp() {
        pipeline = new VerificationPipeline();
    }

    @BusinessWorkflow(name = "SimpleWorkflow")
    static class SimpleWorkflow {
        enum State {
            @InitialState START,
            @TerminalState END
        }

        @Transition(from = "START", to = "END", trigger = "finish")
        public void finish() {}
    }

    @Test
    void testPipelineWithPassingEngine() {
        VerificationEngine passingEngine = new VerificationEngine() {
            @Override
            public String getName() {
                return "MockBMC";
            }

            @Override
            public String getDescription() {
                return "Mock Model Checking Engine";
            }

            @Override
            public EngineResult verify(WorkflowDefinition workflow, VerificationContext context) {
                return EngineResult.passed(getName(), 15L);
            }
        };

        pipeline.registerEngine(passingEngine);
        VerificationReport report = pipeline.verifyClass(SimpleWorkflow.class);

        assertThat(report.getStatus()).isEqualTo(VerificationStatus.PASSED);
        assertThat(report.hasErrors()).isFalse();
        assertThat(report.getEngineResults()).containsKey("MockBMC");
        assertThat(report.toPrettyString()).contains("MockBMC").contains("PASSED");
    }

    @Test
    void testPipelineWithFailingEngineAndCounterExample() {
        VerificationEngine failingEngine = new VerificationEngine() {
            @Override
            public String getName() {
                return "MockSMT";
            }

            @Override
            public String getDescription() {
                return "Mock SMT Verification Engine";
            }

            @Override
            public EngineResult verify(WorkflowDefinition workflow, VerificationContext context) {
                Diagnostic diag = new Diagnostic(
                        Diagnostic.Severity.ERROR,
                        getName(),
                        "INV-01",
                        "Invariant 'balance >= 0' violated",
                        "SimpleWorkflow"
                );
                CounterExample ce = new CounterExample(
                        "Negative balance reachable",
                        Map.of("balance", -10L, "amount", 100L),
                        List.of("START", "END")
                );
                return EngineResult.failed(getName(), List.of(diag), List.of(ce), 25L);
            }
        };

        pipeline.registerEngine(failingEngine);
        VerificationReport report = pipeline.verifyClass(SimpleWorkflow.class);

        assertThat(report.getStatus()).isEqualTo(VerificationStatus.FAILED);
        assertThat(report.hasErrors()).isTrue();
        assertThat(report.getDiagnostics()).hasSize(1);
        assertThat(report.getCounterExamples()).hasSize(1);
        assertThat(report.toPrettyString())
                .contains("FAILED")
                .contains("Negative balance reachable")
                .contains("INV-01");
    }
}
