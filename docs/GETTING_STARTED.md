# Quick Start Guide (Getting Started)

Welcome to **AegisFlow**! This guide will help you install, configure, and verify your first business workflow in under **5 minutes**.

---

## 1. Add Maven / Gradle Dependencies

### Maven (`pom.xml`)
```xml
<!-- Spring Boot 3 Applications -->
<dependency>
    <groupId>io.github.aegisflow</groupId>
    <artifactId>aegis-flow-spring-boot-starter</artifactId>
    <version>0.1.0-SNAPSHOT</version>
</dependency>

<!-- Core Java Applications (Without Spring) -->
<dependency>
    <groupId>io.github.aegisflow</groupId>
    <artifactId>aegis-flow-core</artifactId>
    <version>0.1.0-SNAPSHOT</version>
</dependency>
```

### Gradle (`build.gradle`)
```groovy
// Spring Boot Starter
implementation 'io.github.aegisflow:aegis-flow-spring-boot-starter:0.1.0-SNAPSHOT'

// Core Java
implementation 'io.github.aegisflow:aegis-flow-core:0.1.0-SNAPSHOT'
```

---

## 2. Define a Business Workflow

```java
package com.example.shop;

import io.github.aegisflow.core.annotation.*;

@BusinessWorkflow(
    name = "OrderWorkflow",
    version = "1.0.0",
    description = "E-Commerce Order Processing Workflow"
)
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

    public boolean isShipping() {
        return state == OrderState.SHIPPING;
    }

    public boolean isDelivered() {
        return state == OrderState.DELIVERED;
    }

    public boolean isCancelled() {
        return state == OrderState.CANCELLED;
    }

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

---

## 3. Run Verification in Unit Tests

```java
import io.github.aegisflow.core.pipeline.VerificationPipeline;
import io.github.aegisflow.core.report.VerificationReport;
import io.github.aegisflow.core.report.VerificationStatus;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class OrderWorkflowTest {

    @Test
    void testVerifyOrderWorkflow() {
        VerificationPipeline pipeline = VerificationPipeline.createDefault();
        VerificationReport report = pipeline.verifyClass(OrderWorkflow.class);

        System.out.println(report.toPrettyString());

        assertThat(report.getStatus()).isEqualTo(VerificationStatus.PASSED);
        assertThat(report.hasErrors()).isFalse();
    }
}
```

---

## 4. Automated Startup Verification with Spring Boot

Enable automatic verification by adding `@EnableBusinessVerification` to your Spring Boot main class:

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
