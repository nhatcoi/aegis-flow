# Quick Start (5 Minutes)

Learn how to integrate AegisFlow into your Java 21 or Spring Boot 3 application.

---

## 1. Add Dependencies

::: code-group

```xml [Maven (pom.xml)]
<!-- For Spring Boot 3 -->
<dependency>
    <groupId>io.github.aegisflow</groupId>
    <artifactId>aegis-flow-spring-boot-starter</artifactId>
    <version>0.1.0-SNAPSHOT</version>
</dependency>

<!-- For Core Java (No Spring dependency) -->
<dependency>
    <groupId>io.github.aegisflow</groupId>
    <artifactId>aegis-flow-core</artifactId>
    <version>0.1.0-SNAPSHOT</version>
</dependency>
```

```groovy [Gradle (build.gradle)]
// For Spring Boot 3
implementation 'io.github.aegisflow:aegis-flow-spring-boot-starter:0.1.0-SNAPSHOT'

// For Core Java
implementation 'io.github.aegisflow:aegis-flow-core:0.1.0-SNAPSHOT'
```

:::

---

## 2. Requirements

* **Java:** Version 21 LTS or newer.
* **Spring Boot (Optional):** Version 3.0.x or newer.
* **Build Tools:** Maven 3.8+ or Gradle 8.0+.

---

## 3. Run Verification in Unit Tests (Core Java)

When using `aegis-flow-core` independently, execute the verification pipeline using `VerificationPipeline`:

```java
import io.github.aegisflow.core.pipeline.VerificationPipeline;
import io.github.aegisflow.core.report.VerificationReport;
import io.github.aegisflow.core.report.VerificationStatus;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class OrderWorkflowVerificationTest {

    @Test
    void testVerifyWorkflow() {
        VerificationPipeline pipeline = VerificationPipeline.createDefault();
        VerificationReport report = pipeline.verifyClass(OrderWorkflow.class);

        // Output ASCII Dashboard to console
        System.out.println(report.toPrettyString());

        // Assert verification status
        assertThat(report.getStatus()).isEqualTo(VerificationStatus.PASSED);
        assertThat(report.hasErrors()).isFalse();
    }
}
```

::: tip NEXT STEP
Proceed to [Your First Workflow](./first-workflow.md) to see a complete workflow example using AegisFlow annotations.
:::
