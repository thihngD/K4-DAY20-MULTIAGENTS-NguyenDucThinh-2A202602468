"""Code Agent: viết script Python, chạy thử trong REPL có sandbox, sửa một lần nếu lỗi, rồi trả về code và kết quả."""
from .base_worker import BaseWorker
from .common import strip_fences

ALLOWED_IMPORTS = "sqlite3, csv, json, math, statistics, datetime, collections, re, matplotlib.pyplot"


class CodeAgent(BaseWorker):
    system_prompt = (
        "You are a Code Generation Specialist. Write a short self-contained Python script for the task, "
        "test it with python_repl, and return the working code and its output. Always test before answering."
    )
    max_attempts = 2          # lần đầu + một lần sửa theo thông báo lỗi

    def __init__(self, model, tools: list, db_path: str, output_dir: str):
        super().__init__("code_agent", model, tools)
        self.db_path = db_path
        self.output_dir = output_dir

    def process(self, task_content: str, parameters: dict | None = None) -> dict:
        # URI chỉ đọc: script không thể ghi vào cơ sở dữ liệu
        sandbox_vars = {"DB_URI": f"file:{self.db_path}?mode=ro", "OUTPUT_DIR": self.output_dir}
        prompt = (f"[CODE] Write a Python 3 script for the task.\nTask: {task_content}\nParameters: {parameters or {}}\n"
                  f"Variables already defined: DB_URI (read-only SQLite URI of table sales; connect with "
                  f"sqlite3.connect(DB_URI, uri=True)), OUTPUT_DIR (folder for files).\n"
                  f"Allowed imports: {ALLOWED_IMPORTS}. Save any chart as OUTPUT_DIR + '/chart.png' with plt.savefig. "
                  "Print the final answer. Reply with code only.")
        code = strip_fences(self._ask(prompt))
        run = {"status": "error", "error": "not run"}
        for attempt in range(1, self.max_attempts + 1):
            run = self._execute_tool("python_repl", {"code": code, "variables": sandbox_vars})
            if run.get("status") == "success":
                break
            self.logger.warning("attempt %d failed: %s", attempt, run.get("error"))
            if attempt < self.max_attempts:
                code = strip_fences(self._ask(
                    f"[CODE] The script failed with: {run.get('error')}\nFix it. Previous script:\n{code}\n"
                    f"Allowed imports: {ALLOWED_IMPORTS}. Reply with code only."))
        if run.get("status") != "success":
            return {"status": "error", "error": run.get("error", "code failed"), "code": code}
        return {"status": "success",
                "result": f"Code:\n{code}\n\nOutput:\n{run.get('stdout', '').strip()}"}
