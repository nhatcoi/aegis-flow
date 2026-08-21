<div align="center">

# AegisFlow

**A Modular Business Workflow & Domain Rules Verification Framework for Java & Spring Boot**

[English](README.md) | [Tiếng Việt](README-VI.md) | [Documentation (Live)](https://nhatcoi.github.io/aegis-flow/)

[![Java](https://img.shields.io/badge/Java-21%2B%20LTS-orange.svg)](https://openjdk.org/)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.x-brightgreen.svg)](https://spring.io/projects/spring-boot)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/Docs-GitHub%20Pages-blueviolet.svg)](https://nhatcoi.github.io/aegis-flow/)

</div>

---

## 1. Overview

**AegisFlow** is an open-source formal verification and safety analysis framework designed for Software Engineers developing mission-critical systems (E-Commerce, Banking, Fintech, Logistics, Supply Chain).

Traditional unit tests validate individual execution paths with specific mock values, leaving combinatorial edge cases undiscovered. **AegisFlow** combines mathematical verification tools (**SMT Solvers via Microsoft Z3**, **Bounded Model Checking via Kripke Structures**, and **Property Fuzzing**) directly into the Java and Spring Boot ecosystem.

---

## 2. Key Features

* **Contract-Driven Design (DbC):** Enforce method integrity with `@Requires`, `@Ensures`, and temporal delta tracking using `old(variable)`.
* **State Machine Verification:** Automatically construct Kripke state graphs from `@InitialState`, `@State`, `@TerminalState`, and `@Transition` to detect deadlocks and unreachable states.
* **SMT-Based Invariant Proofs:** Translate class invariants (`@Invariant`) and business rules (`@Rule("isShipping ==> isPaid")`) into first-order logic formulas for SMT Solvers.
* **Spring Boot 3 Native Starter:** Zero-configuration integration via `@EnableBusinessVerification`. Automatically verifies workflow beans on application startup and exposes REST monitoring endpoints.
* **Actionable Counter-Examples:** Whenever an invariant or contract is violated, AegisFlow generates the exact state transition trace and variable valuations to accelerate debugging.

---

## 3. Project Structure (Multi-Module)

| Module | Description | Dependencies |
| :--- | :--- | :--- |
| **`aegis-flow-core`** | Annotations DSL, AST Parser, Intermediate Representation (IR), Micro-Kernel SPI, Pipeline Coordinator, Verification Report. | Pure Java 21 LTS (Zero external dependencies). |
| **`aegis-flow-smt`** | SMT-based Formal Verification Engine using Microsoft Z3 Solver. | `aegis-flow-core`, `com.microsoft.z3`. |
| **`aegis-flow-bmc`** | Bounded Model Checking (BMC) and Kripke State Graph Reachability Engine. | `aegis-flow-core`. |
| **`aegis-flow-fuzz`** | Automated property-based mutation and state transition fuzzing engine. | `aegis-flow-core`. |
| **`aegis-flow-spring-boot-starter`** | Spring Boot 3 AutoConfiguration, startup verification runner, and management service. | `aegis-flow-core`, Spring Boot 3.x. |
| **`aegis-flow-samples`** | Practical reference implementations (`aegis-flow-sample-order`, `aegis-flow-sample-spring-boot`). | Core and verification modules. |

---

## 4. Quick Start

### 4.1 Add Dependencies

```xml
<!-- For Spring Boot 3 Applications -->
<dependency>
    <groupId>io.github.aegisflow</groupId>
    <artifactId>aegis-flow-spring-boot-starter</artifactId>
    <version>0.1.0-SNAPSHOT</version>
</dependency>

<!-- For Core Java Applications -->
<dependency>
    <groupId>io.github.aegisflow</groupId>
    <artifactId>aegis-flow-core</artifactId>
    <version>0.1.0-SNAPSHOT</version>
</dependency>
```

### 4.2 Define an Annotated Workflow

```java
package com.example.shop;

import io.github.aegisflow.core.annotation.*;

@BusinessWorkflow(name = "OrderWorkflow", version = "1.0.0")
@Invariant(value = "!(isDelivered && isCancelled)", description = "An order cannot be delivered and cancelled")
@Invariant(value = "balance >= 0", description = "Account balance cannot become negative")
@Rule(id = "RULE-SHIP-01", description = "Order must be paid before shipping", expression = "isShipping ==> isPaid")
public class OrderWorkflow {

    public enum OrderState {
        @InitialState CREATED,
        PAID,
        SHIPPING,
        @TerminalState DELIVERED,
        @TerminalState CANCELLED
    }

    private OrderState state = OrderState.CREATED;
    private long balance = 1000;

    public boolean isPaid() {
        return state == OrderState.PAID || state == OrderState.SHIPPING || state == OrderState.DELIVERED;
    }

    public boolean isShipping() { return state == OrderState.SHIPPING; }
    public boolean isDelivered() { return state == OrderState.DELIVERED; }
    public boolean isCancelled() { return state == OrderState.CANCELLED; }

    @Transition(from = "CREATED", to = "PAID", trigger = "pay", guard = "amount > 0 && amount <= balance")
    @Requires("amount > 0 && balance >= amount")
    @Ensures("balance == old(balance) - amount")
    public void pay(long amount) {
        this.balance -= amount;
        this.state = OrderState.PAID;
    }

    @Transition(from = "PAID", to = "SHIPPING", trigger = "ship")
    public void ship() {
        this.state = OrderState.SHIPPING;
    }

    @Transition(from = "SHIPPING", to = "DELIVERED", trigger = "deliver")
    public void deliver() {
        this.state = OrderState.DELIVERED;
    }

    @Transition(from = "CREATED", to = "CANCELLED", trigger = "cancel")
    @Transition(from = "PAID", to = "CANCELLED", trigger = "cancel")
    public void cancel() {
        this.state = OrderState.CANCELLED;
    }
}
```

### 4.3 Run Verification in Tests

```java
import io.github.aegisflow.core.pipeline.VerificationPipeline;
import io.github.aegisflow.core.report.VerificationReport;
import io.github.aegisflow.core.report.VerificationStatus;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class OrderWorkflowTest {

    @Test
    void testWorkflowIntegrity() {
        VerificationPipeline pipeline = VerificationPipeline.createDefault();
        VerificationReport report = pipeline.verifyClass(OrderWorkflow.class);

        System.out.println(report.toPrettyString());

        assertThat(report.getStatus()).isEqualTo(VerificationStatus.PASSED);
        assertThat(report.hasErrors()).isFalse();
    }
}
```

### 4.4 Automated Startup Verification in Spring Boot

```java
package com.example.shop;

import io.github.aegisflow.boot.annotation.EnableBusinessVerification;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@EnableBusinessVerification(scanPackages = {"com.example.shop"})
public class ShopApplication {
    public static void main(String[] args) {
        SpringApplication.run(ShopApplication.class, args);
    }
}
```

---

## 5. Live Documentation

The comprehensive bilingual documentation site is hosted on GitHub Pages:

* **English Documentation:** [https://nhatcoi.github.io/aegis-flow/](https://nhatcoi.github.io/aegis-flow/)
* **Vietnamese Documentation:** [https://nhatcoi.github.io/aegis-flow/vi/](https://nhatcoi.github.io/aegis-flow/vi/)

---

## 6. License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
