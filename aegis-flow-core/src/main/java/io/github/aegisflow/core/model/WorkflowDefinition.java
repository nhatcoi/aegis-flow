package io.github.aegisflow.core.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * Top-level Intermediate Representation (IR) of a business workflow extracted from annotated classes.
 */
public class WorkflowDefinition {

    private final String name;
    private final String version;
    private final String description;
    private final Class<?> targetClass;

    private final Map<String, StateNode> states = new LinkedHashMap<>();
    private final List<TransitionEdge> transitions = new ArrayList<>();
    private final List<InvariantSpec> invariants = new ArrayList<>();
    private final List<RuleSpec> rules = new ArrayList<>();
    private final List<ContractSpec> contracts = new ArrayList<>();

    public WorkflowDefinition(String name, String version, String description, Class<?> targetClass) {
        this.name = Objects.requireNonNull(name, "workflow name cannot be null").trim();
        this.version = version != null ? version.trim() : "1.0.0";
        this.description = description != null ? description.trim() : "";
        this.targetClass = targetClass;
    }

    public String getName() {
        return name;
    }

    public String getVersion() {
        return version;
    }

    public String getDescription() {
        return description;
    }

    public Class<?> getTargetClass() {
        return targetClass;
    }

    public void addState(StateNode state) {
        states.put(state.getName(), state);
    }

    public Map<String, StateNode> getStates() {
        return Collections.unmodifiableMap(states);
    }

    public Optional<StateNode> getState(String stateName) {
        return Optional.ofNullable(states.get(stateName));
    }

    public Optional<StateNode> getInitialState() {
        return states.values().stream().filter(StateNode::isInitial).findFirst();
    }

    public List<StateNode> getTerminalStates() {
        return states.values().stream().filter(StateNode::isTerminal).toList();
    }

    public void addTransition(TransitionEdge transition) {
        transitions.add(transition);
    }

    public List<TransitionEdge> getTransitions() {
        return Collections.unmodifiableList(transitions);
    }

    public List<TransitionEdge> getTransitionsFrom(String fromState) {
        return transitions.stream()
                .filter(t -> t.getFromState().equalsIgnoreCase(fromState))
                .toList();
    }

    public void addInvariant(InvariantSpec invariant) {
        invariants.add(invariant);
    }

    public List<InvariantSpec> getInvariants() {
        return Collections.unmodifiableList(invariants);
    }

    public void addRule(RuleSpec rule) {
        rules.add(rule);
    }

    public List<RuleSpec> getRules() {
        return Collections.unmodifiableList(rules);
    }

    public void addContract(ContractSpec contract) {
        contracts.add(contract);
    }

    public List<ContractSpec> getContracts() {
        return Collections.unmodifiableList(contracts);
    }

    @Override
    public String toString() {
        return "WorkflowDefinition[" + name + " (v" + version + "), States=" + states.size() +
                ", Transitions=" + transitions.size() + ", Invariants=" + invariants.size() +
                ", Rules=" + rules.size() + ", Contracts=" + contracts.size() + "]";
    }
}
