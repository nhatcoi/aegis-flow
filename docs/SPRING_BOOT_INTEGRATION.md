# Spring Boot 3 Integration Guide

The **`aegis-flow-spring-boot-starter`** module provides zero-configuration integration with **Spring Boot 3.x** applications on **Java 21 LTS**.

---

## 1. Installation

```xml
<dependency>
    <groupId>io.github.aegisflow</groupId>
    <artifactId>aegis-flow-spring-boot-starter</artifactId>
    <version>0.1.0-SNAPSHOT</version>
</dependency>
```

---

## 2. Activation

Annotate your primary configuration or main application class with `@EnableBusinessVerification`:

```java
package com.example.app;

import io.github.aegisflow.boot.annotation.EnableBusinessVerification;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@EnableBusinessVerification(scanPackages = {"com.example.app.workflow"})
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

---

## 3. Configuration Properties (`application.yml`)

```yaml
aegisflow:
  verification:
    # Enable or disable startup verification
    enabled: true

    # Fail application startup if any critical rule violation is detected
    fail-on-error: true

    # Base packages to scan for @BusinessWorkflow definitions
    scan-packages:
      - com.example.app.workflow
      - com.example.app.domain

logging:
  level:
    io.github.aegisflow: DEBUG
```

---

## 4. Verification Management REST Controller

Inject `VerificationService` to expose verification reports:

```java
package com.example.app.controller;

import io.github.aegisflow.boot.service.VerificationService;
import io.github.aegisflow.core.report.VerificationReport;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/verification")
public class VerificationController {

    private final VerificationService verificationService;

    public VerificationController(VerificationService verificationService) {
        this.verificationService = verificationService;
    }

    @GetMapping("/reports")
    public ResponseEntity<Map<String, VerificationReport>> getReports() {
        return ResponseEntity.ok(verificationService.getReports());
    }

    @PostMapping("/run")
    public ResponseEntity<Map<String, Object>> runAll() {
        var reports = verificationService.verifyAll();
        return ResponseEntity.ok(Map.of(
            "totalWorkflows", reports.size(),
            "hasErrors", verificationService.hasErrors()
        ));
    }
}
```

---

## 5. Automated CI/CD Testing with `@SpringBootTest`

```java
package com.example.app;

import io.github.aegisflow.boot.service.VerificationService;
import io.github.aegisflow.core.report.VerificationStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
class ApplicationWorkflowVerificationTest {

    @Autowired
    private VerificationService verificationService;

    @Test
    void testAllBusinessWorkflowsPass() {
        assertThat(verificationService.hasErrors())
            .as("Business workflows must not contain unreachable states or contract violations")
            .isFalse();

        verificationService.getReports().values().forEach(report -> {
            assertThat(report.getStatus()).isEqualTo(VerificationStatus.PASSED);
        });
    }
}
```
