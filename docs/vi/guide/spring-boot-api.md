# Cấu Hình application.yml & REST API

---

## 1. Các Thuộc Tính Trong `application.yml`

```yaml
aegisflow:
  verification:
    # Bật/Tắt tính năng kiểm chứng tự động khi khởi động (Mặc định: true)
    enabled: true

    # Dừng khởi động nếu phát hiện lỗi nghiêm trọng (Mặc định: false)
    fail-on-error: true

    # Danh sách các package cần quét workflow
    scan-packages:
      - com.example.shop.workflow
      - com.example.shop.domain

logging:
  level:
    io.github.aegisflow: DEBUG
```

---

## 2. Truy Xuất Báo Cáo Qua REST API

Bạn có thể inject bean `VerificationService` để tạo endpoint cung cấp báo cáo cho Frontend hoặc hệ thống giám sát CI/CD:

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

## 3. Kiểm Thử Tự Động Với `@SpringBootTest`

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
            .as("Quy trình nghiệp vụ không được có bất kỳ vi phạm nào")
            .isFalse();

        verificationService.getReports().values().forEach(report -> {
            assertThat(report.getStatus()).isEqualTo(VerificationStatus.PASSED);
        });
    }
}
```
