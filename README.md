# AegisFlow (BusinessGuard)

> **A Modular Business Process & Rules Verification Framework for Java / Spring Boot**  
> *Nền tảng phân tích, kiểm thử và kiểm chứng hình thức quy trình nghiệp vụ trên nền tảng Java 21.*

---

## 1. Tổng Quan

**AegisFlow** là một framework mã nguồn mở được thiết kế theo kiến trúc Micro-Kernel / Plugin SPI, giúp các kỹ sư phần mềm (Software Engineers) có thể:
1. **Mô hình hóa quy trình (Workflow Modeling):** Khai báo các trạng thái và chuyển dịch trạng thái qua hệ thống Annotation tiện lợi (`@BusinessWorkflow`, `@Transition`).
2. **Kiểm chứng hình thức (Formal Verification):** Tự động phát hiện lỗi logic, deadlock, trạng thái không thể chạm tới (unreachable states) và vi phạm bất biến nghiệp vụ bằng các công cụ toán học (SMT Solver Z3, Bounded Model Checking).
3. **Kiểm thử tự động (Fuzzing):** Sinh tự động các chuỗi thao tác giả lập người dùng tại runtime để phát hiện lỗi tiềm ẩn.
4. **Tích hợp CI/CD:** Chạy tự động trong quá trình build Maven (`mvn verify`), ngăn chặn mã nguồn chứa lỗi logic được merge vào nhánh chính.

---

## 2. Cấu Trúc Dự Án (Maven Multi-Module)

```text
aegis-flow/
├── pom.xml                         # Root POM quản lý dependencies
├── docs/                           # Tài liệu VitePress (English & Tiếng Việt)
├── aegis-flow-core/                    # Module cốt lõi (Annotations, IR, Scanner, SPI, Pipeline)
├── aegis-flow-smt/                     # Module SMT Verification (Z3 Solver)
├── aegis-flow-bmc/                     # Module Bounded Model Checking (State Graph)
├── aegis-flow-fuzz/                    # Module Fuzzing quy trình nghiệp vụ
├── aegis-flow-spring-boot-starter/     # AutoConfiguration cho Spring Boot
└── aegis-flow-samples/                 # Dự án mẫu kiểm chứng thực tế
    ├── aegis-flow-sample-order/        # Sample Order Workflow Java thuần
    └── aegis-flow-sample-spring-boot/  # Sample Spring Boot Web Application
```

---

## 3. Hướng Dẫn Sử Dụng Nhanh (Quick Start)

### Khai Báo Workflow Nghiệp Vụ

```java
import io.github.aegisflow.core.annotation.*;

@BusinessWorkflow(name = "OrderWorkflow")
@Invariant(value = "!(isDelivered && isCancelled)", description = "Đơn đã giao không thể bị hủy")
public class OrderWorkflow {

    public enum OrderState {
        @InitialState CREATED,
        PAID,
        SHIPPING,
        @TerminalState DELIVERED,
        @TerminalState CANCELLED
    }

    @Transition(from = "CREATED", to = "PAID", trigger = "pay", guard = "amount > 0 && amount <= balance")
    @Requires("balance >= amount")
    @Ensures("balance == old(balance) - amount")
    public void pay(int balance, int amount) {
        // Business logic
    }

    @Transition(from = "PAID", to = "SHIPPING", trigger = "ship")
    public void ship() {
        // Business logic
    }

    @Transition(from = "SHIPPING", to = "DELIVERED", trigger = "deliver")
    public void deliver() {
        // Business logic
    }
}
```

### Thực Thi Kiểm Chứng

```java
import io.github.aegisflow.core.pipeline.VerificationPipeline;
import io.github.aegisflow.core.report.VerificationReport;

public class Main {
    public static void main(String[] args) {
        VerificationPipeline pipeline = VerificationPipeline.createDefault();
        VerificationReport report = pipeline.verifyClass(OrderWorkflow.class);
        
        System.out.println(report.toPrettyString());
        if (report.hasErrors()) {
            System.exit(1);
        }
    }
}
```

---

## 4. Hệ Thống Tài Liệu (VitePress i18n: English & Tiếng Việt)

Trang tài liệu chính thức được xây dựng bằng **[VitePress](https://vitepress.dev/)** hỗ trợ song ngữ **English** và **Tiếng Việt**, tìm kiếm tức thì và Dark/Light Mode.

### Chạy Trang Tài Liệu Trực Tiếp:
```bash
# Cài đặt dependency và chạy dev server
npm install
npm run docs:dev

# Build trang tài liệu tĩnh (sẵn sàng deploy GitHub Pages / Vercel / Netlify)
npm run docs:build
```

### Danh Mục Tài Liệu Chi Tiết:
* **English:**
  * Getting Started: [`docs/guide/getting-started.md`](file:///home/nhatcoi/Documents/personal/aegis-flow/docs/guide/getting-started.md)
  * Annotations DSL: [`docs/guide/annotations.md`](file:///home/nhatcoi/Documents/personal/aegis-flow/docs/guide/annotations.md)
  * Design by Contract: [`docs/guide/design-by-contract.md`](file:///home/nhatcoi/Documents/personal/aegis-flow/docs/guide/design-by-contract.md)
  * Spring Boot 3 Integration: [`docs/guide/spring-boot.md`](file:///home/nhatcoi/Documents/personal/aegis-flow/docs/guide/spring-boot.md)
  * FAQ & Comparisons: [`docs/reference/faq.md`](file:///home/nhatcoi/Documents/personal/aegis-flow/docs/reference/faq.md)
  * Micro-Kernel Architecture: [`docs/reference/architecture.md`](file:///home/nhatcoi/Documents/personal/aegis-flow/docs/reference/architecture.md)
* **Tiếng Việt:**
  * Cài Đặt Nhanh: [`docs/vi/guide/getting-started.md`](file:///home/nhatcoi/Documents/personal/aegis-flow/docs/vi/guide/getting-started.md)
  * Cẩm Nang Annotations: [`docs/vi/guide/annotations.md`](file:///home/nhatcoi/Documents/personal/aegis-flow/docs/vi/guide/annotations.md)
  * Thiết Kế Theo Hợp Đồng: [`docs/vi/guide/design-by-contract.md`](file:///home/nhatcoi/Documents/personal/aegis-flow/docs/vi/guide/design-by-contract.md)
  * Tích Hợp Spring Boot 3: [`docs/vi/guide/spring-boot.md`](file:///home/nhatcoi/Documents/personal/aegis-flow/docs/vi/guide/spring-boot.md)
  * FAQ & So Sánh Thư Viện: [`docs/vi/reference/faq.md`](file:///home/nhatcoi/Documents/personal/aegis-flow/docs/vi/reference/faq.md)

---

## 5. Bản Quyền

Dự án được phát hành dưới giấy phép MIT License.
