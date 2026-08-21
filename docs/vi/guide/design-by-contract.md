# Thiết Kế Theo Hợp Đồng (Design by Contract)

Nguyên lý **Design by Contract (DbC)** giúp đảm bảo tính toàn vẹn của phương thức bằng cách định rõ trách nhiệm giữa bên gọi (Caller) và bên thực thi (Callee).

---

## 1. Tiền Điều Kiện (`@Requires` - Precondition)

Tiền điều kiện là nghĩa vụ mà bên gọi bắt buộc phải đáp ứng trước khi phương thức được thực thi:

```java
@Requires("amount > 0")
@Requires("accountBalance >= amount")
public void transfer(long amount, Account target) {
    this.accountBalance -= amount;
    target.deposit(amount);
}
```

Nếu tiền điều kiện không thỏa mãn, phương thức không có trách nhiệm phải thực thi và pipeline kiểm chứng sẽ cảnh báo nếu phát hiện có luồng gọi vi phạm.

---

## 2. Hậu Điều Kiện (`@Ensures` - Postcondition)

Hậu điều kiện là cam kết về trạng thái của đối tượng sau khi phương thức hoàn thành:

```java
@Requires("amount > 0 && accountBalance >= amount")
@Ensures("accountBalance == old(accountBalance) - amount")
public void withdraw(long amount) {
    this.accountBalance -= amount;
}
```

### Hàm Đặc Biệt: `old(...)`
Hàm `old(variable)` cho phép bạn tham chiếu đến giá trị của biến **ngay trước khi phương thức bắt đầu chạy**.

| Biểu thức | Ý nghĩa |
| :--- | :--- |
| `balance == old(balance) - amount` | Số dư mới phải giảm đúng bằng `amount` |
| `itemCount == old(itemCount) + 1` | Số lượng phần tử tăng thêm đúng 1 |
| `totalPrice == old(totalPrice)` | Tổng giá trị không bị thay đổi sau thao tác |
