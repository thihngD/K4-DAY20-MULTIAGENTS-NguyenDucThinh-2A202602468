"""Phần 3 - Worker agents, message queue và tích hợp coordinator ↔ worker qua queue (offline)."""
import asyncio

import pytest

from src.agents import CodeAgent, DataAgent, EvaluatorAgent
from src.agents.base_worker import BaseWorker
from src.communication import MessageQueue, QueueWorkerProxy
from src.coordinator import Coordinator
from src.llm import FakeLLM
from src.tools.base_tool import BaseTool


class StubTool(BaseTool):
    """Tool giả với hành vi xác định, để test worker mà không cần cơ sở dữ liệu hay REPL thật."""

    def __init__(self, name, handler):
        super().__init__(name, f"stub {name}")
        self.handler = handler

    def validate_input(self, input_dict):
        return None

    def invoke(self, input_dict):
        return self.handler(input_dict)


class SequenceLLM:
    """Trả lời lần lượt theo danh sách (dùng khi cần câu trả lời khác nhau cho từng lần gọi)."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        from src.llm import Reply
        return Reply(self.replies.pop(0) if len(self.replies) > 1 else self.replies[0])


def ok_query(_):
    return {"status": "success", "data": [{"revenue": 1234.5}]}


def test_base_worker_builds_prompt_and_rejects_unknown_tool():
    worker = BaseWorker("w", FakeLLM(), [StubTool("t", ok_query)])
    assert "Task: hello" in worker._build_prompt("hello", {"k": 1})
    with pytest.raises(ValueError):
        worker._execute_tool("missing", {})


def test_data_agent_runs_query_then_summarises():
    model = FakeLLM({"[SQL]": "SELECT SUM(amount) AS revenue FROM sales WHERE quarter = 'Q3';",
                     "[SUMMARY]": "Q3 revenue is 1234.5."})
    agent = DataAgent(model, [StubTool("query_database", ok_query)], schema="sales(amount REAL)")
    out = agent.process("What was Q3 revenue?", {"quarter": "Q3"})
    assert out["status"] == "success" and "1234.5" in out["result"]
    assert out["query"].startswith("SELECT") and out["rows"] == [{"revenue": 1234.5}]


def test_data_agent_reports_query_error():
    model = FakeLLM({"[SQL]": "DROP TABLE sales;"})
    agent = DataAgent(model, [StubTool("query_database", lambda _: {"status": "error", "error": "blocked"})])
    out = agent.process("delete everything")
    assert out["status"] == "error" and out["error"] == "blocked"


def test_code_agent_fixes_failed_script_once():
    runs = []

    def repl(inp):
        runs.append(inp["code"])
        if len(runs) == 1:
            return {"status": "error", "error": "NameError: x"}
        return {"status": "success", "stdout": "chart saved\n"}

    model = SequenceLLM(["print(x)", "chart = 1\nprint('chart saved')"])
    agent = CodeAgent(model, [StubTool("python_repl", repl)], db_path="db.sqlite", output_dir="outputs")
    out = agent.process("create a chart")
    assert out["status"] == "success" and "chart saved" in out["result"] and "chart" in out["result"]
    assert len(runs) == 2 and "NameError" in model.prompts[1]          # lần sửa có thông báo lỗi


def test_evaluator_returns_weighted_score():
    model = FakeLLM({"[EVAL]": '{"scores": {"accuracy": 90, "completeness": 80, "clarity": 70, "performance": 60},'
                               ' "feedback": "good", "issues": [], "suggestions": []}'})
    tools = [StubTool("validation", lambda _: {"status": "success"}),
             StubTool("scoring", lambda i: {"weighted_score": 82.0, "grade": "B"})]
    out = EvaluatorAgent(model, tools).process("evaluate the answer")
    assert out["status"] == "success" and "score 82.0/100" in out["result"] and out["scores"]["grade"] == "B"


def test_evaluator_rejects_non_json_reply():
    agent = EvaluatorAgent(FakeLLM({"[EVAL]": "looks fine to me"}), [])
    out = asyncio.run(agent.process_async("evaluate this"))
    assert out["status"] == "error" and "JSON" in out["error"]


def test_message_queue_send_receive_and_log():
    async def scenario():
        q = MessageQueue()
        q.register_agent("a")
        q.register_agent("b")
        mid = await q.send_message("a", "b", {"type": "ping"})
        msg = await q.receive_message("b", timeout=1)
        assert msg["id"] == mid and msg["from"] == "a" and msg["type"] == "ping" and msg["timestamp"]
        assert len(q.get_message_log("a")) == 1
        with pytest.raises(ValueError):
            await q.send_message("a", "nobody", {})
        with pytest.raises(TimeoutError):
            await q.receive_message("b", timeout=0.05)
    asyncio.run(scenario())


def test_coordinator_talks_to_worker_through_queue():
    async def scenario():
        q = MessageQueue()
        worker = DataAgent(FakeLLM({"[SQL]": "SELECT 1;", "[SUMMARY]": "Revenue is 1234.5."}),
                           [StubTool("query_database", ok_query)])
        q.register_agent(worker.name)
        server = asyncio.create_task(worker.serve(q, poll_timeout=0.05))
        coord = Coordinator(workers=[QueueWorkerProxy("data_agent", q)], timeout=5, max_retries=0)
        response = await coord.handle_request("Analyze sales data")
        server.cancel()
        assert response["status"] == "success" and "1234.5" in response["data"]
        kinds = [m["type"] for m in q.get_message_log()]
        assert kinds == ["task_request", "task_result"]
    asyncio.run(scenario())


def test_worker_error_travels_back_through_queue():
    async def scenario():
        q = MessageQueue()
        worker = DataAgent(FakeLLM({"[SQL]": "DROP TABLE sales;"}),
                           [StubTool("query_database", lambda _: {"status": "error", "error": "blocked"})])
        q.register_agent(worker.name)
        server = asyncio.create_task(worker.serve(q, poll_timeout=0.05))
        coord = Coordinator(workers=[QueueWorkerProxy("data_agent", q)], timeout=5, max_retries=0)
        response = await coord.handle_request("Analyze sales data")
        server.cancel()
        assert response["status"] == "error" and response["errors"][0]["error"] == "blocked"
    asyncio.run(scenario())


def test_evaluator_runs_after_producers_with_their_output():
    async def scenario():
        model = FakeLLM({"[SQL]": "SELECT 1;", "[SUMMARY]": "Revenue is 1234.5.",
                         "[EVAL]": '{"scores": {"accuracy": 90, "completeness": 90, "clarity": 90, "performance": 90},'
                                   ' "feedback": "ok", "issues": [], "suggestions": []}'})
        data = DataAgent(model, [StubTool("query_database", ok_query)])
        evaluator = EvaluatorAgent(model, [StubTool("validation", lambda _: {"status": "success"}),
                                           StubTool("scoring", lambda i: {"weighted_score": 90.0, "grade": "A"})])
        coord = Coordinator(workers=[data, evaluator], timeout=5, max_retries=0)
        response = await coord.handle_request("Analyze revenue and evaluate the result")
        eval_prompt = [p for p in model.prompts if "[EVAL]" in p][0]
        assert "WORK TO EVALUATE" in eval_prompt and "1234.5" in eval_prompt
        assert response["status"] == "success" and "score 90.0/100" in response["evaluation"]
    asyncio.run(scenario())
