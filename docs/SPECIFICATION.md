# DSL Annotations & Intermediate Representation (IR) Specification

This specification defines the Annotation DSL and Intermediate Representation (IR) structures for **AegisFlow**.

---

## 1. Annotation Syntax & Semantic Rules

### 1.1 `@BusinessWorkflow`
* **Target:** `ElementType.TYPE`
* **Retention:** `RetentionPolicy.RUNTIME`
* **Attributes:**
  * `name`: String identifier of the workflow.
  * `version`: Semantic version string (e.g., `"1.0.0"`).
  * `description`: Optional documentation note.

### 1.2 State Annotations (`@InitialState`, `@State`, `@TerminalState`)
* **Target:** `ElementType.FIELD`
* **Rules:**
  * Exactly one `@InitialState` per workflow.
  * At least one `@TerminalState` per workflow.
  * Multiple intermediate `@State` fields are permitted.

### 1.3 `@Transition`
* **Target:** `ElementType.METHOD` (Repeatable via `@Transitions`)
* **Attributes:**
  * `from`: Source state name.
  * `to`: Destination state name.
  * `trigger`: Event identifier (defaults to method name).
  * `guard`: Optional boolean expression that must evaluate to `true` to allow transition.

### 1.4 Contracts & Invariants (`@Requires`, `@Ensures`, `@Invariant`, `@Rule`)
* **`@Requires`**: Method precondition expression.
* **`@Ensures`**: Method postcondition expression (supports `old(...)` syntax).
* **`@Invariant`**: Class-level invariant guaranteed across all states.
* **`@Rule`**: Implication logic (`conditionA ==> conditionB`).

---

## 2. Intermediate Representation (IR) Models

The scanner extracts raw annotations into immutable domain models:

* **`WorkflowDefinition`**: Represents a parsed workflow graph, containing states, edges, invariants, and method contracts.
* **`StateNode`**: Encapsulates state type (`INITIAL`, `INTERMEDIATE`, `TERMINAL`) and name.
* **`TransitionEdge`**: Encapsulates source, destination, method trigger, guard expression, and preconditions/postconditions.
* **`InvariantSpec` & `RuleSpec`**: Parsed AST expressions paired with human-readable descriptions.
