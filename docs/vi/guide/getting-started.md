# Cài Đặt (5 Phút)

Hướng dẫn tích hợp AegisFlow vào dự án Java 21 hoặc Spring Boot 3 của bạn.

---

## 1. Cấu Hình Dependency

::: code-group

```xml [Maven (pom.xml)]
<!-- Dành cho Spring Boot 3 -->
<dependency>
    <groupId>io.github.aegisflow</groupId>
    <artifactId>aegis-flow-spring-boot-starter</artifactId>
    <version>0.1.0-SNAPSHOT</version>
</dependency>

<!-- Dành cho ứng dụng Java Core thuần -->
<dependency>
    <groupId>io.github.aegisflow</groupId>
    <artifactId>aegis-flow-core</artifactId>
    <version>0.1.0-SNAPSHOT</version>
</dependency>
```

```groovy [Gradle (build.gradle)]
// Dành cho Spring Boot 3
implementation 'io.github.aegisflow:aegis-flow-spring-boot-starter:0.1.0-SNAPSHOT'

// Dành cho Java Core thuần
implementation 'io.github.aegisflow:aegis-flow-core:0.1.0-SNAPSHOT'
```

:::

---

## 2. Yêu Cầu Hệ Thống

* **Java:** Phiên bản 21 LTS trở lên.
* **Spring Boot (Tùy chọn):** Phiên bản 3.0.x trở lên.
* **Maven / Gradle:** Phiên bản Maven 3.8+ hoặc Gradle 8.0+.

---

## 3. Chạy Kiểm Chứng Trong Unit Test (Java Core)

Nếu bạn không sử dụng Spring Boot, bạn có thể thực thi pipeline kiểm chứng trực tiếp bằng `VerificationPipeline`:

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

        // In Dashboard trực tiếp ra log/console
        System.out.println(report.toPrettyString());

        // Khẳng định trạng thái kiểm chứng PASSED
        assertThat(report.getStatus()).isEqualTo(VerificationStatus.PASSED);
        assertThat(report.hasErrors()).isFalse();
    }
}
```

::: tip TIẾP THEO
Hãy xem tiếp trang [Workflow Đầu Tiên](./first-workflow.md) để học cách viết một lớp nghiệp vụ hoàn chỉnh với các Annotation DSL.
:::
