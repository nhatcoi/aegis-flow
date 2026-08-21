package io.github.aegisflow.core.pipeline;

import io.github.aegisflow.core.model.WorkflowDefinition;
import io.github.aegisflow.core.report.CounterExample;
import io.github.aegisflow.core.report.Diagnostic;
import io.github.aegisflow.core.report.VerificationReport;
import io.github.aegisflow.core.report.VerificationStatus;
import io.github.aegisflow.core.scanner.WorkflowScanner;
import io.github.aegisflow.core.spi.EngineResult;
import io.github.aegisflow.core.spi.VerificationContext;
import io.github.aegisflow.core.spi.VerificationEngine;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;

/**
 * Orchestrates the workflow scanning, expression parsing, and execution of registered verification engines.
 */
public class VerificationPipeline {

    private static final Logger log = LoggerFactory.getLogger(VerificationPipeline.class);

    private final WorkflowScanner scanner;
    private final List<VerificationEngine> engines = new ArrayList<>();

    public VerificationPipeline() {
        this(new WorkflowScanner());
    }

    public VerificationPipeline(WorkflowScanner scanner) {
        this.scanner = Objects.requireNonNull(scanner, "scanner cannot be null");
    }

    /**
     * Factory method creating a pipeline with all engines discovered via Java ServiceLoader SPI.
     */
    public static VerificationPipeline createDefault() {
        VerificationPipeline pipeline = new VerificationPipeline();
        pipeline.discoverEngines();
        return pipeline;
    }

    /**
     * Discovers verification engines using Java ServiceLoader.
     */
    public void discoverEngines() {
        ServiceLoader<VerificationEngine> loader = ServiceLoader.load(VerificationEngine.class);
        for (VerificationEngine engine : loader) {
            registerEngine(engine);
        }
        log.info("Discovered and registered {} verification engines via SPI", engines.size());
    }

    /**
     * Explicitly registers a verification engine.
     */
    public VerificationPipeline registerEngine(VerificationEngine engine) {
        Objects.requireNonNull(engine, "engine cannot be null");
        engines.removeIf(e -> e.getName().equalsIgnoreCase(engine.getName()));
        engines.add(engine);
        engines.sort(Comparator.comparingInt(VerificationEngine::getOrder));
        log.debug("Registered verification engine: {} (order: {})", engine.getName(), engine.getOrder());
        return this;
    }

    public List<VerificationEngine> getRegisteredEngines() {
        return Collections.unmodifiableList(engines);
    }

    /**
     * Scans and verifies a target class.
     */
    public VerificationReport verifyClass(Class<?> targetClass) {
        return verifyClass(targetClass, new VerificationContext());
    }

    /**
     * Scans and verifies a target class with custom context.
     */
    public VerificationReport verifyClass(Class<?> targetClass, VerificationContext context) {
        WorkflowDefinition workflow = scanner.scan(targetClass);
        return verify(workflow, context);
    }

    /**
     * Verifies a pre-constructed WorkflowDefinition IR.
     */
    public VerificationReport verify(WorkflowDefinition workflow) {
        return verify(workflow, new VerificationContext());
    }

    /**
     * Verifies a WorkflowDefinition IR with custom context.
     */
    public VerificationReport verify(WorkflowDefinition workflow, VerificationContext context) {
        Objects.requireNonNull(workflow, "workflow cannot be null");
        Objects.requireNonNull(context, "context cannot be null");

        log.info("Starting verification pipeline for workflow: {}", workflow.getName());
        long startTime = System.currentTimeMillis();

        Map<String, EngineResult> engineResults = new LinkedHashMap<>();
        List<Diagnostic> allDiagnostics = new ArrayList<>();
        List<CounterExample> allCounterExamples = new ArrayList<>();

        for (VerificationEngine engine : engines) {
            if (!engine.supports(context)) {
                log.debug("Skipping engine {} (not supported in current context)", engine.getName());
                continue;
            }

            log.debug("Executing verification engine: {}", engine.getName());
            long engineStart = System.currentTimeMillis();
            try {
                EngineResult result = engine.verify(workflow, context);
                engineResults.put(engine.getName(), result);
                allDiagnostics.addAll(result.getDiagnostics());
                allCounterExamples.addAll(result.getCounterExamples());
            } catch (Exception ex) {
                log.error("Engine {} failed with unexpected exception", engine.getName(), ex);
                Diagnostic errorDiag = new Diagnostic(
                        Diagnostic.Severity.ERROR,
                        engine.getName(),
                        "ENGINE_ERROR",
                        "Engine failed with exception: " + ex.getMessage(),
                        workflow.getName()
                );
                allDiagnostics.add(errorDiag);
                EngineResult failedResult = EngineResult.failed(
                        engine.getName(),
                        List.of(errorDiag),
                        Collections.emptyList(),
                        System.currentTimeMillis() - engineStart
                );
                engineResults.put(engine.getName(), failedResult);
            }
        }

        long totalDuration = System.currentTimeMillis() - startTime;

        VerificationStatus overallStatus = determineOverallStatus(engineResults, allDiagnostics);

        VerificationReport report = new VerificationReport(
                workflow.getName(),
                overallStatus,
                engineResults,
                allDiagnostics,
                allCounterExamples,
                totalDuration
        );

        log.info("Completed verification for {} with status: {} in {} ms",
                workflow.getName(), overallStatus, totalDuration);

        return report;
    }

    private VerificationStatus determineOverallStatus(Map<String, EngineResult> engineResults, List<Diagnostic> diagnostics) {
        boolean hasError = diagnostics.stream().anyMatch(d -> d.getSeverity() == Diagnostic.Severity.ERROR) ||
                engineResults.values().stream().anyMatch(r -> r.getStatus() == VerificationStatus.FAILED);
        if (hasError) {
            return VerificationStatus.FAILED;
        }

        boolean hasWarning = diagnostics.stream().anyMatch(d -> d.getSeverity() == Diagnostic.Severity.WARNING) ||
                engineResults.values().stream().anyMatch(r -> r.getStatus() == VerificationStatus.WARNING);
        if (hasWarning) {
            return VerificationStatus.WARNING;
        }

        return VerificationStatus.PASSED;
    }
}
