"""Data Agent: trả lời câu hỏi dữ liệu bằng một truy vấn SQL rồi tóm tắt kết quả."""
import json

from .base_worker import BaseWorker
from .common import strip_fences


class DataAgent(BaseWorker):
    system_prompt = (
        "You are a Data Analysis Specialist. Answer data questions with ONE SQLite SELECT query on the table "
        "sales, run it with query_database, then summarise the rows in one or two sentences with the key numbers."
    )

    max_attempts = 2

    def __init__(self, model, tools: list, schema: str = ""):
        super().__init__("data_agent", model, tools)
        self.schema = schema

    def process(self, task_content: str, parameters: dict | None = None) -> dict:
        note = ""
        for attempt in range(1, self.max_attempts + 1):
            sql = strip_fences(self._ask(
                f"{self.system_prompt}\n\n[SQL] Write one read-only SQLite query (SELECT, or WITH ... SELECT) "
                f"that answers the task.\nTable schema:\n{self.schema}\n"
                f"Task: {task_content}\nParameters: {parameters or {}}{note}\nReply with the SQL only."))
            try:
                out = self._execute_tool("query_database", {"query": sql})
            except ValueError as exc:             # câu lệnh bị chặn: thử lại có kèm lý do
                out = {"status": "error", "error": str(exc)}
            if out.get("status") == "success":
                break
            note = f"\nThe previous query was rejected: {out.get('error')}. Write a valid SELECT query."
        if out.get("status") != "success":
            return {"status": "error", "error": out.get("error", "query failed"), "query": sql}
        rows = out.get("data", [])[:20]
        summary = self._ask(
            f"[SUMMARY] Task: {task_content}\nQuery: {sql}\nRows (max 20): {json.dumps(rows, default=str)}\n"
            "Answer the task in one or two sentences, quoting the key numbers.")
        return {"status": "success", "result": summary, "query": sql, "rows": rows}
