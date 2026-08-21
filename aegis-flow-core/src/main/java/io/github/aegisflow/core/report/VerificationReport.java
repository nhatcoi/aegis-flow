package io.github.aegisflow.core.report;

import io.github.aegisflow.core.spi.EngineResult;

import java.util.*;

/**
 * Aggregated verification report combining findings across all executed verification engines.
 */
public class VerificationReport {

    private final String workflowName;
    private final VerificationStatus status;
    private final Map<String, EngineResult> engineResults;
    private final List<Diagnostic> diagnostics;
    private final List<CounterExample> counterExamples;
    private final long totalDurationMs;

    public VerificationReport(String workflowName, VerificationStatus status,
                              Map<String, EngineResult> engineResults,
                              List<Diagnostic> diagnostics,
                              List<CounterExample> counterExamples,
                              long totalDurationMs) {
        this.workflowName = Objects.requireNonNull(workflowName, "workflowName cannot be null");
        this.status = Objects.requireNonNull(status, "status cannot be null");
        this.engineResults = engineResults != null ? new LinkedHashMap<>(engineResults) : Collections.emptyMap();
        this.diagnostics = diagnostics != null ? new ArrayList<>(diagnostics) : Collections.emptyList();
        this.counterExamples = counterExamples != null ? new ArrayList<>(counterExamples) : Collections.emptyList();
        this.totalDurationMs = totalDurationMs;
    }

    public String getWorkflowName() {
        return workflowName;
    }

    public VerificationStatus getStatus() {
        return status;
    }

    public Map<String, EngineResult> getEngineResults() {
        return Collections.unmodifiableMap(engineResults);
    }

    public List<Diagnostic> getDiagnostics() {
        return Collections.unmodifiableList(diagnostics);
    }

    public List<CounterExample> getCounterExamples() {
        return Collections.unmodifiableList(counterExamples);
    }

    public long getTotalDurationMs() {
        return totalDurationMs;
    }

    public boolean hasErrors() {
        return status == VerificationStatus.FAILED ||
                diagnostics.stream().anyMatch(d -> d.getSeverity() == Diagnostic.Severity.ERROR);
    }

    public boolean hasWarnings() {
        return status == VerificationStatus.WARNING ||
                diagnostics.stream().anyMatch(d -> d.getSeverity() == Diagnostic.Severity.WARNING);
    }

    /**
     * Formats the report into a clean, human-readable terminal dashboard.
     */
    public String toPrettyString() {
        StringBuilder sb = new StringBuilder();
        sb.append("\n╔══════════════════════════════════════════════════════════════════════════╗\n");
        sb.append(String.format("║  AEGISFLOW VERIFICATION REPORT: %-45s ║\n", workflowName));
        sb.append("╠══════════════════════════════════════════════════════════════════════════╣\n");
        sb.append(String.format("║  Overall Status: %-15s   Total Time: %-6d ms               ║\n", status, totalDurationMs));
        sb.append("╠══════════════════════════════════════════════════════════════════════════╣\n");
        sb.append("║  ENGINES SUMMARY:                                                        ║\n");

        if (engineResults.isEmpty()) {
            sb.append("║    (No engines were executed)                                            ║\n");
        } else {
            for (Map.Entry<String, EngineResult> entry : engineResults.entrySet()) {
                EngineResult res = entry.getValue();
                String icon = res.getStatus() == VerificationStatus.PASSED ? "✓" : "✗";
                sb.append(String.format("║    %s %-15s : %-10s (%d ms, %d diagnostics, %d counter-examples) ║\n",
                        icon, res.getEngineName(), res.getStatus(), res.getExecutionDurationMs(),
                        res.getDiagnostics().size(), res.getCounterExamples().size()));
            }
        }

        if (!diagnostics.isEmpty()) {
            sb.append("╠══════════════════════════════════════════════════════════════════════════╣\n");
            sb.append("║  DIAGNOSTICS:                                                            ║\n");
            for (Diagnostic d : diagnostics) {
                String ruleStr = d.getRuleId().isEmpty() ? "" : "[" + d.getRuleId() + "] ";
                sb.append(String.format("║  • [%-7s] [%-8s] %s%-45s ║\n", d.getSeverity(), d.getEngineName(), ruleStr, d.getMessage()));
            }
        }

        if (!counterExamples.isEmpty()) {
            sb.append("╠══════════════════════════════════════════════════════════════════════════╣\n");
            sb.append("║  COUNTER-EXAMPLES:                                                       ║\n");
            for (CounterExample ce : counterExamples) {
                sb.append("║  ❌ ").append(ce.getDescription()).append("\n");
                if (!ce.getVariables().isEmpty()) {
                    sb.append("║     Variables: ").append(ce.getVariables()).append("\n");
                }
                if (!ce.getExecutionTrace().isEmpty()) {
                    sb.append("║     Trace: ").append(String.join(" -> ", ce.getExecutionTrace())).append("\n");
                }
            }
        }

        sb.append("╚══════════════════════════════════════════════════════════════════════════╝\n");
        return sb.toString();
    }

    @Override
    public String toString() {
        return toPrettyString();
    }
}
