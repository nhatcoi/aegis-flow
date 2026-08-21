# Tích Hợp Spring Boot Starter

Module **`aegis-flow-spring-boot-starter`** tích hợp hoàn toàn tự động vào các ứng dụng **Spring Boot 3.x** (Java 21 LTS).

---

## 1. Khởi Động Nhanh Với `@EnableBusinessVerification`

Thêm annotation `@EnableBusinessVerification` tại lớp cấu hình chính hoặc `@SpringBootApplication`:

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

## 2. Vòng Đời Tự Động Khởi Chạy (Auto Startup Verification)

Khi ứng dụng Spring Boot khởi động:

1. **Auto-Discovery:** Starter tự động quét ApplicationContext và các package được cấu hình để tìm các Bean có gắn `@BusinessWorkflow`.
2. **Pipeline Execution:** Thực thi pipeline kiểm chứng qua tất cả các engine đã đăng ký.
3. **Console Dashboard:** In bảng báo cáo trực quan ra log hệ thống:

```text
2026-08-21T10:47:29.435+07:00  INFO [main] BusinessVerificationRunner : Starting automated AegisFlow Business Workflow Verification...

╔══════════════════════════════════════════════════════════════════════════╗
║  AEGISFLOW VERIFICATION REPORT: OrderProcessingWorkflow                       ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Overall Status: PASSED            Total Time: 0      ms               ║
╠══════════════════════════════════════════════════════════════════════════╣
║  ENGINES SUMMARY:                                                        ║
║    (No engines were executed)                                            ║
╚══════════════════════════════════════════════════════════════════════════╝
```
