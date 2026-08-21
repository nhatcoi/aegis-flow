package io.github.aegisflow.core.expr;

import java.util.Map;

/**
 * Base interface for all Abstract Syntax Tree (AST) nodes of constraint expressions.
 */
public interface ExprNode {

    /**
     * Converts the AST node back to a standardized expression string.
     */
    String toExpressionString();

    /**
     * Evaluates the expression against a context of variable names and their runtime values.
     */
    Object evaluate(Map<String, Object> context);

    /**
     * Accepts a visitor for tree traversal and transformation (e.g. SMT translation).
     */
    <T> T accept(ExprVisitor<T> visitor);
}
