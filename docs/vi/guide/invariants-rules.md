# ️ Bất Biến & Luật Nghiệp Vụ (Invariants & Rules)

---

## 1. Bất Biến Lớp (`@Invariant`)

**Bất biến (Class Invariant)** là biểu thức logic bắt buộc phải đúng:
1. Sau khi đối tượng được khởi tạo.
2. Trước và sau mỗi lần gọi bất kỳ phương thức chuyển trạng thái nào.

```java
@BusinessWorkflow(name = "BankAccountWorkflow")
@Invariant(value = "balance >= 0", description = "Số dư tài khoản không được âm")
@Invariant(value = "overdraftLimit >= 0", description = "Hạn mức thấu chi không được âm")
public class BankAccountWorkflow {
    private long balance = 0;
    private long overdraftLimit = 1000;
    ...
}
```

::: warning LỖI VI PHẠM BẤT BIẾN
Nếu một bước chuyển trạng thái làm cho `balance < 0`, engine SMT và Pipeline sẽ phát hiện và đánh dấu trạng thái kiểm chứng là `FAILED`, kèm theo Counter-Example giá trị biến vi phạm.
:::

---

## 2. Luật Nghiệp Vụ (`@Rule`) & Toán Tử Kéo Theo (`==>`)

Quy tắc `@Rule` thường dùng để mô hình hóa các mệnh đề logic ràng buộc quan hệ:

$$\text{Điều kiện A} \implies \text{Điều kiện B}$$

Cú pháp: `expression = "A ==> B"` (tương đương $\neg A \lor B$)

### Ví dụ Thực Tế:

```java
@Rule(
    id = "RULE-SHIP-01",
    description = "Nếu đơn hàng đang giao, bắt buộc đơn hàng đã được thanh toán",
    expression = "isShipping ==> isPaid"
)
@Rule(
    id = "RULE-REFUND-01",
    description = "Số tiền hoàn không được vượt quá số tiền đã thanh toán",
    expression = "refundAmount <= capturedAmount"
)
public class OrderWorkflow { ... }
```
