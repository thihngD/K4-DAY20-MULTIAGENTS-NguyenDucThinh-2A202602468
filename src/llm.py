"""Mô hình ngôn ngữ cho hệ thống multi-agent.

- `make_llm()`: ChatOpenAI thật, đọc OPENAI_API_KEY từ `.env` (không ghi khóa vào mã nguồn).
- `FakeLLM`: mô hình giả cho test. Trả lời theo từ khóa trong prompt, không gọi API, không tốn token.
"""
import os
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


def make_llm():
    """ChatOpenAI với timeout và số lần thử lại (một lần gọi treo không được làm treo cả hệ thống)."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=os.getenv("RQ2_MODEL", DEFAULT_MODEL), temperature=0,
                      timeout=60, max_retries=2)
