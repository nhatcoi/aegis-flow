# Payment Proof Lab — Kiểm chứng đặc tả hệ thống thanh toán

Bài tập lớn **CSE703093 — An toàn phần mềm** (Chủ đề 5: quy trình end-to-end tích hợp 4 chương).

Từ một đặc tả yêu cầu (Excel 10 sheet theo template của học phần, hoặc JSON), công cụ chạy toàn bộ
chuỗi kiểm chứng và **xuất bằng chứng** cho mọi kết luận:

| Chương | Kỹ thuật | Module |
|---|---|---|
| 1 | Cấu trúc Kripke, model checking CTL (parser đầy đủ, phản ví dụ, lasso cho `AF`), deadlock, mutual exclusion | `core/ctl.py`, `core/kripke.py` |
| 3 | Bounded Model Checking bằng Z3, completeness threshold | `core/bmc.py` |
| 2 | Sinh mã C/Python v0 (có lỗi) + v1 (đã vá); static scanner theo luồng; ASan/UBSan chạy thật; cppcheck (nếu có) | `core/codegen.py`, `core/c_analyzer.py`, `core/toolchain.py` |
| 3 | Trích AST, McCabe V(G); SMT với Z3: miền int32, bit-vector wrap-around, chứng minh bản vá (UNSAT) | `core/static_ast.py`, `core/arithmetic_z3.py` |
| 4 | Fuzzing black-box, coverage-guided (hill climbing), concolic (Z3) — cùng ngân sách, seed cố định | `core/fuzzing.py` |
| — | Gộp CWE/CVE **chỉ từ bằng chứng công cụ**, trạng thái v0/v1, đánh giá test case PASS/FAIL | `core/cwe_analyzer.py`, `core/pipeline.py` |

## Cài đặt

Yêu cầu Python 3.11–3.13, [uv](https://docs.astral.sh/uv/), và clang hoặc gcc để chạy ASan/UBSan
(thiếu trình biên dịch thì bước này được bỏ qua và ghi rõ trong báo cáo).

```bash
uv sync
```

## Chạy

Pipeline đầy đủ cho đặc tả thanh toán, kèm so sánh thiết kế v0 → v1:

```bash
uv run python -m core.pipeline dataset/specs_excel/payment_gateway_v0_spec.xlsx --compare dataset/specs_excel/payment_gateway_v1_spec.xlsx --seed 1 --budget 2000
```

Giao diện desktop (chạy cùng pipeline, xem đồ thị/phản ví dụ, xuất kết quả):

```bash
uv run python main.py
```

Kiểm thử tự động:

```bash
uv run pytest
```

Sinh lại cặp đặc tả thanh toán v0/v1:

```bash
uv run python scripts/build_payment_specs.py
```

Đóng gói bài nộp `MSSV_HoTen_BTL/` (báo cáo PDF, source, results, README):

```bash
uv run python scripts/package_submission.py --mssv 2201xxxx --name "Họ Tên" --pdf report/main.pdf
```

## Kết quả xuất ra: `results/<đặc tả>/`

| File | Nội dung |
|---|---|
| `report.md` | Kết quả theo chương, phân tích từng CWE theo 5 mục (vị trí, nguyên nhân, bằng chứng, cách vá, bằng chứng đã vá) |
| `before_after.md` | Bảng tổng hợp trước/sau |
| `comparison.md` | So sánh thiết kế đặc tả v0 → v1 (khi dùng `--compare`) |
| `summary.json` | Toàn bộ số liệu dạng máy đọc được |
| `environment.txt` | Hệ điều hành, phiên bản Python/Z3/clang, seed, ngân sách |
| `logs/` | `ctl.txt`, `bmc.txt`, `scan.txt`, `sanitizer_*.log`, `cppcheck.txt`, `z3.txt`, `ast.csv`, `fuzz.csv`, `fuzz_events.txt`, `tests.csv` |
| `source/` | Mã sinh ra `*_v0` và `*_v1` |
| `figures/` | Sơ đồ Kripke `kripke.png` và `kripke.tex` (TikZ, tô đỏ phản ví dụ) |

## Cấu trúc thư mục

```text
core/        pipeline phân tích (xem bảng trên)
gui/         giao diện PyQt6 (qt_app.py, theme.py)
dataset/     đặc tả mẫu JSON/Excel — định dạng: dataset/specs/FORMAT.md, dataset/specs_excel/FORMAT_EXCEL.md
scripts/     sinh đặc tả thanh toán, đóng gói bài nộp
results/     bằng chứng đã xuất cho đặc tả thanh toán v0/v1
report/      khung báo cáo LaTeX (biên dịch bằng XeLaTeX)
tests/       pytest cho pipeline; tests/web/ cho backend web
backend/, frontend/, specs/   bản web (FastAPI + React) thử nghiệm trước đây, không thuộc pipeline chính
```

## Giới hạn đã biết

- Static scanner dựa trên mẫu, trong phạm vi một hàm, không phân tích alias: không sound, không complete.
  Kết quả của nó được đối chiếu với ASan.
- LeakSanitizer không hỗ trợ macOS: CWE-401 trên macOS chỉ có bằng chứng tĩnh (chạy trên Linux để có log leak).
- CTL/BMC chứng minh tính chất của **mô hình trạng thái**, không phải của mã thanh toán viết tay.
- Concolic chỉ mô hình hóa tập con cú pháp Python của mã sinh ra; hàm gọi thư viện ngoài được ghi nhận là
  "không mô hình hóa được".
