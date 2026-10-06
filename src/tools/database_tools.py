"""Công cụ truy vấn cơ sở dữ liệu cho Data Agent.

An toàn theo ba lớp: (1) chỉ cho một câu SELECT, chặn từ khóa ghi; (2) kết nối SQLite chỉ đọc (mode=ro);
(3) tự thêm LIMIT để kết quả không quá lớn.
"""
import re
import sqlite3
from pathlib import Path

from .base_tool import BaseTool

FORBIDDEN = re.compile(r"\b(drop|delete|truncate|alter|insert|update|create|attach|pragma|replace|vacuum)\b", re.I)
DEFAULT_LIMIT = 1000


class QueryDatabaseTool(BaseTool):
    def __init__(self, db_path: str | Path):
        super().__init__("query_database", "Run one read-only SELECT query on the sales database (SQLite).")
        self.db_path = Path(db_path)

    def validate_input(self, input_dict: dict) -> None:
        query = input_dict.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        body = query.strip().rstrip(";").strip()
        if ";" in body:
            raise ValueError("only one statement is allowed")
        if not re.match(r"(?is)^(select|with)\b", body) or not re.search(r"(?i)\bselect\b", body):
            raise ValueError("only SELECT queries (optionally WITH ... SELECT) are allowed")
        if FORBIDDEN.search(body):
            raise ValueError("query contains a forbidden keyword")

    def invoke(self, input_dict: dict) -> dict:
        self.validate_input(input_dict)
        query = input_dict["query"].strip().rstrip(";")
        if not re.search(r"(?i)\blimit\b", query):
            query = f"{query} LIMIT {DEFAULT_LIMIT}"
        try:
            conn = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True)
            try:
                cursor = conn.execute(query)
                columns = [c[0] for c in cursor.description or []]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            finally:
                conn.close()
        except sqlite3.Error as exc:
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        return {"status": "success", "rows": len(rows), "columns": columns, "data": rows}
