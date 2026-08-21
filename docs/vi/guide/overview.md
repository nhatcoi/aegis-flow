# Tổng Quan & Bài Toán Giải Quyết

## 1. Vấn Đề Trong Phát Triển Ứng Dụng Doanh Nghiệp

Trong các hệ thống phức tạp như **E-Commerce**, **Ngân hàng số (Fintech)**, **Logistics** hay **Quản lý kho**, các lỗi sai sót logic thường rơi vào các trường hợp:

* **Chuyển trạng thái bất hợp pháp:** Đơn hàng chưa thanh toán nhưng đã được xuất kho giao hàng (`SHIPPING`), hoặc đơn hàng đã giao thành công (`DELIVERED`) lại bị chuyển sang trạng thái hủy (`CANCELLED`).
* **Vi phạm bất biến dữ liệu xuyên suốt thời gian:** Số dư tài khoản bị âm sau chuỗi giao dịch, số tiền hoàn trả lớn hơn số tiền đã thanh toán.
* **Deadlock / Unreachable States:** Có những trạng thái không bao giờ có đường đi tới hoặc bị kẹt trong vòng lặp vô tận không thể thoát ra trạng thái kết thúc (`Terminal State`).

::: danger NGUY CƠ TIỀM ẨN
Các lỗi logic nghiệp vụ này cực kỳ khó bắt bằng Unit Test thông thường vì số lượng tổ hợp trạng thái và giá trị biến số đầu vào bùng nổ theo cấp số nhân (State Explosion).
:::

---

## 2. Khoảng Trống Thị Trường (Market Gap)

Hiện tại, các thư viện phổ biến trong hệ sinh thái Java chỉ giải quyết được một phần của bài toán:

| Thư viện | Phạm vi giải quyết | Hạn chế đối với kiểm chứng |
| :--- | :--- | :--- |
| **Spring Statemachine** | Thực thi luồng tại runtime khi có event | Không có khả năng chứng minh toán học xem liệu trạng thái lỗi/deadlock có thể xảy ra hay không |
| **Hibernate Validator (JSR-380)** | Kiểm tra trường dữ liệu đơn lẻ tại một thời điểm | Không kiểm tra được ràng buộc biến thiên qua thời gian (`old(balance) - amount`) |
| **ArchUnit** | Kiểm tra cấu trúc package / class | Không kiểm tra được domain logic & business rules |
| **AegisFlow** | **Chứng minh hình thức toàn bộ luồng nghiệp vụ & sinh phản ví dụ** | **Bảo vệ toàn diện trước khi code được deploy lên Production** |

---

## 3. Kiến Trúc 3 Trụ Cột Của AegisFlow

```text
┌─────────────────────────────────────────────────────────────┐
│                 BUSINESS WORKFLOW MODEL                     │
│                                                             │
│   1. State Machine:    @InitialState, @State, @TerminalState│
│   2. Transitions:      @Transition (from, to, trigger, guard│
│   3. Invariants:       @Invariant (luôn đúng tại mọi state) │
│   4. Business Rules:   @Rule (luật điều kiện kéo theo ==>)  │
│   5. Method Contracts: @Requires, @Ensures, old(...)        │
└─────────────────────────────────────────────────────────────┘
```

1. **State Space & Reachability:** Dựng đồ thị chuyển trạng thái và kiểm tra tính liên thông, phát hiện nút chết (Deadlock) hoặc nút cô lập (Unreachable).
2. **SMT Formal Verification:** Chuyển đổi các điều kiện `@Invariant` và `@Rule` thành công thức logic hình thức để Z3 Solver tìm phản ví dụ.
3. **Design by Contract:** Kiểm chứng tiền điều kiện (`@Requires`) và hậu điều kiện (`@Ensures`) với khả năng truy xuất giá trị quá khứ (`old(...)`).
