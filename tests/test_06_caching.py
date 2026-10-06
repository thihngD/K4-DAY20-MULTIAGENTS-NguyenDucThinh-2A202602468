"""Thử thách mở rộng 6c - cache kết quả của Coordinator (offline)."""
import asyncio

from src.caching import cache_key
from src.llm import FakeLLM
from src.sample_data import create_sales_db
from src.system import MultiAgentSystem

RULES = {"[SQL]": "SELECT region, SUM(amount) AS revenue FROM sales GROUP BY region",
         "[SUMMARY]": "Revenue by region computed."}


def run_sequence(tmp_path, requests, rules=RULES):
    db = create_sales_db(tmp_path / "sales.db", rows=30)
    model = FakeLLM(rules)

    async def scenario():
        async with MultiAgentSystem(model=model, db_path=db, output_dir=tmp_path / "out", cache=True) as system:
            return [await system.process(r) for r in requests], system.coordinator

    responses, coordinator = asyncio.run(scenario())
    return responses, coordinator, model


def test_cache_key_normalises_case_and_spaces():
    assert cache_key("  Total   Revenue? ") == cache_key("total revenue?")
    assert cache_key("") is None and cache_key(None) is None


def test_repeated_request_is_served_from_cache(tmp_path):
    responses, coord, model = run_sequence(tmp_path, ["What is total revenue?", "what is  TOTAL revenue?"])
    assert [r["cache"] for r in responses] == ["miss", "hit"]
    assert responses[0]["data"] == responses[1]["data"]
    assert coord.hits == 1 and coord.misses == 1
    assert len([p for p in model.prompts if "[SQL]" in p]) == 1      # mô hình chỉ được gọi một lần cho SQL


def test_failed_result_is_not_cached(tmp_path):
    bad_rules = {"[SQL]": "DROP TABLE sales", "[SUMMARY]": "x"}
    responses, coord, model = run_sequence(tmp_path, ["Show all sales", "Show all sales"], rules=bad_rules)
    assert [r["status"] for r in responses] == ["error", "error"]
    assert coord.cache == {} and coord.misses == 2                  # cả hai lần đều được tính lại
