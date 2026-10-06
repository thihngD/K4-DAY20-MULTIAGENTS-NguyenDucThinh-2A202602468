"""Thí nghiệm 6c - cache kết quả. Cùng bộ yêu cầu và thứ tự với scripts/benchmark.py, nhưng bật cache.

    python experiments/caching/run_caching.py --run 1      # ghi experiments/caching/results/run1.json

Mỗi lần chạy khởi tạo hệ thống mới (cache rỗng). Lần lặp 1 của mỗi tình huống là bỏ lỡ (miss),
lần 2 và 3 là trúng cache (hit). So sánh với benchmarks/run*.json (không cache) để tính phần tiết kiệm.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.llm import CountingLLM, make_llm  # noqa: E402
from src.system import MultiAgentSystem  # noqa: E402

CASES = [
    ("Simple data query", "What is total revenue by region?"),
    ("Code generation", "Write a Python script that draws a bar chart of revenue by region"),
    ("Complex workflow", "Analyze sales data, create a chart and evaluate the result"),
]


async def run(iterations: int) -> list[dict]:
    model = CountingLLM(make_llm())
    records = []
    async with MultiAgentSystem(model=model, db_path=ROOT / "data" / "sales.db",
                                output_dir=ROOT / "experiments" / "caching" / "outputs", cache=True) as system:
        for name, request in CASES:
            for i in range(1, iterations + 1):
                before = model.total_tokens
                started = time.time()
                response = await system.process(request)
                records.append({"case": name, "iteration": i, "cache": response.get("cache"),
                                "latency": round(time.time() - started, 3), "status": response["status"],
                                "tokens": model.total_tokens - before})
                print(f"  {name:18s} iter {i}: {records[-1]['latency']:6.2f}s cache={records[-1]['cache']} "
                      f"status={records[-1]['status']} tokens={records[-1]['tokens']}", flush=True)
    return records


def summarise(records: list[dict]) -> dict:
    miss = [r for r in records if r["cache"] == "miss"]
    hit = [r for r in records if r["cache"] == "hit"]
    return {
        "requests": len(records),
        "hits": len(hit),
        "misses": len(miss),
        "hit_rate": round(len(hit) / len(records), 3),
        "latency_miss_avg": round(statistics.mean(r["latency"] for r in miss), 3) if miss else None,
        "latency_hit_avg": round(statistics.mean(r["latency"] for r in hit), 4) if hit else None,
        "tokens_total": sum(r["tokens"] for r in records),
        "tokens_on_hits": sum(r["tokens"] for r in hit),
        "error_rate": round(sum(1 for r in records if r["status"] != "success") / len(records), 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--iterations", type=int, default=3)
    args = ap.parse_args()
    print(f"caching experiment run {args.run}: {args.iterations} iterations per case, cache on")
    records = asyncio.run(run(args.iterations))
    out = ROOT / "experiments" / "caching" / "results" / f"run{args.run}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cache": True, "records": records, "summary": summarise(records)}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
