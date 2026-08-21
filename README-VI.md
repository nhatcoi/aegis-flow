<div align="center">

# AegisFlow

**Nền Tảng Phân Tích & Kiểm Chứng Hình Thức Quy Trình Nghiệp Vụ Cho Java & Spring Boot**

[English](README.md) | [Tiếng Việt](README-VI.md) | [Tài Liệu Trực Tuyến (Live)](https://nhatcoi.github.io/aegis-flow/vi/)

[![Java](https://img.shields.io/badge/Java-21%2B%20LTS-orange.svg)](https://openjdk.org/)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.x-brightgreen.svg)](https://spring.io/projects/spring-boot)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/Docs-GitHub%20Pages-blueviolet.svg)](https://nhatcoi.github.io/aegis-flow/vi/)

</div>

---

## 1. Tổng Quan

**AegisFlow** là một framework mã nguồn mở được phát triển theo định hướng Kỹ nghệ Phần mềm (Software Engineering) kết hợp với các phương pháp Kiểm chứng Hình thức (Formal Methods), giúp bảo vệ tính toàn vẹn của hệ thống phần mềm nghiệp vụ quan trọng (E-Commerce, Ngân hàng, Fintech, Logistics).

Khác với các bài kiểm thử đơn vị (Unit Test) truyền thống chỉ kiểm tra các kịch bản mẫu rời rạc, **AegisFlow** ứng dụng các công cụ toán học (**SMT Solver Z3**, **Đồ thị trạng thái Kripke / Bounded Model Checking**, và **Fuzzing đột biến**) trực tiếp vào hệ sinh thái Java và Spring Boot.

---

## 2. Các Tính Năng Cốt Lõi

* **Thiết Kế Theo Hợp Đồng (Design by Contract):** Ràng buộc tiền/hậu điều kiện phương thức với `@Requires`, `@Ensures`, và theo dõi biến thiên dữ liệu qua thời gian với hàm `old(biến)`.
* **Kiểm Chứng Đồ Thị Trạng Thái (BMC):** Tự động xây dựng đồ thị Kripke từ `@InitialState`, `@State`, `@TerminalState`, `@Transition` để phát hiện Deadlock và trạng thái không thể chạm tới (Unreachable States).
* **Chứng Minh Bất Biến Bằng SMT Solver:** Chuyển đổi bất biến lớp (`@Invariant`) và luật nghiệp vụ (`@Rule("isShipping ==> isPaid")`) thành bài toán logic vị từ để SMT Solver (Microsoft Z3) chứng minh tính đúng đắn.
* **Tích Hợp Tự Động Spring Boot 3:** Kích hoạt chỉ với `@EnableBusinessVerification`. Tự động quét các Bean Workflow khi ứng dụng khởi động và cung cấp REST API giám sát.
* **Báo Cáo & Vết Vi Phạm (Counter-Examples):** Khi phát hiện vi phạm, AegisFlow xuất chính xác chuỗi chuyển dịch trạng thái và giá trị biến vi phạm giúp kỹ sư sửa lỗi nhanh chóng.

---

## 3. Cấu Trúc Dự Án (Maven Multi-Module)

| Module | Chức năng chính | Phụ thuộc |
| :--- | :--- | :--- |
| **`aegis-flow-core`** | Annotations DSL, AST Parser, Cấu trúc trung gian (IR), Micro-Kernel SPI, Pipeline điều phối, Báo cáo kiểm chứng. | Pure Java 21 LTS (Không có phụ thuộc ngoài). |
| **`aegis-flow-smt`** | Engine kiểm chứng hình thức sử dụng SMT Solver (Microsoft Z3). | `aegis-flow-core`, `com.microsoft.z3`. |
| **`aegis-flow-bmc`** | Engine Bounded Model Checking (BMC) và duyệt đồ thị trạng thái Kripke. | `aegis-flow-core`. |
| **`aegis-flow-fuzz`** | Engine kiểm thử mờ (Fuzzing) đột biến chuỗi chuyển dịch trạng thái. | `aegis-flow-core`. |
| **`aegis-flow-spring-boot-starter`** | Spring Boot 3 AutoConfiguration, Runner kiểm chứng khởi động và Service quản trị. | `aegis-flow-core`, Spring Boot 3.x. |
| **`aegis-flow-samples`** | Các dự án mẫu minh họa thực tế (`aegis-flow-sample-order`, `aegis-flow-sample-spring-boot`). | Module Core và các Engine. |

---

## 4. Hướng Dẫn Sử Dụng Nhanh (Quick Start)

### 4.1 Thêm Dependency

```xml
<!-- Dành cho ứng dụng Spring Boot 3 -->
<dependency>
    <groupId>io.github.aegisflow</groupId>
    <artifactId>aegis-flow-spring-boot-starter</artifactId>
    <version>0.1.0-SNAPSHOT</version>
</dependency>

<!-- Dành cho ứng dụng Java thuần -->
<dependency>
    <groupId>io.github.aegisflow</groupId>
    <artifactId>aegis-flow-core</artifactId>
    <version>0.1.0-SNAPSHOT</version>
</dependency>
```

### 4.2 Khai Báo Workflow Nghiệp Vụ

```java
package com.example.shop;

import io.github.aegisflow.core.annotation.*;

@BusinessWorkflow(name = "OrderWorkflow", version = "1.0.0")
@Invariant(value = "!(isDelivered && isCancelled)", description = "Đơn hàng không thể vừa giao vừa bị hủy")
@Invariant(value = "balance >= 0", description = "Số dư tài khoản không được âm")
@Rule(id = "RULE-SHIP-01", description = "Đơn hàng phải thanh toán trước khi giao", expression = "isShipping ==> isPaid")
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

### 4.3 Thực Thi Kiểm Chứng Trong Unit Test

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

### 4.4 Tự Động Kiểm Chứng Khi Khởi Động Spring Boot

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

## 5. Trang Tài Liệu Trực Tuyến

Trang tài liệu chính thức được xuất bản trên GitHub Pages:

* **Tài liệu Tiếng Việt:** [https://nhatcoi.github.io/aegis-flow/vi/](https://nhatcoi.github.io/aegis-flow/vi/)
* **Tài liệu English:** [https://nhatcoi.github.io/aegis-flow/](https://nhatcoi.github.io/aegis-flow/)

---

## 6. Giấy Phép (License)

Dự án được phát hành theo giấy phép mã nguồn mở MIT License - xem file [LICENSE](LICENSE) để biết thêm chi tiết.
