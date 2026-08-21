package io.github.aegisflow.core.spi;

import io.github.aegisflow.core.model.WorkflowDefinition;

/**
 * Service Provider Interface (SPI) for verification engines (e.g. SMT, BMC, Fuzz, Static).
 */
public interface VerificationEngine {

    /**
     * Unique identifier name for this engine (e.g. "SMT", "BMC", "FUZZ").
     */
    String getName();

    /**
     * Human-readable description of the engine capabilities.
     */
    String getDescription();

    /**
     * Execution order of this engine in the pipeline (lower values run first).
     */
    default int getOrder() {
        return 100;
    }

    /**
     * Returns true if this engine is enabled and supports the given verification context.
     */
    default boolean supports(VerificationContext context) {
        return true;
    }

    /**
     * Performs verification on the provided workflow definition.
     *
     * @param workflow Intermediate Representation (IR) of the business workflow
     * @param context  execution context and options
     * @return result of the verification
     */
    EngineResult verify(WorkflowDefinition workflow, VerificationContext context);
}
