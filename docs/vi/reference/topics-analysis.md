# Phân Tích 5 Nhóm Đề Tài Môn Học AegisFlow

Tài liệu này tổng hợp phân tích từ bài toán môn học **An Toàn Phần Mềm (AegisFlow) / Kiểm Chứng Hình Thức** và chiến lược tích hợp vào nền tảng công nghiệp.

---

## 1. Năm Nhóm Đề Tài Học Thuật

1. **Nhóm 1: Kripke Structure & Bounded Model Checking (BMC)**
   * Dựng không gian trạng thái hữu hạn ($S, S_0, R, L$) và kiểm tra tính đúng đắn của đường đi trong phạm vi $k$ bước chuyển.
   * *Hiện thực:* Module `aegis-flow-bmc` phân tích tính liên thông của `@State` và `@Transition`.
2. **Nhóm 2: Memory Safety & Static Analysis**
   * Phân tích tĩnh luồng dữ liệu, phát hiện rò rỉ hoặc truy cập con trỏ null.
   * *Hiện thực:* Module `aegis-flow-core` kiểm tra tính hợp lệ của biến và kiểu dữ liệu trong AST.
3. **Nhóm 3: SMT-based Formal Verification (Z3 Solver)**
   * Chuyển đổi bất biến toán học và điều kiện hợp đồng thành bài toán thỏa mãn mệnh đề số học.
   * *Hiện thực:* Module `aegis-flow-smt` sinh công thức Z3 từ `@Invariant` và `@Rule`.
4. **Nhóm 4: Mutation & Coverage-Guided Fuzzing**
   * Sinh ngẫu nhiên các chuỗi gọi hàm và giá trị tham số đột biến để dò tìm trường hợp biên.
   * *Hiện thực:* Module `aegis-flow-fuzz` thực thi fuzzing trên các transition edges.
5. **Nhóm 5: End-to-End Verification Platform**
   * Nền tảng tích hợp toàn bộ các kỹ thuật trên vào một quy trình CI/CD hoàn chỉnh.
   * *Hiện thực:* **AegisFlow + Spring Boot Starter**.
