package io.github.aegisflow.core.expr;

import java.util.Map;
import java.util.Objects;

/**
 * AST node representing a binary operation (e.g., A + B, A && B, A >= B).
 */
public class BinaryOpNode implements ExprNode {

    public enum Operator {
        ADD("+"),
        SUB("-"),
        MUL("*"),
        DIV("/"),
        MOD("%"),
        EQ("=="),
        NE("!="),
        LT("<"),
        LE("<="),
        GT(">"),
        GE(">="),
        AND("&&"),
        OR("||"),
        IMPLIES("==>");

        private final String symbol;

        Operator(String symbol) {
            this.symbol = symbol;
        }

        public String getSymbol() {
            return symbol;
        }

        public static Operator fromSymbol(String s) {
            for (Operator op : values()) {
                if (op.symbol.equals(s)) {
                    return op;
                }
            }
            throw new IllegalArgumentException("Unknown binary operator: " + s);
        }
    }

    private final ExprNode left;
    private final Operator operator;
    private final ExprNode right;

    public BinaryOpNode(ExprNode left, Operator operator, ExprNode right) {
        this.left = Objects.requireNonNull(left, "left node cannot be null");
        this.operator = Objects.requireNonNull(operator, "operator cannot be null");
        this.right = Objects.requireNonNull(right, "right node cannot be null");
    }

    public ExprNode getLeft() {
        return left;
    }

    public Operator getOperator() {
        return operator;
    }

    public ExprNode getRight() {
        return right;
    }

    @Override
    public String toExpressionString() {
        return "(" + left.toExpressionString() + " " + operator.getSymbol() + " " + right.toExpressionString() + ")";
    }

    @Override
    public Object evaluate(Map<String, Object> context) {
        Object leftVal = left.evaluate(context);
        
        // Short-circuit evaluations for logical operators
        if (operator == Operator.AND) {
            boolean l = toBoolean(leftVal);
            if (!l) return false;
            return toBoolean(right.evaluate(context));
        }
        if (operator == Operator.OR) {
            boolean l = toBoolean(leftVal);
            if (l) return true;
            return toBoolean(right.evaluate(context));
        }
        if (operator == Operator.IMPLIES) {
            boolean l = toBoolean(leftVal);
            if (!l) return true; // !A || B
            return toBoolean(right.evaluate(context));
        }

        Object rightVal = right.evaluate(context);

        if (operator == Operator.EQ) {
            return Objects.equals(leftVal, rightVal);
        }
        if (operator == Operator.NE) {
            return !Objects.equals(leftVal, rightVal);
        }

        // Numeric operations
        if (leftVal instanceof Number lNum && rightVal instanceof Number rNum) {
            boolean isDouble = (leftVal instanceof Double || rightVal instanceof Double ||
                               leftVal instanceof Float || rightVal instanceof Float);
            if (isDouble) {
                double l = lNum.doubleValue();
                double r = rNum.doubleValue();
                return switch (operator) {
                    case ADD -> l + r;
                    case SUB -> l - r;
                    case MUL -> l * r;
                    case DIV -> l / r;
                    case MOD -> l % r;
                    case LT -> l < r;
                    case LE -> l <= r;
                    case GT -> l > r;
                    case GE -> l >= r;
                    default -> throw new UnsupportedOperationException("Operator " + operator + " not supported for numbers");
                };
            } else {
                long l = lNum.longValue();
                long r = rNum.longValue();
                return switch (operator) {
                    case ADD -> l + r;
                    case SUB -> l - r;
                    case MUL -> l * r;
                    case DIV -> l / r;
                    case MOD -> l % r;
                    case LT -> l < r;
                    case LE -> l <= r;
                    case GT -> l > r;
                    case GE -> l >= r;
                    default -> throw new UnsupportedOperationException("Operator " + operator + " not supported for integers");
                };
            }
        }

        // String concatenation
        if (operator == Operator.ADD && (leftVal instanceof String || rightVal instanceof String)) {
            return String.valueOf(leftVal) + String.valueOf(rightVal);
        }

        throw new UnsupportedOperationException("Cannot apply operator " + operator + " to " + leftVal + " and " + rightVal);
    }

    private boolean toBoolean(Object val) {
        if (val instanceof Boolean b) {
            return b;
        }
        if (val == null) return false;
        throw new IllegalArgumentException("Expected boolean value, but got: " + val);
    }

    @Override
    public <T> T accept(ExprVisitor<T> visitor) {
        return visitor.visitBinary(this);
    }

    @Override
    public String toString() {
        return toExpressionString();
    }
}
