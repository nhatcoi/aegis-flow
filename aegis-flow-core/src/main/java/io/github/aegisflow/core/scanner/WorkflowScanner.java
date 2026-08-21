package io.github.aegisflow.core.scanner;

import io.github.aegisflow.core.annotation.*;
import io.github.aegisflow.core.expr.ExprNode;
import io.github.aegisflow.core.expr.MiniExpressionParser;
import io.github.aegisflow.core.model.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.*;

/**
 * Scans Java classes and extracts the intermediate representation (IR) WorkflowDefinition.
 */
public class WorkflowScanner {

    private static final Logger log = LoggerFactory.getLogger(WorkflowScanner.class);
    private final MiniExpressionParser expressionParser;

    public WorkflowScanner() {
        this(new MiniExpressionParser());
    }

    public WorkflowScanner(MiniExpressionParser expressionParser) {
        this.expressionParser = Objects.requireNonNull(expressionParser, "expressionParser cannot be null");
    }

    /**
     * Scans the target class and constructs a WorkflowDefinition IR.
     *
     * @param targetClass the class annotated with @BusinessWorkflow or containing workflow elements
     * @return WorkflowDefinition IR
     */
    public WorkflowDefinition scan(Class<?> targetClass) {
        Objects.requireNonNull(targetClass, "targetClass cannot be null");

        BusinessWorkflow workflowAnn = targetClass.getAnnotation(BusinessWorkflow.class);
        String name = (workflowAnn != null && !workflowAnn.name().isEmpty())
                ? workflowAnn.name()
                : targetClass.getSimpleName();
        String version = workflowAnn != null ? workflowAnn.version() : "1.0.0";
        String description = workflowAnn != null ? workflowAnn.description() : "";

        WorkflowDefinition workflow = new WorkflowDefinition(name, version, description, targetClass);

        // 1. Scan states from Enums and Fields
        scanDeclaredStates(targetClass, workflow);

        // 2. Scan class-level Invariants
        scanInvariants(targetClass, workflow);

        // 3. Scan class-level Rules
        scanRules(targetClass, workflow);

        // 4. Scan class-level Transitions
        scanClassTransitions(targetClass, workflow);

        // 5. Scan methods for Transitions & Contracts
        scanMethods(targetClass, workflow);

        // 6. Ensure states referenced in transitions are registered in workflow
        reconcileTransitionStates(workflow);

        log.debug("Scanned workflow: {}", workflow);
        return workflow;
    }

    private void scanDeclaredStates(Class<?> targetClass, WorkflowDefinition workflow) {
        // Check inner enums
        for (Class<?> declaredClass : targetClass.getDeclaredClasses()) {
            if (declaredClass.isEnum()) {
                scanEnumStates(declaredClass, workflow);
            }
        }

        // Check if targetClass itself is an Enum
        if (targetClass.isEnum()) {
            scanEnumStates(targetClass, workflow);
        }

        // Check fields annotated with @State
        for (Field field : targetClass.getDeclaredFields()) {
            State stateAnn = field.getAnnotation(State.class);
            if (stateAnn != null) {
                String stateName = !stateAnn.name().isEmpty() ? stateAnn.name() : field.getName();
                boolean isInitial = field.isAnnotationPresent(InitialState.class);
                boolean isTerminal = field.isAnnotationPresent(TerminalState.class);
                workflow.addState(new StateNode(stateName, isInitial, isTerminal, stateAnn.description()));
            }
        }
    }

    private void scanEnumStates(Class<?> enumClass, WorkflowDefinition workflow) {
        for (Field enumField : enumClass.getDeclaredFields()) {
            if (enumField.isEnumConstant()) {
                String stateName = enumField.getName();
                State stateAnn = enumField.getAnnotation(State.class);
                if (stateAnn != null && !stateAnn.name().isEmpty()) {
                    stateName = stateAnn.name();
                }
                boolean isInitial = enumField.isAnnotationPresent(InitialState.class);
                boolean isTerminal = enumField.isAnnotationPresent(TerminalState.class);
                String desc = stateAnn != null ? stateAnn.description() : "";

                workflow.addState(new StateNode(stateName, isInitial, isTerminal, desc));
            }
        }
    }

    private void scanInvariants(Class<?> targetClass, WorkflowDefinition workflow) {
        Invariant[] invariants = targetClass.getAnnotationsByType(Invariant.class);
        for (Invariant inv : invariants) {
            String exprStr = inv.value();
            ExprNode ast = expressionParser.parse(exprStr);
            workflow.addInvariant(new InvariantSpec(exprStr, ast, inv.description()));
        }
    }

    private void scanRules(Class<?> targetClass, WorkflowDefinition workflow) {
        Rule[] rules = targetClass.getAnnotationsByType(Rule.class);
        for (Rule rule : rules) {
            String exprStr = rule.expression();
            ExprNode ast = expressionParser.parse(exprStr);
            workflow.addRule(new RuleSpec(rule.id(), rule.description(), exprStr, ast));
        }
    }

    private void scanClassTransitions(Class<?> targetClass, WorkflowDefinition workflow) {
        Transition[] transitions = targetClass.getAnnotationsByType(Transition.class);
        for (Transition t : transitions) {
            addTransition(workflow, t, null);
        }
    }

    private void scanMethods(Class<?> targetClass, WorkflowDefinition workflow) {
        for (Method method : targetClass.getDeclaredMethods()) {
            // Transitions on method
            Transition[] methodTransitions = method.getAnnotationsByType(Transition.class);
            for (Transition t : methodTransitions) {
                addTransition(workflow, t, method);
            }

            // Design-by-Contract: @Requires and @Ensures
            Requires[] requiresList = method.getAnnotationsByType(Requires.class);
            Ensures[] ensuresList = method.getAnnotationsByType(Ensures.class);

            if (requiresList.length > 0 || ensuresList.length > 0) {
                List<ContractSpec.Condition> preList = new ArrayList<>();
                for (Requires req : requiresList) {
                    ExprNode ast = expressionParser.parse(req.value());
                    preList.add(new ContractSpec.Condition(req.value(), ast, req.description()));
                }

                List<ContractSpec.Condition> postList = new ArrayList<>();
                for (Ensures ens : ensuresList) {
                    ExprNode ast = expressionParser.parse(ens.value());
                    postList.add(new ContractSpec.Condition(ens.value(), ast, ens.description()));
                }

                workflow.addContract(new ContractSpec(method, preList, postList));
            }
        }
    }

    private void addTransition(WorkflowDefinition workflow, Transition t, Method method) {
        String from = t.from();
        String to = t.to();
        String trigger = !t.trigger().isEmpty() ? t.trigger() : (method != null ? method.getName() : "");
        String guardRaw = t.guard();
        ExprNode guardAst = expressionParser.parse(guardRaw);

        workflow.addTransition(new TransitionEdge(from, to, trigger, guardRaw, guardAst, t.description(), method));
    }

    private void reconcileTransitionStates(WorkflowDefinition workflow) {
        for (TransitionEdge edge : workflow.getTransitions()) {
            if (workflow.getState(edge.getFromState()).isEmpty()) {
                workflow.addState(new StateNode(edge.getFromState(), false, false, "Inferred from transition source"));
            }
            if (workflow.getState(edge.getToState()).isEmpty()) {
                workflow.addState(new StateNode(edge.getToState(), false, false, "Inferred from transition destination"));
            }
        }
    }
}
