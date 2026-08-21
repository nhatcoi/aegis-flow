package io.github.aegisflow.core.model;

import io.github.aegisflow.core.expr.ExprNode;

import java.util.Objects;

/**
 * Intermediate representation of a workflow invariant specification.
 */
public class InvariantSpec {

    private final String rawExpression;
    private final ExprNode ast;
    private final String description;

    public InvariantSpec(String rawExpression, ExprNode ast, String description) {
        this.rawExpression = Objects.requireNonNull(rawExpression, "rawExpression cannot be null").trim();
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
        return "@Invariant(\"" + rawExpression + "\")" +
                (description.isEmpty() ? "" : " // " + description);
    }
}
