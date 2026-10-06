"""Phần 5 - Tích hợp end-to-end, lỗi, đồng thời và độ trễ. Offline: mô hình giả, REPL và SQLite thật."""
import asyncio
import sqlite3
import time

import pytest

from src.llm import FakeLLM
from src.sample_data import create_sales_db
from src.system import MultiAgentSystem

EVAL = ('{"scores": {"accuracy": 90, "completeness": 85, "clarity": 80, "performance": 88},'
        ' "feedback": "Clear.", "issues": [], "suggestions": []}')
CHART_CODE = ("import sqlite3\nimport matplotlib.pyplot as plt\n"
              "rows = sqlite3.connect(DB_URI, uri=True).execute('SELECT region, SUM(amount) FROM sales "
              "GROUP BY region').fetchall()\nplt.bar([r[0] for r in rows], [r[1] for r in rows])\n"
              "plt.savefig(OUTPUT_DIR + '/chart.png')\nprint(len(rows), 'regions')")


def good_model(**overrides):
    rules = {"[SQL]": "SELECT region, ROUND(SUM(amount), 2) AS revenue FROM sales GROUP BY region",
             "[SUMMARY]": "Revenue by region is computed.", "[CODE]": CHART_CODE, "[EVAL]": EVAL}
    rules.update(overrides)
    return FakeLLM(rules)


class SlowLLM(FakeLLM):
    def __init__(self, delay, **kwargs):
        super().__init__(**kwargs)
        self.delay = delay

    def invoke(self, prompt):
        time.sleep(self.delay)
        return super().invoke(prompt)


class FlakyLLM(FakeLLM):
    """Lỗi ở lần gọi đầu tiên (ví dụ lỗi mạng), sau đó hoạt động bình thường."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.failed = False

    def invoke(self, prompt):
        if not self.failed:
            self.failed = True
            raise RuntimeError("connection reset")
        return super().invoke(prompt)


@pytest.fixture
def db(tmp_path):
    return create_sales_db(tmp_path / "sales.db", rows=60)


def make_system(tmp_path, model, db, **kwargs):
    return MultiAgentSystem(model=model, db_path=db, output_dir=tmp_path / "outputs", **kwargs)


def run(coro):
    return asyncio.run(coro)


def test_e2e_simple_query(tmp_path, db):
    async def scenario():
        async with make_system(tmp_path, good_model(), db) as system:
            return await system.process("What is total revenue by region?")
    response = run(scenario())
    assert response["status"] == "success" and response["task_type"] == "data_analysis"
    assert "Revenue by region" in response["data"] and response["code"] is None


def test_e2e_complex_workflow_produces_chart_and_score(tmp_path, db):
    async def scenario():
        async with make_system(tmp_path, good_model(), db) as system:
            return await system.process("Calculate revenue by region, create a chart and evaluate the result")
    response = run(scenario())
    assert response["status"] == "success"
    assert "4 regions" in response["code"] and "score" in response["evaluation"]
    assert (tmp_path / "outputs" / "chart.png").exists()


def test_sql_injection_is_blocked_and_database_untouched(tmp_path, db):
    async def scenario():
        async with make_system(tmp_path, good_model(**{"[SQL]": "DROP TABLE sales"}), db) as system:
            return await system.process("Show all sales data")
    response = run(scenario())
    assert response["status"] == "error" and "only SELECT" in response["errors"][0]["error"]
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 60
    conn.close()


def test_python_sandbox_blocks_os_access_end_to_end(tmp_path, db):
    async def scenario():
        model = good_model(**{"[CODE]": "import os\nprint(os.listdir('.'))"})
        async with make_system(tmp_path, model, db) as system:
            return await system.process("Create a file listing with Python code")
    response = run(scenario())
    assert response["status"] == "error" and response["errors"][0]["worker"] == "code_agent"
    assert "not allowed" in response["errors"][0]["error"]


def test_slow_worker_times_out_gracefully(tmp_path, db):
    async def scenario():
        model = SlowLLM(delay=0.5, rules=good_model().rules)
        async with make_system(tmp_path, model, db, timeout=0.2, max_retries=0) as system:
            return await system.process("What is total revenue?")
    response = run(scenario())                 # không ném lỗi
    assert response["status"] == "error" and response["errors"][0]["status"] == "timeout"


def test_worker_failure_does_not_stop_later_requests(tmp_path, db):
    async def scenario():
        model = FlakyLLM(rules=good_model().rules)
        async with make_system(tmp_path, model, db, max_retries=1) as system:
            first = await system.process("What is total revenue?")
            second = await system.process("What is total revenue?")
            return first, second
    first, second = run(scenario())
    assert first["status"] == "success"        # lỗi lần đầu được thử lại và thành công
    assert second["status"] == "success"


def test_ten_concurrent_requests_meet_success_target(tmp_path, db):
    async def scenario():
        async with make_system(tmp_path, good_model(), db) as system:
            return await asyncio.gather(*(system.process(f"Task {i}: total revenue") for i in range(10)))
    results = run(scenario())
    success = sum(1 for r in results if r["status"] == "success")
    assert success >= 8                         # mục tiêu: ít nhất 80% thành công


def test_offline_latency_is_well_below_budget(tmp_path, db):
    async def scenario():
        async with make_system(tmp_path, good_model(), db) as system:
            started = time.time()
            await system.process("Calculate revenue by region, create a chart and evaluate the result")
            return time.time() - started
    assert run(scenario()) < 10                # ngân sách 10 giây cho một yêu cầu (mô hình giả)


def test_message_log_records_each_hop(tmp_path, db):
    async def scenario():
        async with make_system(tmp_path, good_model(), db) as system:
            await system.process("What is total revenue?")
            return system.queue.get_message_log()
    log = run(scenario())
    kinds = [m["type"] for m in log]
    assert kinds == ["task_request", "task_result"]
    assert log[0]["to"] == "data_agent" and log[1]["to"] == "coordinator/data_agent"
    assert log[0]["id"] and log[0]["timestamp"]


def test_invalid_request_returns_error_without_workers(tmp_path, db):
    async def scenario():
        async with make_system(tmp_path, good_model(), db) as system:
            return await system.process("   ")
    response = run(scenario())
    assert response["status"] == "error" and "invalid input" in response["errors"][0]["error"]


def test_process_requires_started_system(tmp_path, db):
    system = make_system(tmp_path, good_model(), db)
    with pytest.raises(RuntimeError):
        run(system.process("What is total revenue?"))
