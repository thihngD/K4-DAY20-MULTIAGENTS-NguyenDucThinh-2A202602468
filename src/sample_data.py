"""Tạo cơ sở dữ liệu bán hàng mẫu (SQLite) để chạy hệ thống. Dữ liệu sinh ngẫu nhiên với seed cố định, không phải dữ liệu thật."""
import random
import sqlite3
from pathlib import Path

SCHEMA = ("sales(order_id TEXT, order_date TEXT, quarter TEXT, region TEXT, product TEXT, amount REAL) "
          "-- quarter is Q1..Q4 of 2024; region is North, South, East or West")
REGIONS = ["North", "South", "East", "West"]
PRODUCTS = ["Laptop", "Phone", "Tablet", "Monitor", "Keyboard"]


def create_sales_db(path: str | Path, rows: int = 200, seed: int = 42) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    rng = random.Random(seed)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE sales (order_id TEXT, order_date TEXT, quarter TEXT, region TEXT, "
                 "product TEXT, amount REAL)")
    data = []
    for i in range(1, rows + 1):
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        quarter = f"Q{(month - 1) // 3 + 1}"
        data.append((f"O-{i:04d}", f"2024-{month:02d}-{day:02d}", quarter, rng.choice(REGIONS),
                     rng.choice(PRODUCTS), round(rng.uniform(20, 800), 2)))
    conn.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?)", data)
    conn.commit()
    conn.close()
    return path
