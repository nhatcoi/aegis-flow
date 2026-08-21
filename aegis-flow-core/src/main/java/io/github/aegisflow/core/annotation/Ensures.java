package io.github.aegisflow.core.annotation;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Repeatable;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Postcondition (Design by Contract) that must evaluate to true after method execution.
 * Special identifier 'result' can be used to refer to method return value.
 * Special function 'old(variable)' can be used to refer to pre-execution values.
 */
@Documented
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Repeatable(EnsuresList.class)
public @interface Ensures {

    /**
     * Boolean postcondition expression.
     * Example: "result >= 0 && balance == old(balance) - amount"
     */
    String value();

    /**
     * Optional description of the guarantee.
     */
    String description() default "";
}
