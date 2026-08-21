# Viết Workflow Đầu Tiên

Dưới đây là một ví dụ thực tế về quy trình xử lý đơn hàng E-Commerce sử dụng toàn bộ hệ thống Annotation của AegisFlow.

---

## 1. Khai Báo Lớp Nghiệp Vụ `OrderWorkflow`

```java
package io.github.aegisflow.sample.order;

import io.github.aegisflow.core.annotation.*;

@BusinessWorkflow(
    name = "OrderWorkflow",
    version = "1.0.0",
    description = "Quản lý vòng đời đơn hàng trực tuyến"
)
@Invariant(value = "!(isDelivered && isCancelled)", description = "Đơn hàng đã giao thành công không thể bị hủy")
@Invariant(value = "balance >= 0", description = "Số dư tài khoản không được âm")
@Rule(id = "RULE-SHIP-01", description = "Chỉ được giao hàng khi đã thanh toán", expression = "isShipping ==> isPaid")
public class OrderWorkflow {

    public enum OrderStatus {
        @InitialState
        CREATED,

        PAID,

        SHIPPING,

        @TerminalState
        DELIVERED,

        @TerminalState
        CANCELLED
    }

    private OrderStatus status = OrderStatus.CREATED;
    private long balance = 1000;
    private long totalAmount = 250;

    public boolean isPaid() {
        return status == OrderStatus.PAID || status == OrderStatus.SHIPPING || status == OrderStatus.DELIVERED;
    }

    public boolean isShipping() {
        return status == OrderStatus.SHIPPING;
    }

    public boolean isDelivered() {
        return status == OrderStatus.DELIVERED;
    }

    public boolean isCancelled() {
        return status == OrderStatus.CANCELLED;
    }

    @Transition(from = "CREATED", to = "PAID", trigger = "pay", guard = "amount > 0 && amount <= balance")
    @Requires("amount > 0 && amount <= balance")
    @Ensures("balance == old(balance) - amount")
    public void pay(long amount) {
        if (amount <= 0 || amount > balance) {
            throw new IllegalArgumentException("Số tiền thanh toán không hợp lệ");
        }
        this.balance -= amount;
        this.status = OrderStatus.PAID;
    }

    @Transition(from = "PAID", to = "SHIPPING", trigger = "ship")
    public void ship() {
        this.status = OrderStatus.SHIPPING;
    }

    @Transition(from = "SHIPPING", to = "DELIVERED", trigger = "deliver")
    public void deliver() {
        this.status = OrderStatus.DELIVERED;
    }

    @Transition(from = "CREATED", to = "CANCELLED", trigger = "cancel")
    @Transition(from = "PAID", to = "CANCELLED", trigger = "cancel")
    public void cancel() {
        this.status = OrderStatus.CANCELLED;
    }
}
```

---

## 2. Giải Thích Các Thành Phần

1. **`@BusinessWorkflow`**: Đánh dấu lớp là đối tượng workflow cần được quét và phân tích.
2. **`@InitialState` & `@TerminalState`**: Xác định điểm bắt đầu (`CREATED`) và các điểm kết thúc (`DELIVERED`, `CANCELLED`).
3. **`@Transition`**: Khai báo các bước chuyển hợp lệ. Cho phép khai báo lặp lại (Repeatable) trên phương thức `cancel()`.
4. **`@Invariant`**: Bất biến bắt buộc luôn thỏa mãn ở mọi trạng thái (`balance >= 0`).
5. **`@Requires` & `@Ensures`**: Cam kết số dư tài khoản sau khi trừ tiền bằng đúng số dư trước khi trừ trừ đi số tiền thanh toán (`balance == old(balance) - amount`).
