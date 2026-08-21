package io.github.aegisflow.core.annotation;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Declares a state in a business workflow.
 */
@Documented
@Target({ElementType.FIELD, ElementType.TYPE, ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
public @interface State {

    /**
     * Name of the state. If empty, the field or enum name is used.
     */
    String name() default "";

    /**
     * Optional description of the state.
     */
    String description() default "";
}
