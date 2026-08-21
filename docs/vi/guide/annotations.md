# ️ Hệ Thống Annotations DSL

Bảng tra cứu toàn bộ danh mục Annotation DSL trong AegisFlow.

---

## 1. Danh Mục Chi Tiết

| Annotation | Phạm vi áp dụng | Mục đích |
| :--- | :--- | :--- |
| **`@BusinessWorkflow`** | Class | Đánh dấu class là quy trình nghiệp vụ cần kiểm chứng |
| **`@InitialState`** | Enum Constant / Field | Đánh dấu trạng thái khởi đầu của workflow (bắt buộc đúng 1) |
| **`@State`** | Enum Constant / Field | Đánh dấu trạng thái trung gian thông thường |
| **`@TerminalState`** | Enum Constant / Field | Đánh dấu trạng thái kết thúc (không thể chuyển đi tiếp) |
| **`@Transition`** | Method | Định nghĩa bước chuyển trạng thái (`from`, `to`, `trigger`, `guard`) |
| **`@Invariant`** | Class | Điều kiện bất biến luôn luôn phải đúng tại mọi thời điểm |
| **`@Rule`** | Class | Quy tắc nghiệp vụ logic kéo theo (`==>`) |
| **`@Requires`** | Method | Tiền điều kiện bắt buộc trước khi gọi hàm (Precondition) |
| **`@Ensures`** | Method | Hậu điều kiện cam kết sau khi hàm kết thúc (Postcondition) |
| **`@Verified`** | Class / Package | Kích hoạt kiểm chứng hình thức tại lúc compile hoặc startup |

---

## 2. Tính Năng Repeatable Annotations

AegisFlow hỗ trợ gắn lặp lại nhiều Annotation trên cùng một phần tử mà không gây xung đột:

::: code-group

```java [Nhiều Bước Chuyển (@Transition)]
// Cho phép hủy từ CREATED hoặc từ PAID
@Transition(from = "CREATED", to = "CANCELLED", trigger = "cancel")
@Transition(from = "PAID", to = "CANCELLED", trigger = "cancel")
public void cancel() {
    this.status = OrderStatus.CANCELLED;
}
```

```java [Nhiều Bất Biến (@Invariant)]
@Invariant(value = "balance >= 0", description = "Số dư không âm")
@Invariant(value = "!(isDelivered && isCancelled)", description = "Không thể vừa giao vừa hủy")
public class AccountWorkflow { ... }
```

```java [Nhiều Hợp Đồng (@Requires, @Ensures)]
@Requires("amount > 0")
@Requires("balance >= amount")
@Ensures("balance == old(balance) - amount")
public void withdraw(long amount) { ... }
```

:::
