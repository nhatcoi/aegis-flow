package io.github.aegisflow.core.annotation;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Repeatable;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Declares a business rule constraint on a workflow.
 */
@Documented
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
@Repeatable(Rules.class)
public @interface Rule {

    /**
     * Unique identifier for the rule (e.g., "BR-001").
     */
    String id() default "";

    /**
     * Boolean expression defining the rule.
     */
    String expression();

    /**
     * Human-readable description of the business rule.
     */
    String description() default "";
}
