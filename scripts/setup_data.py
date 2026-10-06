"""Tạo cơ sở dữ liệu bán hàng mẫu: data/sales.db (dữ liệu ngẫu nhiên, seed cố định).

    python scripts/setup_data.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sample_data import create_sales_db  # noqa: E402

if __name__ == "__main__":
    path = create_sales_db(Path(__file__).resolve().parents[1] / "data" / "sales.db")
    print(f"created {path}")
