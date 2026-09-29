# Báo cáo BTL — khung LaTeX

Khung theo `BTL_02_HuongDan_BaoCao.pdf` (7 phần, 10–20 trang). Phần phân tích lỗ hổng
dùng cấu trúc 5 mục con + bảng before/after của `report_guide.pdf`.

## Biên dịch

**Overleaf**: upload cả thư mục `report/` → Menu → Compiler: **XeLaTeX** → Recompile.

**Máy local** (cần cài một trong hai):

```bash
brew install tectonic
```

```bash
cd report && tectonic main.tex
```

## Cấu trúc

| File | Nội dung |
|---|---|
| `main.tex` | Thông tin đề tài (sửa họ tên, MSSV, lớp ở đầu file) |
| `preamble.tex` | Font, style code, macro `\TODO`, `\cwe`, `\code` |
| `sections/00-bia.tex` … `06-ket-luan.tex` | 7 phần chính |
| `sections/99-phu-luc.tex` | Hướng dẫn chạy lại, log, khai báo dùng AI |
| `figures/*.tex` | Hình TikZ: kiến trúc, pipeline, Kripke |
| `refs.bib` | Tài liệu tham khảo |

## Trước khi nộp

- Tìm và xóa hết `\TODO{...}` (hiển thị chữ đỏ trong PDF).
- Số liệu trong chương 4 phải khớp với log trong `results/payment/`.
- Mọi đoạn mã trích ghi rõ file, dòng, phiên bản v0/v1.
