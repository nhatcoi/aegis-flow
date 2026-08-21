# Lịch Sử Thay Đổi (Changelog)

Toàn bộ các cập nhật và thay đổi của dự án **AegisFlow** được ghi nhận chi tiết tại đây.

---

## [0.1.0-SNAPSHOT] - 21/08/2026

### Module Cốt Lõi (`aegis-flow-core`)
* **Hệ Thống Annotations DSL:** Bổ sung `@BusinessWorkflow`, `@InitialState`, `@State`, `@TerminalState`, `@Transition`, `@Invariant`, `@Rule`, `@Requires`, `@Ensures`, `@Verified`.
* **Bộ Phân Tích Biểu Thức Mini DSL:** Parser đệ quy xuống độc lập hỗ trợ logic số học, boolean, toán tử hệ quả (`==>`), và hàm thời gian (`old(...)`).
* **Kiến Trúc Micro-Kernel & SPI:** Điều phối pipeline thực thi linh hoạt qua Java ServiceLoader SPI, xuất báo cáo Dashboard và Counter-Example trực quan.

### Tích Hợp Spring Boot 3 (`aegis-flow-spring-boot-starter`)
* **AutoConfiguration:** Tích hợp Spring Boot 3 tự động, kích hoạt dễ dàng qua `@EnableBusinessVerification`.
* **Startup Runner:** Tự động quét và thực thi kiểm chứng các Bean Workflow ngay khi ứng dụng khởi động.
* **REST & Management Service:** Quản trị kết quả tập trung qua `VerificationService`, cung cấp API giám sát cho CI/CD.

### Tài Liệu & Bản Quyền
* Trang tài liệu VitePress hỗ trợ song ngữ Tiếng Việt và English.
* Đính kèm giấy phép mã nguồn mở MIT License.

---

## Kế Hoạch Các Phiên Bản Tiếp Theo

### [0.2.0] - Đang Phát Triển
* **SMT Engine (`aegis-flow-smt`):** Tích hợp Z3 Theorem Prover để chứng minh tính đúng đắn của hợp đồng và bất biến.
* **BMC Engine (`aegis-flow-bmc`):** Xây dựng đồ thị Kripke Structure, phát hiện Deadlock và trạng thái không thể chạm tới.
* **Fuzzing Engine (`aegis-flow-fuzz`):** Sinh chuỗi chuyển dịch trạng thái ngẫu nhiên để phát hiện lỗi runtime.
