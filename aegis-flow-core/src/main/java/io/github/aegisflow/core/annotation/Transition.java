package io.github.aegisflow.core.annotation;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Repeatable;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Defines a transition between two workflow states.
 */
@Documented
@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
@Repeatable(Transitions.class)
public @interface Transition {

    /**
     * Source state from which the transition begins.
     */
    String from();

    /**
     * Target state to which the workflow moves.
     */
    String to();

    /**
     * Optional trigger action or event name.
     */
    String trigger() default "";

    /**
     * Optional boolean guard expression that must be satisfied for the transition.
     * Example: "amount > 0 && amount <= balance"
     */
    String guard() default "";

    /**
     * Optional description of the transition.
     */
    String description() default "";
}
