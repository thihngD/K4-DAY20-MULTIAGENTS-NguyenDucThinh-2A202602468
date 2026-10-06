"""Mô hình ngôn ngữ cho hệ thống multi-agent.

- `make_llm()`: ChatOpenAI thật, đọc OPENAI_API_KEY từ `.env` (không ghi khóa vào mã nguồn).
- `FakeLLM`: mô hình giả cho test. Trả lời theo từ khóa trong prompt, không gọi API, không tốn token.
"""
import os
import threading
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class Reply:
    content: str


class FakeLLM:
    """Mô hình giả. `rules` là {từ khóa: câu trả lời}; prompt chứa từ khóa nào thì trả câu đó."""

    def __init__(self, rules: dict | None = None, default: str = "OK"):
        self.rules = rules or {}
        self.default = default
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> Reply:
        self.prompts.append(prompt)
        for key, answer in self.rules.items():
            if key in prompt:
                return Reply(answer)
        return Reply(self.default)


class CountingLLM:
    """Bọc một mô hình để đếm số lần gọi và token (dùng cho đo hiệu năng). An toàn khi nhiều thread cùng gọi."""

    def __init__(self, model):
        self.model = model
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._lock = threading.Lock()

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def invoke(self, prompt: str):
        reply = self.model.invoke(prompt)
        usage = getattr(reply, "usage_metadata", None) or {}
        with self._lock:
            self.calls += 1
            self.input_tokens += usage.get("input_tokens", 0)
            self.output_tokens += usage.get("output_tokens", 0)
        return reply


DEMO_RULES = {   # luật cho FakeLLM khi chạy script demo/đo lường mà không gọi API
    "[SQL]": "SELECT region, ROUND(SUM(amount), 2) AS revenue FROM sales GROUP BY region",
    "[SUMMARY]": "Revenue by region computed from the sales table.",
    "[CODE]": ("import sqlite3\nimport matplotlib.pyplot as plt\n"
               "rows = sqlite3.connect(DB_URI, uri=True).execute('SELECT region, SUM(amount) FROM sales "
               "GROUP BY region').fetchall()\nplt.bar([r[0] for r in rows], [r[1] for r in rows])\n"
               "plt.savefig(OUTPUT_DIR + '/chart.png')\nprint(len(rows), 'regions')"),
    "[EVAL]": '{"scores": {"accuracy": 90, "completeness": 85, "clarity": 80, "performance": 88}, '
              '"feedback": "Clear.", "issues": [], "suggestions": []}',
}


def make_llm():
    """ChatOpenAI với timeout và số lần thử lại (một lần gọi treo không được làm treo cả hệ thống)."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=os.getenv("RQ2_MODEL", DEFAULT_MODEL), temperature=0,
                      timeout=60, max_retries=2)
