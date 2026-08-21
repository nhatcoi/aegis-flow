# System Architecture & Technical Design

This document details the software architecture of **AegisFlow** — A formal verification and business domain rules analysis framework designed for Java 21 LTS and Spring Boot 3 applications.

---

## 1. Architectural Philosophy: Micro-Kernel & Plugin SPI

AegisFlow employs a **Micro-Kernel (Plugin-based)** architecture powered by the Java **Service Provider Interface (SPI)** mechanism:

```text
+-----------------------------------------------------------------------------+
|                          CLIENT APPLICATION LAYER                           |
|        Domain Models, Enums, Business Services, Workflows, Spring Beans     |
+--------------------------------------+--------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                               aegis-flow-core                               |
|  +-------------------------+  +-------------------+  +-------------------+  |
|  |    Annotations & DSL    |  |   Scanner Engine  |  |  Intermediate     |  |
|  |   (@BusinessWorkflow,   |  | (Reflection / AST |  |  Representation   |  |
|  |   @Transition, etc.)    |  |    Inspection)    |  |   (IR Metadata)   |  |
|  +-------------------------+  +-------------------+  +-------------------+  |
|  +-----------------------------------------------------------------------+  |
|  |                     Verification Pipeline Coordinator                 |  |
|  +-----------------------------------------------------------------------+  |
+--------------------------------------+--------------------------------------+
                                       | (Java ServiceLoader SPI Discovery)
         +-----------------------------+-----------------------------+
         v                             v                             v
 +---------------+             +---------------+             +---------------+
 | aegis-flow-smt|             | aegis-flow-bmc|             |aegis-flow-fuzz|
 |(Z3 SMT Solver)|             |(Bounded Model)|             | (State Fuzzer)|
 +---------------+             +---------------+             +---------------+
         |                             |                             |
         +-----------------------------+-----------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                              REPORTING LAYER                                |
|  - ASCII Terminal Dashboard          - JUnit 5 Assertion Assertions         |
|  - Spring Boot Actuator / REST APIs  - Actionable Counter-Example Traces    |
+-----------------------------------------------------------------------------+
```

---

## 2. Multi-Module Project Structure

| Module | Core Responsibility | Key Dependencies |
| :--- | :--- | :--- |
| **`aegis-flow-core`** | Annotations, Intermediate Representation (IR), AST Parser, SPI Specifications, Pipeline Coordinator, Verification Report Models. | Standard Java 21 only (Zero external dependencies). |
| **`aegis-flow-smt`** | SMT-based Formal Verification using Z3 Solver to prove method contracts and class invariants. | `aegis-flow-core`, `com.microsoft.z3`. |
| **`aegis-flow-bmc`** | State Graph Reachability & Bounded Model Checking (deadlocks, unreachable states, circular traps). | `aegis-flow-core`. |
| **`aegis-flow-fuzz`** | Automated property-based fuzzing and state transition permutation engine. | `aegis-flow-core`. |
| **`aegis-flow-spring-boot-starter`** | Spring Boot 3 `AutoConfiguration`, `@EnableBusinessVerification`, startup lifecycle runner. | `aegis-flow-core`, Spring Boot 3.x. |
| **`aegis-flow-samples`** | Practical reference applications (`aegis-flow-sample-order`, `aegis-flow-sample-spring-boot`). | Core and verification engines. |

---

## 3. The `VerificationEngine` SPI Contract

Third-party verification engines or domain plugins implement the standard `VerificationEngine` interface:

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

Registered engines are declared in `META-INF/services/io.github.aegisflow.core.spi.VerificationEngine` and discovered seamlessly at runtime.
