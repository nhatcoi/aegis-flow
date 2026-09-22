# Spec Verification Lab & Payment Software Security

Hệ thống kiểm chứng đặc tả hình thức (Formal Specification), mô hình Kripke, phân tích ràng buộc số học với Z3 SMT Solver, sinh mã Python an toàn và kiểm tra lỗ hổng bảo mật CWE / CVE.

---

## 🎯 Tính năng chính

1. **Nạp & Quản lý Đặc tả (Specification Management)**:
   - Hỗ trợ định dạng JSON và Microsoft Excel (`.xlsx`).
   - Kiểm tra tính hợp lệ về cấu trúc trạng thái, biến số học, tiền điều kiện/hậu điều kiện.

2. **Kiểm chứng Mô hình Kripke (Kripke Model Checking)**:
   - Xây dựng đồ thị Kripke Structure từ tập trạng thái và chuyển trạng thái (*transitions*).
   - Kiểm tra Deadlock, tính đến được (*Reachability*), và tính tất định (*Determinism*).
   - Trực quan hóa đồ thị trạng thái tương tác với Matplotlib / NetworkX.

3. **Kiểm chứng Ràng buộc với Z3 SMT Solver (Arithmetic & Bounds Checking)**:
   - Bounded verification cho các biến số học, số dư, hạn mức thanh toán.
   - Phát hiện tràn số, giá trị âm, hoặc vi phạm bất biến (*invariant violation*).

4. **Sinh mã Tự động (Automated Code Generation)**:
   - Sinh mã Python sạch kèm runtime checks và assertion guardrails từ đặc tả.

5. **Phân tích An toàn & Lỗ hổng CWE / CVE (Security Audit)**:
   - Đối chiếu quy trình với các mẫu lỗ hổng CWE phổ biến:
     - CWE-20: Improper Input Validation
     - CWE-287: Improper Authentication
     - CWE-362: Race Condition / Concurrency
     - CWE-400: Uncontrolled Resource Consumption
     - CWE-799: Improper Control of Generation of Frequent Requests (Rate Limiting)
     - CWE-840: Business Logic Errors
   - Xuất báo cáo kiểm thử chi tiết dạng Markdown.

---

## 🛠️ Cài đặt & Khởi chạy

### Yêu cầu
- Python >= 3.11
- Trình quản lý gói `uv` (hoặc `pip`)

### Cài đặt môi trường
```bash
# Cài đặt dependencies với uv
uv sync
```

### Chạy ứng dụng giao diện (Desktop GUI)
```bash
uv run python main.py
# hoặc
python main.py
```

### Chạy kiểm thử tự động (Unit Tests)
```bash
uv run pytest
```

---

## 📁 Cấu trúc thư mục

```text
├── backend/            # API backend (FastAPI) & server logic
├── core/               # Thư viện lõi xử lý logic
│   ├── spec_loader.py    # Nạp spec từ JSON / Excel
│   ├── kripke.py         # Xây dựng mô hình & kiểm chứng Kripke
│   ├── arithmetic_z3.py  # SMT Solver Z3 kiểm chứng số học
│   ├── codegen.py        # Sinh mã Python từ đặc tả
│   ├── cwe_analyzer.py   # Phân tích đối chiếu lỗ hổng CWE
│   └── reporter.py       # Xuất báo cáo Markdown
├── dataset/            # Bộ dataset đặc tả mẫu (JSON & Excel)
├── gui/                # Desktop UI (Tkinter / Matplotlib)
├── frontend/           # Web UI (React + Vite)
├── tests/              # Bộ test suites
├── main.py             # Entrypoint khởi động Desktop GUI
└── pyproject.toml      # Cấu hình dự án & dependencies
```
