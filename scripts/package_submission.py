"""Assemble the BTL submission folder required by the course guide:

    MSSV_HoTen_BTL/
        BaoCao_MSSV_HoTen.pdf
        source/     (analysis tool, specs, tests)
        results/    (logs, before/after tables, figures exported by core.pipeline)
        README.md   (how to reproduce everything)

    uv run python scripts/package_submission.py --mssv 2201xxxx --name "Nguyen Van A" --pdf report/main.pdf
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ITEMS = ["core", "gui", "scripts", "tests", "dataset/specs", "dataset/specs_excel", "main.py",
                "pyproject.toml", "uv.lock", "README.md"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "node_modules", ".DS_Store")

README = """# {folder}

Bài tập lớn CSE703093 — An toàn phần mềm. Báo cáo: `{pdf}`.

## Chạy lại toàn bộ kết quả

Yêu cầu: Python 3.11–3.13, [uv](https://docs.astral.sh/uv/), clang hoặc gcc (cho ASan/UBSan).

```bash
cd source
uv sync
uv run pytest
uv run python -m core.pipeline dataset/specs_excel/payment_gateway_v0_spec.xlsx \\
    --compare dataset/specs_excel/payment_gateway_v1_spec.xlsx --seed 1 --budget 2000
uv run python main.py
```

Lệnh pipeline ghi lại thư mục `results/payment_gateway_v0/` và `results/payment_gateway_v1/`
(đã nộp kèm trong `results/`). Seed cố định nên số liệu fuzzing tái tạo được; môi trường đã dùng
ghi trong `results/*/environment.txt`.

## Nội dung `results/<đặc tả>/`

| File | Nội dung |
|---|---|
| `report.md` | Toàn bộ kết quả theo chương |
| `before_after.md` | Bảng tổng hợp trước/sau (mã v0 → v1) |
| `comparison.md` | So sánh thiết kế đặc tả v0 → v1 (chỉ có ở v0) |
| `logs/` | ctl, bmc, scan, sanitizer_*.log, z3, fuzz.csv, ast.csv, tests.csv |
| `source/` | Mã sinh ra, bản v0 (có lỗi) và v1 (đã vá) |
| `figures/` | Sơ đồ Kripke (PNG và TikZ) |
"""


def ascii_name(text: str) -> str:
    text = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn" and ch.isalnum())


def copy_item(rel: str, dest_root: Path) -> None:
    src = ROOT / rel
    dst = dest_root / rel
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, ignore=IGNORE)
    else:
        shutil.copy2(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mssv", required=True)
    parser.add_argument("--name", required=True, help="Họ tên (có dấu cũng được)")
    parser.add_argument("--pdf", type=Path, default=ROOT / "report" / "main.pdf")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--rerun", action="store_true", help="Chạy lại pipeline trước khi đóng gói")
    args = parser.parse_args()

    folder = f"{args.mssv}_{ascii_name(args.name)}_BTL"
    target = args.out / folder
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    if args.rerun:
        subprocess.run(["uv", "run", "python", "-m", "core.pipeline",
                        "dataset/specs_excel/payment_gateway_v0_spec.xlsx",
                        "--compare", "dataset/specs_excel/payment_gateway_v1_spec.xlsx"], cwd=ROOT, check=True)

    for rel in SOURCE_ITEMS:
        copy_item(rel, target / "source")
    if (ROOT / "results").exists():
        shutil.copytree(ROOT / "results", target / "results", ignore=IGNORE)

    pdf_name = f"BaoCao_{args.mssv}_{ascii_name(args.name)}.pdf"
    if args.pdf.exists():
        shutil.copy2(args.pdf, target / pdf_name)
    else:
        print(f"CHÚ Ý: chưa có file báo cáo {args.pdf} — hãy biên dịch report/main.tex rồi chạy lại.")
    (target / "README.md").write_text(README.format(folder=folder, pdf=pdf_name), encoding="utf-8")

    archive = shutil.make_archive(str(target), "zip", root_dir=args.out, base_dir=folder)
    print(f"Đã tạo {target}/ và {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
