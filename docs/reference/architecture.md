# Micro-Kernel Architecture & SPI

---

## 1. System Architecture Diagram

```text
+-------------------------------------------------------------+
|                 APPLICATION / DOMAIN LAYER                  |
|       @BusinessWorkflow, @State, @Transition, @Invariant    |
+------------------------------+------------------------------+
                               | (Java Reflection / Metadata)
+------------------------------v------------------------------+
|                    JGUARD SCANNER & PARSER                  |
|        - WorkflowScanner extracts AST & Contracts           |
|        - MiniExpressionParser parses DSL expressions        |
+------------------------------+------------------------------+
                               | WorkflowDefinition (IR)
+------------------------------v------------------------------+
|              VERIFICATION PIPELINE (MICRO-KERNEL)           |
|           Java ServiceLoader SPI (Discovery Engine)         |
+------+-----------------------+-----------------------+------+
       | (SPI)                 | (SPI)                 | (SPI)
+------v------+         +------v------+         +------v------+
|  aegis-flow-smt │         |  aegis-flow-bmc │         | aegis-flow-fuzz │
| (Z3 Solver) |         |(Graph Model)|         |  (Fuzzing)  |
+-------------+         +-------------+         +-------------+
```

---

## 2. Service Provider Interface (`VerificationEngine`)

Every verification engine implements the `VerificationEngine` SPI:

```java
package io.github.aegisflow.core.spi;

import io.github.aegisflow.core.model.WorkflowDefinition;

public interface VerificationEngine {

    String getEngineId();

    String getName();

    EngineResult verify(WorkflowDefinition workflow, VerificationContext context);

    default boolean isEnabledByDefault() {
        return true;
    }
}
```

Engines are automatically discovered at runtime via standard Java `java.util.ServiceLoader` declarations in `META-INF/services/io.github.aegisflow.core.spi.VerificationEngine`.
