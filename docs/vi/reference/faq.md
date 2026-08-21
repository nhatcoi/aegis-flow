# Câu Hỏi Thường Gặp (FAQ & So Sánh)

---

### 1. AegisFlow khác gì so với Spring Statemachine?
* **Spring Statemachine** là công cụ **thực thi luồng runtime** (State Machine Engine) giúp chuyển đổi trạng thái khi có event. Nó **không** có khả năng chứng minh hình thức (Formal Verification) xem liệu trạng thái `DEADLOCK` có thể xảy ra hay không, hoặc liệu các bất biến toán học có bao giờ bị vi phạm dưới mọi điều kiện biến số hay không.
* **AegisFlow** là **Static & Formal Verification Framework**: Nó phân tích tĩnh, xây dựng đồ thị trạng thái, dùng SMT Solver và BMC để **chứng minh** tính đúng đắn trước khi code được deploy lên Production.

---

### 2. AegisFlow khác gì so với Hibernate Validator / Bean Validation (JSR-380)?
* **Hibernate Validator** chỉ kiểm tra dữ liệu **tại một thời điểm đơn lẻ** (Single snapshot / field-level validation như `@NotNull`, `@Min(18)`).
* **AegisFlow** kiểm chứng **ràng buộc xuyên suốt thời gian (Temporal / Contract / Workflow-level)**:
  * Sự thay đổi giá trị giữa quá khứ và hiện tại: `balance == old(balance) - amount`.
  * Mối quan hệ giữa các trạng thái khác nhau: `isShipping ==> isPaid`.
  * Tính bất biến toàn vẹn qua nhiều bước chuyển trạng thái: `!(isDelivered && isCancelled)`.

---

### 3. AegisFlow khác gì so với ArchUnit?
* **ArchUnit** kiểm tra kiến trúc mã nguồn theo cấu trúc package/class (ví dụ: Controller không được gọi Repository trực tiếp).
* **AegisFlow** kiểm chứng **Domain Logic & Business Rules** (luật nghiệp vụ, logic toán học, trạng thái hợp lệ).

---

### 4. Tôi có cần cài đặt Z3 Solver C++ trên máy để dùng không?
* Không bắt buộc. Module `aegis-flow-smt` được thiết kế tương thích với Z3 Java Native Bindings.
* Đối với `aegis-flow-core` và `aegis-flow-spring-boot-starter`, framework hoàn toàn là **Pure Java 21 standard library** không cần bất kỳ native binary nào.

---

### 5. Xử lý lỗi `fail-on-error` trong môi trường CI/CD như thế nào?
Trong môi trường CI/CD (như GitHub Actions, GitLab CI), bạn nên đặt `fail-on-error: true` hoặc chạy `mvn test`. Nếu có bất kỳ vi phạm logic hoặc lỗ hổng bất biến nào, build sẽ tự động fail và xuất Counter-Example để developer sửa ngay trước khi merge code.
