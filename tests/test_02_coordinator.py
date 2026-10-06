"""Phần 2 - Coordinator (offline, worker giả, không tốn token)."""
import asyncio

import pytest

from src.coordinator import Coordinator, MAX_TASKS


class MockWorker:
    """Worker giả: trả về `result` sau `delay` giây, hoặc ném `error`."""

    def __init__(self, name, result="mock answer", delay=0.0, error=None, fail_times=0):
        self.name = name
        self.result = result
        self.delay = delay
        self.error = error
        self.fail_times = fail_times
        self.calls = 0

    async def process_async(self, task_content, parameters=None):
        self.calls += 1
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        if self.calls <= self.fail_times:
            raise RuntimeError("temporary failure")
        return {"status": "success", "result": f"{self.name}: {self.result}"}


def make_coordinator(*workers, **kwargs):
    return Coordinator(model=None, workers=list(workers), **kwargs)


def test_coordinator_init():
    coord = make_coordinator(MockWorker("data_agent"), MockWorker("code_agent"), timeout=5)
    assert set(coord.workers) == {"data_agent", "code_agent"}
    assert coord.timeout == 5 and coord.active_tasks == {}


def test_parse_request_classifies_tasks():
    coord = make_coordinator()
    parsed = coord.parse_request("Analyze sales data")
    assert parsed["task_type"] == "data_analysis"
    assert parsed["parameters"] is not None
    assert coord.parse_request("Write Python script to read CSV")["task_type"] == "code_generation"
    assert coord.parse_request("Calculate revenue and create chart")["task_type"] == "complex"
    assert coord.parse_request("Evaluate this report")["task_type"] == "evaluation"
    assert coord.parse_request("What was Q3 revenue?")["parameters"]["quarter"] == "Q3"
    assert coord.parse_request("Analyze sales ASAP")["priority"] == "high"


@pytest.mark.parametrize("bad", ["", "   ", None, 42])
def test_parse_request_rejects_invalid_input(bad):
    with pytest.raises(ValueError):
        make_coordinator().parse_request(bad)


def test_route_task():
    coord = make_coordinator(MockWorker("data_agent"), MockWorker("code_agent"), MockWorker("evaluator_agent"))
    assert coord.route_task("data_analysis", "x") == ["data_agent"]
    assert coord.route_task("complex", "revenue and chart") == ["data_agent", "code_agent"]
    assert coord.route_task("complex", "revenue, chart and evaluate") == ["data_agent", "code_agent", "evaluator_agent"]
    with pytest.raises(ValueError):
        coord.route_task("unknown", "x")


@pytest.mark.asyncio
async def test_execute_tasks_collects_results():
    coord = make_coordinator(MockWorker("data_agent"), MockWorker("code_agent"))
    tasks = [{"id": "1", "worker": "data_agent", "content": "q"}, {"id": "2", "worker": "code_agent", "content": "c"}]
    results = await coord.execute_tasks(tasks)
    assert [r["status"] for r in results] == ["success", "success"]
    assert results[0]["type"] == "data" and results[1]["result"] == "code_agent: mock answer"


@pytest.mark.asyncio
async def test_worker_timeout_is_graceful():
    coord = make_coordinator(MockWorker("data_agent", delay=0.5))
    tasks = [{"id": "1", "worker": "data_agent", "content": "q"}]
    results = await coord.execute_tasks_with_retry(tasks, max_retries=1, timeout=0.05)
    assert results[0]["status"] == "timeout"             # không ném ngoại lệ, có kết quả từng phần
    assert coord.workers["data_agent"].calls == 2        # 1 lần đầu + 1 lần thử lại


@pytest.mark.asyncio
async def test_worker_exception_is_recorded_and_retried():
    worker = MockWorker("code_agent", fail_times=1)
    coord = make_coordinator(worker)
    results = await coord.execute_tasks_with_retry([{"id": "1", "worker": "code_agent", "content": "c"}],
                                                   max_retries=2, timeout=5)
    assert results[0]["status"] == "success" and worker.calls == 2


@pytest.mark.asyncio
async def test_aggregate_partial_when_one_worker_fails():
    coord = make_coordinator(MockWorker("data_agent"), MockWorker("code_agent", error=ValueError("boom")))
    tasks = [{"id": "1", "worker": "data_agent", "content": "q"}, {"id": "2", "worker": "code_agent", "content": "c"}]
    out = coord.aggregate_results(await coord.execute_tasks_with_retry(tasks, max_retries=0, timeout=5))
    assert out["status"] == "partial" and out["data"] and out["code"] is None
    assert out["errors"][0]["worker"] == "code_agent" and "boom" in out["errors"][0]["error"]


@pytest.mark.asyncio
async def test_handle_request_end_to_end_with_mock_workers():
    coord = make_coordinator(MockWorker("data_agent"), MockWorker("code_agent"))
    response = await coord.handle_request("Calculate revenue and create chart")
    assert response["status"] == "success"
    assert "data_agent" in response["data"] and "code_agent" in response["code"]
    assert response["task_type"] == "complex" and response["timestamp"]


@pytest.mark.asyncio
async def test_handle_request_invalid_input_returns_error():
    response = await make_coordinator().handle_request("   ")
    assert response["status"] == "error" and "invalid input" in response["errors"][0]["error"]


@pytest.mark.asyncio
async def test_resource_limit_rejects_too_many_tasks():
    coord = make_coordinator(*[MockWorker(f"w{i}") for i in range(MAX_TASKS + 2)])
    coord.route_task = lambda task_type, content: [f"w{i}" for i in range(MAX_TASKS + 1)]
    response = await coord.handle_request("analyze everything")
    assert response["status"] == "error" and "too many tasks" in response["errors"][0]["error"]
