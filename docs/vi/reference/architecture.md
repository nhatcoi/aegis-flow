# ️ Kiến Trúc Micro-Kernel & Cơ Chế Cắm-Rút SPI

---

## 1. Sơ Đồ Kiến Trúc Hệ Thống

```text
┌─────────────────────────────────────────────────────────────┐
│                 APPLICATION / DOMAIN LAYER                  │
│       @BusinessWorkflow, @State, @Transition, @Invariant    │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Java Reflection / Bytecode)
┌──────────────────────────────▼──────────────────────────────┐
│                    AegisFlow SCANNER & PARSER                    │
│        • WorkflowScanner trích xuất AST & Contract          │
│        • MiniExpressionParser phân tích cú pháp DSL         │
└──────────────────────────────┬──────────────────────────────┘
                               │ WorkflowDefinition (IR)
┌──────────────────────────────▼──────────────────────────────┐
│              VERIFICATION PIPELINE (MICRO-KERNEL)           │
│           Java ServiceLoader SPI (Discovery Engine)         │
└──────┬───────────────────────┼───────────────────────┬──────┘
       │ (SPI)                 │ (SPI)                 │ (SPI)
┌──────▼──────┐         ┌──────▼──────┐         ┌──────▼──────┐
│  aegis-flow-smt   │         │  aegis-flow-bmc   │         │  aegis-flow-fuzz  │
│ (Z3 Solver) │         │(Graph Model)│         │  (Fuzzing)  │
└─────────────┘         └─────────────┘         └─────────────┘
```

---

## 2. Giao Diện Service Provider Interface (`VerificationEngine`)

Mọi engine kiểm chứng đều cài đặt interface `VerificationEngine`:

```java
package io.github.aegisflow.core.spi;

import io.github.aegisflow.core.model.WorkflowDefinition;

public interface VerificationEngine {

    String getEngineId();

    String getName();

    EngineResult verify(WorkflowDefinition workflow, VerificationContext context);

    default boolean isEnabledByDefault() {
        return true;
    }
}
```

Các engine được tự động phát hiện qua chuẩn Java `java.util.ServiceLoader` (file `META-INF/services/io.github.aegisflow.core.spi.VerificationEngine`), đảm bảo người dùng chỉ cần thêm dependency Maven là engine tương ứng sẽ tự động kích hoạt.
