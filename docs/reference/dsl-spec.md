# Mini DSL Grammar Specification

AegisFlow includes a self-contained Recursive Descent Parser with zero external dependencies.

---

## 1. Operator Precedence

From lowest to highest precedence:

| Order | Operator Type | Syntax | Associativity |
| :---: | :--- | :---: | :---: |
| **1** | Implication | `==>` | Right-to-Left |
| **2** | Logical OR | `\|\|` | Left-to-Right |
| **3** | Logical AND | `&&` | Left-to-Right |
| **4** | Equality / Inequality | `==`, `!=` | Left-to-Right |
| **5** | Relational comparisons | `<`, `<=`, `>`, `>=` | Left-to-Right |
| **6** | Addition / Subtraction | `+`, `-` | Left-to-Right |
| **7** | Multiplication / Division / Modulo | `*`, `/`, `%` | Left-to-Right |
| **8** | Unary negation / NOT | `!`, `-` | Right-to-Left |
| **9** | Member access & function call | `.`, `f(...)` | Left-to-Right |
| **10** | Atoms & Parentheses | Numbers, Booleans, Identifiers, `(...)` | - |

---

## 2. Built-in Functions

* **`old(x)`**: Retrieves the value of variable `x` prior to method invocation.
* **`abs(x)`**: Absolute value of $x$.
* **`min(a, b)`**: Minimum value between $a$ and $b$.
* **`max(a, b)`**: Maximum value between $a$ and $b$.

---

## 3. Abstract Syntax Tree (AST)

All expressions are parsed into AST nodes extending `ExprNode`:

* `BinaryOpNode(ExprNode left, BinaryOp op, ExprNode right)`
* `UnaryOpNode(UnaryOp op, ExprNode expr)`
* `IdentifierNode(String name)`
* `LiteralNode(Object value)`
* `FunctionCallNode(String functionName, List<ExprNode> arguments)`
