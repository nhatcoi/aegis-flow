package io.github.aegisflow.core.spi;

import io.github.aegisflow.core.report.CounterExample;
import io.github.aegisflow.core.report.Diagnostic;
import io.github.aegisflow.core.report.VerificationStatus;

import java.util.*;

/**
 * Result returned by a single verification engine execution.
 */
public class EngineResult {

    private final String engineName;
    private final VerificationStatus status;
    private final List<Diagnostic> diagnostics;
    private final List<CounterExample> counterExamples;
    private final Map<String, Object> metrics;
    private final long executionDurationMs;

    public EngineResult(String engineName, VerificationStatus status,
                        List<Diagnostic> diagnostics, List<CounterExample> counterExamples,
                        Map<String, Object> metrics, long executionDurationMs) {
        this.engineName = Objects.requireNonNull(engineName, "engineName cannot be null");
        this.status = Objects.requireNonNull(status, "status cannot be null");
        this.diagnostics = diagnostics != null ? new ArrayList<>(diagnostics) : Collections.emptyList();
        this.counterExamples = counterExamples != null ? new ArrayList<>(counterExamples) : Collections.emptyList();
        this.metrics = metrics != null ? new LinkedHashMap<>(metrics) : Collections.emptyMap();
        this.executionDurationMs = executionDurationMs;
    }

    public static EngineResult passed(String engineName, long durationMs) {
        return new EngineResult(engineName, VerificationStatus.PASSED, Collections.emptyList(), Collections.emptyList(), Collections.emptyMap(), durationMs);
    }

    public static EngineResult failed(String engineName, List<Diagnostic> diagnostics, List<CounterExample> counterExamples, long durationMs) {
        return new EngineResult(engineName, VerificationStatus.FAILED, diagnostics, counterExamples, Collections.emptyMap(), durationMs);
    }

    public String getEngineName() {
        return engineName;
    }

    public VerificationStatus getStatus() {
        return status;
    }

    public List<Diagnostic> getDiagnostics() {
        return Collections.unmodifiableList(diagnostics);
    }

    public List<CounterExample> getCounterExamples() {
        return Collections.unmodifiableList(counterExamples);
    }

    public Map<String, Object> getMetrics() {
        return Collections.unmodifiableMap(metrics);
    }

    public long getExecutionDurationMs() {
        return executionDurationMs;
    }

    public boolean hasErrors() {
        return status == VerificationStatus.FAILED ||
                diagnostics.stream().anyMatch(d -> d.getSeverity() == Diagnostic.Severity.ERROR);
    }
}
