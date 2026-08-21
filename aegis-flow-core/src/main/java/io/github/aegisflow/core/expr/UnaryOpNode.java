package io.github.aegisflow.core.expr;

import java.util.Map;
import java.util.Objects;

/**
 * AST node representing a unary operation (e.g., !A, -x).
 */
public class UnaryOpNode implements ExprNode {

    public enum Operator {
        NOT("!"),
        NEG("-");

        private final String symbol;

        Operator(String symbol) {
            this.symbol = symbol;
        }

        public String getSymbol() {
            return symbol;
        }
    }

    private final Operator operator;
    private final ExprNode operand;

    public UnaryOpNode(Operator operator, ExprNode operand) {
        this.operator = Objects.requireNonNull(operator, "operator cannot be null");
        this.operand = Objects.requireNonNull(operand, "operand cannot be null");
    }

    public Operator getOperator() {
        return operator;
    }

    public ExprNode getOperand() {
        return operand;
    }

    @Override
    public String toExpressionString() {
        return operator.getSymbol() + "(" + operand.toExpressionString() + ")";
    }

    @Override
    public Object evaluate(Map<String, Object> context) {
        Object val = operand.evaluate(context);
        if (operator == Operator.NOT) {
            if (val instanceof Boolean b) {
                return !b;
            }
            throw new IllegalArgumentException("Cannot negate non-boolean: " + val);
        }
        if (operator == Operator.NEG) {
            if (val instanceof Double d) return -d;
            if (val instanceof Float f) return -f;
            if (val instanceof Long l) return -l;
            if (val instanceof Integer i) return -i;
            if (val instanceof Number n) return -n.doubleValue();
            throw new IllegalArgumentException("Cannot negate non-number: " + val);
        }
        throw new UnsupportedOperationException("Unknown unary operator: " + operator);
    }

    @Override
    public <T> T accept(ExprVisitor<T> visitor) {
        return visitor.visitUnary(this);
    }

    @Override
    public String toString() {
        return toExpressionString();
    }
}
