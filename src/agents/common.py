"""Tiện ích chung cho worker: bỏ rào markdown khỏi câu trả lời của mô hình, tách JSON."""
import json
import re


def strip_fences(text: str) -> str:
    """Bỏ ```sql / ```python ... ``` nếu mô hình trả về dạng markdown."""
    m = re.search(r"```[a-zA-Z]*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def parse_json(text: str) -> dict:
    """Lấy object JSON đầu tiên trong câu trả lời. Ném ValueError nếu không có."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in model reply")
    return json.loads(m.group(0))
