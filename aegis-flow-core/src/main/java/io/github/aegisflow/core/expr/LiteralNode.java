package io.github.aegisflow.core.expr;

import java.util.Map;
import java.util.Objects;

/**
 * AST node representing a literal constant value (integer, double, boolean, string, or null).
 */
public class LiteralNode implements ExprNode {

    private final Object value;

    public LiteralNode(Object value) {
        this.value = value;
    }

    public Object getValue() {
        return value;
    }

    @Override
    public String toExpressionString() {
        if (value == null) return "null";
        if (value instanceof String s) return "\"" + s + "\"";
        return String.valueOf(value);
    }

    @Override
    public Object evaluate(Map<String, Object> context) {
        return value;
    }

    @Override
    public <T> T accept(ExprVisitor<T> visitor) {
        return visitor.visitLiteral(this);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        LiteralNode that = (LiteralNode) o;
        return Objects.equals(value, that.value);
    }

    @Override
    public int hashCode() {
        return Objects.hash(value);
    }

    @Override
    public String toString() {
        return toExpressionString();
    }
}
