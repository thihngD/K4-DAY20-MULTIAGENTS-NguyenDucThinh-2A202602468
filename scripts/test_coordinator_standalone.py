"""Phần 2 - kiểm tra Coordinator độc lập với worker giả. Không gọi mô hình, không tốn token.

    python scripts/test_coordinator_standalone.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.coordinator import Coordinator  # noqa: E402


class MockWorker:
    def __init__(self, name, delay=0.0):
        self.name = name
        self.delay = delay

    async def process_async(self, task_content, parameters=None):
        await asyncio.sleep(self.delay)
        return {"status": "success", "result": f"[mock {self.name} data]"}


async def main() -> int:
    coord = Coordinator(model=None, workers=[MockWorker("data_agent"), MockWorker("code_agent"),
                                             MockWorker("slow_agent", delay=1.0)], timeout=0.5, max_retries=0)
    print("Testing Coordinator with mock workers...\n")
    failures = 0

    cases = [
        ("Test 1: Simple task", "Analyze sales data", "data_analysis", ["data_agent"], "success"),
        ("Test 2: Multiple tasks", "Analyze AND create report", "complex", ["data_agent", "code_agent"], "success"),
    ]
    for title, text, expected_type, expected_workers, expected_status in cases:
        parsed = coord.parse_request(text)
        workers = coord.route_task(parsed["task_type"], text)
        response = await coord.handle_request(text)
        ok = parsed["task_type"] == expected_type and workers == expected_workers and response["status"] == expected_status
        failures += not ok
        print(title)
        print(f"  Input: {text!r}\n  Parsed: task_type={parsed['task_type']}\n  Routed to: {', '.join(workers)}")
        print(f"  Result: status={response['status']}  {'✓ Pass' if ok else '✗ FAIL'}\n")

    slow = Coordinator(model=None, workers=[MockWorker("data_agent", delay=1.0)], timeout=0.2, max_retries=1)
    response = await slow.handle_request("Analyze the long task")
    ok = response["status"] == "error" and response["errors"][0]["status"] == "timeout"
    failures += not ok
    print("Test 3: Timeout handling")
    print("  Input: 'Analyze the long task' (worker takes 1.0s, timeout 0.2s, 1 retry)")
    print(f"  Result: status={response['status']} error={response['errors'][0]['status']}  "
          f"{'✓ Pass (graceful timeout)' if ok else '✗ FAIL'}\n")

    print(f"All coordinator tests passed ({3 - failures}/3)" if failures == 0 else f"{failures} test(s) FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
