# Ngữ Pháp Biểu Thức Mini DSL (Specification)

AegisFlow tích hợp bộ Parser đệ quy xuống (Recursive Descent Parser) độc lập, không phụ thuộc vào bất kỳ thư viện ngoài nào.

---

## 1. Thứ Tự Ưu Tiên Toán Tử (Precedence Hierarchy)

Từ ưu tiên thấp nhất đến cao nhất:

| Thứ tự | Loại toán tử | Ký hiệu | Tính kết hợp |
| :---: | :--- | :---: | :---: |
| **1** | Logic kéo theo (Implication) | `==>` | Phải sang trái |
| **2** | Logic OR | `\|\|` | Trái sang phải |
| **3** | Logic AND | `&&` | Trái sang phải |
| **4** | So sánh bằng / khác | `==`, `!=` | Trái sang phải |
| **5** | So sánh thứ tự | `<`, `<=`, `>`, `>=` | Trái sang phải |
| **6** | Cộng, trừ | `+`, `-` | Trái sang phải |
| **7** | Nhân, chia, chia dư | `*`, `/`, `%` | Trái sang phải |
| **8** | Đảo dấu logic / số học | `!`, `-` (unary) | Phải sang trái |
| **9** | Lấy thuộc tính / Gọi hàm | `.`, `f(...)` | Trái sang phải |
| **10** | Nguyên tử & Dấu ngoặc | Số, boolean, biến, `(...)` | - |

---

## 2. Các Hàm Tích Hợp Sẵn (Built-in Functions)

* **`old(x)`**: Truy xuất giá trị của biến `x` ở trạng thái trước khi thực thi phương thức.
* **`abs(x)`**: Giá trị tuyệt đối của số $x$.
* **`min(a, b)`**: Giá trị nhỏ nhất giữa $a$ và $b$.
* **`max(a, b)`**: Giá trị lớn nhất giữa $a$ và $b$.

---

## 3. Cấu Trúc Abstract Syntax Tree (AST)

Tất cả các biểu thức được phân tích thành cây AST kế thừa từ interface `ExprNode`:

* `BinaryOpNode(ExprNode left, BinaryOp op, ExprNode right)`
* `UnaryOpNode(UnaryOp op, ExprNode expr)`
* `IdentifierNode(String name)`
* `LiteralNode(Object value)`
* `FunctionCallNode(String functionName, List<ExprNode> arguments)`
