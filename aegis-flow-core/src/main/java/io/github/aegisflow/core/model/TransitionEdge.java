package io.github.aegisflow.core.model;

import io.github.aegisflow.core.expr.ExprNode;

import java.lang.reflect.Method;
import java.util.Objects;

/**
 * Intermediate representation of a transition between two workflow states.
 */
public class TransitionEdge {

    private final String fromState;
    private final String toState;
    private final String trigger;
    private final String guardRaw;
    private final ExprNode guardAst;
    private final String description;
    private final Method methodRef;

    public TransitionEdge(String fromState, String toState, String trigger,
                          String guardRaw, ExprNode guardAst, String description,
                          Method methodRef) {
        this.fromState = Objects.requireNonNull(fromState, "fromState cannot be null").trim();
        this.toState = Objects.requireNonNull(toState, "toState cannot be null").trim();
        this.trigger = trigger != null ? trigger.trim() : "";
        this.guardRaw = guardRaw != null ? guardRaw.trim() : "";
        this.guardAst = guardAst;
        this.description = description != null ? description : "";
        this.methodRef = methodRef;
    }

    public String getFromState() {
        return fromState;
    }

    public String getToState() {
        return toState;
    }

    public String getTrigger() {
        return trigger;
    }

    public String getGuardRaw() {
        return guardRaw;
    }

    public ExprNode getGuardAst() {
        return guardAst;
    }

    public boolean hasGuard() {
        return guardAst != null;
    }

    public String getDescription() {
        return description;
    }

    public Method getMethodRef() {
        return methodRef;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        TransitionEdge that = (TransitionEdge) o;
        return Objects.equals(fromState, that.fromState) &&
                Objects.equals(toState, that.toState) &&
                Objects.equals(trigger, that.trigger) &&
                Objects.equals(guardRaw, that.guardRaw);
    }

    @Override
    public int hashCode() {
        return Objects.hash(fromState, toState, trigger, guardRaw);
    }

    @Override
    public String toString() {
        String trig = trigger.isEmpty() ? "" : " on " + trigger;
        String gd = guardRaw.isEmpty() ? "" : " [" + guardRaw + "]";
        return fromState + " -> " + toState + trig + gd;
    }
}
