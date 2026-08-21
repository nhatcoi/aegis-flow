package io.github.aegisflow.core.expr;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;

/**
 * AST node representing a function call in constraints (e.g. old(balance), abs(x), isEmpty(list)).
 */
public class FunctionCallNode implements ExprNode {

    private final String functionName;
    private final List<ExprNode> arguments;

    public FunctionCallNode(String functionName, List<ExprNode> arguments) {
        this.functionName = Objects.requireNonNull(functionName, "functionName cannot be null");
        this.arguments = arguments != null ? new ArrayList<>(arguments) : Collections.emptyList();
    }

    public String getFunctionName() {
        return functionName;
    }

    public List<ExprNode> getArguments() {
        return Collections.unmodifiableList(arguments);
    }

    @Override
    public String toExpressionString() {
        String args = arguments.stream()
                .map(ExprNode::toExpressionString)
                .collect(Collectors.joining(", "));
        return functionName + "(" + args + ")";
    }

    @Override
    public Object evaluate(Map<String, Object> context) {
        // Built-in evaluation handlers
        if ("old".equalsIgnoreCase(functionName) && arguments.size() == 1) {
            ExprNode arg = arguments.get(0);
            if (arg instanceof IdentifierNode id) {
                String oldKey = "old_" + id.getName();
                if (context != null && context.containsKey(oldKey)) {
                    return context.get(oldKey);
                }
            }
            return arg.evaluate(context);
        }

        if ("abs".equalsIgnoreCase(functionName) && arguments.size() == 1) {
            Object val = arguments.get(0).evaluate(context);
            if (val instanceof Number n) {
                return Math.abs(n.doubleValue());
            }
        }

        if ("min".equalsIgnoreCase(functionName) && arguments.size() == 2) {
            Object v1 = arguments.get(0).evaluate(context);
            Object v2 = arguments.get(1).evaluate(context);
            if (v1 instanceof Number n1 && v2 instanceof Number n2) {
                return Math.min(n1.doubleValue(), n2.doubleValue());
            }
        }

        if ("max".equalsIgnoreCase(functionName) && arguments.size() == 2) {
            Object v1 = arguments.get(0).evaluate(context);
            Object v2 = arguments.get(1).evaluate(context);
            if (v1 instanceof Number n1 && v2 instanceof Number n2) {
                return Math.max(n1.doubleValue(), n2.doubleValue());
            }
        }

        throw new UnsupportedOperationException("Function '" + functionName + "' is not supported in evaluation mode");
    }

    @Override
    public <T> T accept(ExprVisitor<T> visitor) {
        return visitor.visitFunctionCall(this);
    }

    @Override
    public String toString() {
        return toExpressionString();
    }
}
