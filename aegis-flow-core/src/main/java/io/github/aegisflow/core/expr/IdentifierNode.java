package io.github.aegisflow.core.expr;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;
import java.util.Objects;

/**
 * AST node representing a variable identifier or property path (e.g., "balance", "order.status").
 */
public class IdentifierNode implements ExprNode {

    private final String name;

    public IdentifierNode(String name) {
        this.name = Objects.requireNonNull(name, "identifier name cannot be null").trim();
    }

    public String getName() {
        return name;
    }

    @Override
    public String toExpressionString() {
        return name;
    }

    @Override
    public Object evaluate(Map<String, Object> context) {
        if (context == null) return null;
        if (context.containsKey(name)) {
            return context.get(name);
        }

        // Support dot notation: e.g. "order.isDelivered" or "user.age"
        if (name.contains(".")) {
            String[] parts = name.split("\\.");
            Object current = context.get(parts[0]);
            for (int i = 1; i < parts.length && current != null; i++) {
                current = resolveProperty(current, parts[i]);
            }
            return current;
        }

        return null;
    }

    private Object resolveProperty(Object target, String propName) {
        if (target == null) return null;
        if (target instanceof Map<?, ?> map) {
            return map.get(propName);
        }
        
        Class<?> clazz = target.getClass();
        // 1. Try getter method: getProp() or isProp()
        String capitalized = Character.toUpperCase(propName.charAt(0)) + (propName.length() > 1 ? propName.substring(1) : "");
        for (String methodName : new String[]{"get" + capitalized, "is" + capitalized, propName}) {
            try {
                Method m = clazz.getMethod(methodName);
                m.setAccessible(true);
                return m.invoke(target);
            } catch (Exception ignored) {
            }
        }

        // 2. Try direct field
        try {
            Field f = clazz.getDeclaredField(propName);
            f.setAccessible(true);
            return f.get(target);
        } catch (Exception ignored) {
        }

        return null;
    }

    @Override
    public <T> T accept(ExprVisitor<T> visitor) {
        return visitor.visitIdentifier(this);
    }

    @Override
    public String toString() {
        return toExpressionString();
    }
}
