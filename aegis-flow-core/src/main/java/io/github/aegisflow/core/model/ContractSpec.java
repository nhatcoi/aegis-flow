package io.github.aegisflow.core.model;

import io.github.aegisflow.core.expr.ExprNode;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * Intermediate representation of Design-by-Contract specifications on a method (@Requires and @Ensures).
 */
public class ContractSpec {

    public static class Condition {
        private final String rawExpression;
        private final ExprNode ast;
        private final String description;

        public Condition(String rawExpression, ExprNode ast, String description) {
            this.rawExpression = Objects.requireNonNull(rawExpression, "rawExpression cannot be null");
            this.ast = ast;
            this.description = description != null ? description : "";
        }

        public String getRawExpression() {
            return rawExpression;
        }

        public ExprNode getAst() {
            return ast;
        }

        public String getDescription() {
            return description;
        }

        @Override
        public String toString() {
            return rawExpression;
        }
    }

    private final Method method;
    private final List<Condition> preconditions;
    private final List<Condition> postconditions;

    public ContractSpec(Method method, List<Condition> preconditions, List<Condition> postconditions) {
        this.method = Objects.requireNonNull(method, "method cannot be null");
        this.preconditions = preconditions != null ? new ArrayList<>(preconditions) : Collections.emptyList();
        this.postconditions = postconditions != null ? new ArrayList<>(postconditions) : Collections.emptyList();
    }

    public Method getMethod() {
        return method;
    }

    public String getMethodName() {
        return method.getName();
    }

    public List<Condition> getPreconditions() {
        return Collections.unmodifiableList(preconditions);
    }

    public List<Condition> getPostconditions() {
        return Collections.unmodifiableList(postconditions);
    }

    public boolean hasContracts() {
        return !preconditions.isEmpty() || !postconditions.isEmpty();
    }

    @Override
    public String toString() {
        return "Contract for " + method.getName() + " [Requires: " + preconditions.size() +
                ", Ensures: " + postconditions.size() + "]";
    }
}
