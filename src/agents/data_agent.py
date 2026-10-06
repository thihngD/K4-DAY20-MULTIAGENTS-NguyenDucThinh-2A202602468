"""Data Agent: trả lời câu hỏi dữ liệu bằng một truy vấn SQL rồi tóm tắt kết quả."""
import json

from .base_worker import BaseWorker
from .common import strip_fences


class DataAgent(BaseWorker):
    system_prompt = (
        "You are a Data Analysis Specialist. Answer data questions with ONE SQLite SELECT query on the table "
        "sales, run it with query_database, then summarise the rows in one or two sentences with the key numbers."
    )

    def __init__(self, model, tools: list, schema: str = ""):
        super().__init__("data_agent", model, tools)
        self.schema = schema

    def process(self, task_content: str, parameters: dict | None = None) -> dict:
        sql = strip_fences(self._ask(
            f"[SQL] Write one SQLite SELECT statement that answers the task.\nTable schema:\n{self.schema}\n"
            f"Task: {task_content}\nParameters: {parameters or {}}\nReply with the SQL only."))
        out = self._execute_tool("query_database", {"query": sql})
        if out.get("status") != "success":
            return {"status": "error", "error": out.get("error", "query failed"), "query": sql}
        rows = out.get("data", [])[:20]
        summary = self._ask(
            f"[SUMMARY] Task: {task_content}\nQuery: {sql}\nRows (max 20): {json.dumps(rows, default=str)}\n"
            "Answer the task in one or two sentences, quoting the key numbers.")
        return {"status": "success", "result": summary, "query": sql, "rows": rows}
