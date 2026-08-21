# Configuration & REST API

---

## 1. Properties in `application.yml`

```yaml
jguard:
  verification:
    # Enable/disable startup verification (Default: true)
    enabled: true

    # Fail application startup if critical errors are detected (Default: false)
    fail-on-error: true

    # Packages to scan for workflows
    scan-packages:
      - com.example.shop.workflow
      - com.example.shop.domain

logging:
  level:
    io.github.aegisflow: DEBUG
```

---

## 2. Accessing Reports via REST API

Inject the `VerificationService` bean to expose reports to frontend dashboards or CI/CD monitors:

```java
package com.example.shop.controller;

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
    public ResponseEntity<Map<String, Object>> triggerReverification() {
        var reports = verificationService.verifyAll();
        return ResponseEntity.ok(Map.of(
            "totalWorkflows", reports.size(),
            "hasErrors", verificationService.hasErrors()
        ));
    }
}
```

---

## 3. Automated `@SpringBootTest` Integration

```java
package com.example.shop;

import io.github.aegisflow.boot.service.VerificationService;
import io.github.aegisflow.core.report.VerificationStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
class ApplicationWorkflowTest {

    @Autowired
    private VerificationService verificationService;

    @Test
    void testAllWorkflowsAreValid() {
        assertThat(verificationService.hasErrors())
            .as("Business workflows must not contain any rule or invariant violations")
            .isFalse();

        verificationService.getReports().values().forEach(report -> {
            assertThat(report.getStatus()).isEqualTo(VerificationStatus.PASSED);
        });
    }
}
```
