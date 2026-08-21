package io.github.aegisflow.core.report;

import java.util.*;

/**
 * Concrete counter-example found by an automated verification engine (e.g. SMT or BMC)
 * demonstrating an execution path or input values that violate a business invariant/rule.
 */
public class CounterExample {

    private final String description;
    private final Map<String, Object> variables;
    private final List<String> executionTrace;

    public CounterExample(String description, Map<String, Object> variables, List<String> executionTrace) {
        this.description = description != null ? description : "Counter-example found";
        this.variables = variables != null ? new LinkedHashMap<>(variables) : Collections.emptyMap();
        this.executionTrace = executionTrace != null ? new ArrayList<>(executionTrace) : Collections.emptyList();
    }

    public String getDescription() {
        return description;
    }

    public Map<String, Object> getVariables() {
        return Collections.unmodifiableMap(variables);
    }

    public List<String> getExecutionTrace() {
        return Collections.unmodifiableList(executionTrace);
    }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder("CounterExample: ").append(description);
        if (!variables.isEmpty()) {
            sb.append("\n  Assignments: ").append(variables);
        }
        if (!executionTrace.isEmpty()) {
            sb.append("\n  Trace: ").append(String.join(" -> ", executionTrace));
        }
        return sb.toString();
    }
}
