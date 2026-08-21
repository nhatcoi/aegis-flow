package io.github.aegisflow.core.model;

import io.github.aegisflow.core.expr.ExprNode;

import java.util.Objects;

/**
 * Intermediate representation of a business rule specification.
 */
public class RuleSpec {

    private final String id;
    private final String description;
    private final String rawExpression;
    private final ExprNode ast;

    public RuleSpec(String id, String description, String rawExpression, ExprNode ast) {
        this.id = id != null ? id.trim() : "";
        this.description = description != null ? description.trim() : "";
        this.rawExpression = Objects.requireNonNull(rawExpression, "rawExpression cannot be null").trim();
        this.ast = ast;
    }

    public String getId() {
        return id;
    }

    public String getDescription() {
        return description;
    }

    public String getRawExpression() {
        return rawExpression;
    }

    public ExprNode getAst() {
        return ast;
    }

    @Override
    public String toString() {
        String prefix = id.isEmpty() ? "@Rule" : "@Rule[" + id + "]";
        return prefix + "(\"" + rawExpression + "\")" +
                (description.isEmpty() ? "" : " // " + description);
    }
}
