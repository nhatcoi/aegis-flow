package io.github.aegisflow.core.annotation;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Opt-in annotation to enable AegisFlow verification for a class or specific method.
 */
@Documented
@Target({ElementType.TYPE, ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
public @interface Verified {

    /**
     * Optional profile or engine filter to run (e.g. "smt", "bmc", "fuzz").
     * Empty means all available engines will run.
     */
    String[] engines() default {};
}
