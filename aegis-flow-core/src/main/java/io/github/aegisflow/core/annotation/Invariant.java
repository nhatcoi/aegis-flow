package io.github.aegisflow.core.annotation;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Repeatable;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Defines a state or entity invariant that must hold true across all valid states and transitions.
 * Example: @Invariant("balance >= 0")
 */
@Documented
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
@Repeatable(Invariants.class)
public @interface Invariant {

    /**
     * Boolean expression of the invariant.
     */
    String value();

    /**
     * Optional human-readable description or rationale.
     */
    String description() default "";
}
