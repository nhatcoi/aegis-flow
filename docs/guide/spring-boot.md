# Spring Boot Starter

The `aegis-flow-spring-boot-starter` module provides automatic integration for **Spring Boot 3.x** applications.

---

## 1. Quick Activation with `@EnableBusinessVerification`

Add `@EnableBusinessVerification` to your main application class:

```java
package com.example.shop;

import io.github.aegisflow.boot.annotation.EnableBusinessVerification;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@EnableBusinessVerification(scanPackages = {"com.example.shop.workflow"})
public class ShopApplication {
    public static void main(String[] args) {
        SpringApplication.run(ShopApplication.class, args);
    }
}
```

---

## 2. Automated Startup Verification Lifecycle

When the Spring Boot application boots:

1. **Auto-Discovery:** Automatically scans the `ApplicationContext` and configured packages for beans annotated with `@BusinessWorkflow`.
2. **Pipeline Execution:** Discovers and runs all registered verification engines.
3. **Console Dashboard:** Outputs a structured report directly into the startup logs:

```text
2026-08-21T11:07:02.673+07:00  INFO [main] BusinessVerificationRunner : Starting automated AegisFlow Business Workflow Verification...

+==========================================================================+
|  AEGISFLOW VERIFICATION REPORT: OrderProcessingWorkflow                     |
+==========================================================================+
|  Overall Status: PASSED            Total Time: 0      ms                 |
+==========================================================================+
|  ENGINES SUMMARY:                                                        |
|    (No engines were executed)                                            |
+==========================================================================+
```
