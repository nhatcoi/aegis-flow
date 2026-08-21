package io.github.aegisflow.core.annotation;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Repeatable;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Precondition (Design by Contract) that must evaluate to true prior to method execution.
 */
@Documented
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Repeatable(RequiresList.class)
public @interface Requires {

    /**
     * Boolean precondition expression.
     * Example: "amount > 0 && balance >= amount"
     */
    String value();

    /**
     * Optional description of the requirement.
     */
    String description() default "";
}
