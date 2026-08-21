package io.github.aegisflow.core.model;

import java.util.Objects;

/**
 * Intermediate representation of a state in a business workflow.
 */
public class StateNode {

    private final String name;
    private final boolean initial;
    private final boolean terminal;
    private final String description;

    public StateNode(String name, boolean initial, boolean terminal, String description) {
        this.name = Objects.requireNonNull(name, "state name cannot be null").trim();
        this.initial = initial;
        this.terminal = terminal;
        this.description = description != null ? description : "";
    }

    public String getName() {
        return name;
    }

    public boolean isInitial() {
        return initial;
    }

    public boolean isTerminal() {
        return terminal;
    }

    public String getDescription() {
        return description;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        StateNode stateNode = (StateNode) o;
        return Objects.equals(name, stateNode.name);
    }

    @Override
    public int hashCode() {
        return Objects.hash(name);
    }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder(name);
        if (initial) sb.append(" [INITIAL]");
        if (terminal) sb.append(" [TERMINAL]");
        return sb.toString();
    }
}
