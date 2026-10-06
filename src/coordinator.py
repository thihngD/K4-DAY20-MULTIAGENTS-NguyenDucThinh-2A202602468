"""Coordinator: nhận yêu cầu, phân tích, định tuyến đến worker, chờ kết quả, tổng hợp và trả lời.

Luồng: handle_request -> parse_request -> route_task -> execute_tasks_with_retry -> aggregate_results.
Coordinator không gọi mô hình để phân loại (parse_request dùng từ khóa), nên định tuyến nhanh và không tốn token.
"""
import asyncio
import re
import time
from datetime import datetime, timezone

from .base_agent import BaseAgent

# Loại tác vụ -> worker phụ trách. "complex" gồm dữ liệu và code (thêm evaluator nếu có yêu cầu đánh giá).
TASK_ROUTES = {
    "data_analysis": ["data_agent"],
    "code_generation": ["code_agent"],
    "evaluation": ["evaluator_agent"],
    "complex": ["data_agent", "code_agent"],
}
# Tên kết quả trong phản hồi cuối cho từng worker.
RESULT_KEYS = {"data_agent": "data", "code_agent": "code", "evaluator_agent": "evaluation"}

DATA_WORDS = r"revenue|sales|orders?|doanh thu|tổng|total|query|sql|analy[sz]e|phân tích|quarter|\bq[1-4]\b|region"
CODE_WORDS = r"chart|plot|graph|biểu đồ|code|script|python|csv file|visuali[sz]ation|create (a )?(file|report)"
EVAL_WORDS = r"evaluat|đánh giá|score|chấm|quality|review"
URGENT_WORDS = r"urgent|asap|gấp|khẩn"

MAX_TASKS = 5           # trên mức này coi là quá nhiều tác vụ (resource exhaustion)


class CoordinatorException(Exception):
    pass


class Coordinator(BaseAgent):
    def __init__(self, model=None, workers=None, timeout: float = 60, max_retries: int = 2):
        super().__init__("coordinator", model)
        # worker có thể là agent trực tiếp hoặc QueueWorkerProxy (gọi qua message queue): cùng giao diện process_async
        self.workers = {agent.name: agent for agent in (workers or [])}
        self.timeout = timeout
        self.max_retries = max_retries
        self.active_tasks: dict[str, float] = {}      # id tác vụ -> thời điểm bắt đầu

    # ---- 1. Phân tích yêu cầu ----------------------------------------------------------------
    def parse_request(self, user_input: str) -> dict:
        """Trả về {task_type, parameters, priority} bằng từ khóa. Ném ValueError nếu đầu vào không hợp lệ."""
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("empty or non-text request")
        text = user_input.lower()
        has_data = re.search(DATA_WORDS, text) is not None
        has_code = re.search(CODE_WORDS, text) is not None
        has_eval = re.search(EVAL_WORDS, text) is not None
        if has_data and has_code or (has_data and has_eval):
            task_type = "complex"
        elif has_code:
            task_type = "code_generation"
        elif has_eval:
            task_type = "evaluation"
        else:
            task_type = "data_analysis"
        quarter = re.search(r"\bq([1-4])\b", text)
        parameters = {
            "quarter": f"Q{quarter.group(1)}" if quarter else None,
            "wants_chart": bool(re.search(r"chart|plot|graph|biểu đồ|visuali", text)),
            "wants_evaluation": has_eval,
        }
        priority = "high" if re.search(URGENT_WORDS, text) else "normal"
        self.logger.info("parsed task_type=%s parameters=%s priority=%s", task_type, parameters, priority)
        return {"task_type": task_type, "parameters": parameters, "priority": priority}

    # ---- 2. Định tuyến -------------------------------------------------------------------------
    def route_task(self, task_type: str, content: str) -> list[str]:
        """Danh sách tên worker cần gọi. Với "complex", thêm evaluator khi yêu cầu có đánh giá."""
        if task_type not in TASK_ROUTES:
            raise ValueError(f"unknown task type: {task_type}")
        names = list(TASK_ROUTES[task_type])
        if task_type == "complex" and re.search(EVAL_WORDS, str(content).lower()):
            names.append("evaluator_agent")
        return [n for n in names if n in self.workers] or names

    # ---- 3. Thực thi ---------------------------------------------------------------------------
    async def _call_worker(self, task: dict, timeout: float) -> dict:
        worker = self.workers.get(task["worker"])
        base = {"id": task["id"], "worker": task["worker"], "type": RESULT_KEYS.get(task["worker"], task["worker"])}
        if worker is None:
            return {**base, "status": "error", "error": f"unknown worker {task['worker']}"}
        started = time.time()
        self.active_tasks[task["id"]] = started
        self.logger.info("start task=%s worker=%s", task["id"], task["worker"])
        try:
            result = await asyncio.wait_for(worker.process_async(task["content"], task.get("parameters")), timeout)
            status = result.get("status", "success") if isinstance(result, dict) else "success"
            payload = result.get("result") if isinstance(result, dict) and "result" in result else result
            out = {**base, "status": "success" if status == "success" else "error", "result": payload}
            if isinstance(result, dict) and result.get("error"):
                out["error"] = result["error"]
        except asyncio.TimeoutError:
            out = {**base, "status": "timeout", "error": f"no answer within {timeout}s"}
        except Exception as exc:  # noqa: BLE001 - lỗi của worker không làm dừng coordinator
            out = {**base, "status": "error", "error": f"{type(exc).__name__}: {exc}"}
        finally:
            self.active_tasks.pop(task["id"], None)
        self.logger.info("end task=%s status=%s duration=%.2fs", task["id"], out["status"], time.time() - started)
        return out

    async def execute_tasks(self, tasks: list[dict], timeout: float | None = None) -> list[dict]:
        """Gửi các tác vụ song song và chờ kết quả, mỗi tác vụ có timeout riêng."""
        timeout = self.timeout if timeout is None else timeout
        return list(await asyncio.gather(*(self._call_worker(t, timeout) for t in tasks)))

    async def execute_tasks_with_retry(self, tasks: list[dict], max_retries: int | None = None,
                                       timeout: float | None = None) -> list[dict]:
        """Thử lại chỉ các tác vụ bị timeout hoặc lỗi. Hết lượt thử thì trả về kết quả từng phần (không ném lỗi)."""
        attempts = (self.max_retries if max_retries is None else max_retries) + 1
        pending = list(tasks)
        done: dict[str, dict] = {}
        for attempt in range(1, attempts + 1):
            results = await self.execute_tasks(pending, timeout)
            for r in results:
                done[r["id"]] = r
            pending = [t for t in pending if done[t["id"]]["status"] != "success"]
            if not pending:
                break
            self.logger.warning("attempt %d/%d: %d task(s) failed, retrying", attempt, attempts, len(pending))
        return [done[t["id"]] for t in tasks]

    # ---- 4. Tổng hợp -----------------------------------------------------------------------
    def aggregate_results(self, results: list[dict]) -> dict:
        """Ghép kết quả theo worker. status: success (tất cả đạt), partial (một phần), error (không có gì)."""
        out = {"status": "success", "data": None, "code": None, "evaluation": None, "errors": []}
        ok = 0
        for r in results:
            if r["status"] == "success":
                ok += 1
                out[r["type"]] = r.get("result")
            else:
                out["errors"].append({"worker": r["worker"], "status": r["status"], "error": r.get("error")})
        if ok == 0:
            out["status"] = "error"
        elif ok < len(results):
            out["status"] = "partial"
        out["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return out

    # ---- Điểm vào -----------------------------------------------------------------------------
    async def handle_request(self, request: str) -> dict:
        try:
            parsed = self.parse_request(request)
        except ValueError as exc:
            self.logger.error("invalid input: %s", exc)
            return {"status": "error", "errors": [{"error": f"invalid input: {exc}"}], "data": None, "code": None,
                    "evaluation": None}
        names = self.route_task(parsed["task_type"], request)
        if len(names) > MAX_TASKS:
            return {"status": "error", "errors": [{"error": "too many tasks"}], "data": None, "code": None,
                    "evaluation": None}
        # Giai đoạn 1: worker tạo kết quả (dữ liệu, code). Giai đoạn 2: evaluator chấm kết quả của giai đoạn 1.
        producers = [n for n in names if n != "evaluator_agent"]
        evaluators = [n for n in names if n == "evaluator_agent"]
        tasks = [{"id": f"{i}-{n}", "worker": n, "content": request, "parameters": parsed["parameters"]}
                 for i, n in enumerate(producers, start=1)]
        results = await self.execute_tasks_with_retry(tasks) if tasks else []
        if evaluators:
            artifacts = {r["type"]: r.get("result") for r in results if r["status"] == "success"}
            content = f"{request}\n\nWORK TO EVALUATE:\n{artifacts}" if artifacts else request
            eval_tasks = [{"id": f"eval-{n}", "worker": n, "content": content, "parameters": parsed["parameters"]}
                          for n in evaluators]
            results += await self.execute_tasks_with_retry(eval_tasks)
        return {**self.aggregate_results(results), "task_type": parsed["task_type"], "priority": parsed["priority"]}
