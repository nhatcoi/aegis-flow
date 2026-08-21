package io.github.aegisflow.core.annotation;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Marks a class as a verifiable Business Workflow.
 */
@Documented
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
public @interface BusinessWorkflow {

    /**
     * Unique identifier or human-readable name of the workflow.
     */
    String name() default "";

    /**
     * Version of the workflow definition.
     */
    String version() default "1.0.0";

    /**
     * Optional description of the workflow purpose.
     */
    String description() default "";
}
