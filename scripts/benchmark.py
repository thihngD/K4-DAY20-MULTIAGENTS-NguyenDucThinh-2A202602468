"""Phần 5 - benchmark: ba tình huống, mỗi tình huống lặp `--iterations` lần, gửi tuần tự.

    python scripts/benchmark.py --out benchmarks/run1.json          # mô hình thật (tốn token)
    python scripts/benchmark.py --fake --out benchmarks/dry.json    # mô hình giả, kiểm tra script

Đo: độ trễ min/max/avg/median theo tình huống, P50/P99 chung, thông lượng (yêu cầu/phút), tỉ lệ lỗi,
token mỗi 100 yêu cầu, và độ bận của từng worker (thời gian xử lý / thời gian chạy).
"""
import argparse
import asyncio
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm import DEMO_RULES, CountingLLM, FakeLLM, make_llm  # noqa: E402
from src.sample_data import create_sales_db  # noqa: E402
from src.system import MultiAgentSystem  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("Simple data query", "What is total revenue by region?"),
    ("Code generation", "Write a Python script that draws a bar chart of revenue by region"),
    ("Complex workflow", "Analyze sales data, create a chart and evaluate the result"),
]


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    rank = max(1, round(pct / 100 * len(ordered)))      # phương pháp nearest-rank
    return ordered[rank - 1]


def instrument(system: MultiAgentSystem) -> dict[str, float]:
    """Đo thời gian bận của từng worker bằng cách bọc hàm process."""
    busy = {name: 0.0 for name in system.agents}
    for name, agent in system.agents.items():
        original = agent.process

        def timed(task_content, parameters=None, _orig=original, _name=name):
            started = time.time()
            try:
                return _orig(task_content, parameters)
            finally:
                busy[_name] += time.time() - started

        agent.process = timed
    return busy


async def run(fake: bool, iterations: int, db: Path, out_dir: Path) -> dict:
    counting = None
    model = FakeLLM(DEMO_RULES) if fake else CountingLLM(make_llm())
    counting = model if not fake else None
    async with MultiAgentSystem(model=model, db_path=db, output_dir=out_dir) as system:
        busy = instrument(system)
        records = []
        wall_started = time.time()
        for name, request in CASES:
            for i in range(1, iterations + 1):
                tokens_before = counting.total_tokens if counting else 0
                started = time.time()
                response = await system.process(request)
                latency = time.time() - started
                tokens = (counting.total_tokens - tokens_before) if counting else 0
                records.append({"case": name, "iteration": i, "latency": round(latency, 3),
                                "status": response["status"], "tokens": tokens})
                print(f"  {name:18s} iter {i}: {latency:6.2f}s  status={response['status']}  tokens={tokens}",
                      flush=True)
        wall = time.time() - wall_started
    return {"records": records, "wall_seconds": round(wall, 2), "busy_seconds": {k: round(v, 2) for k, v in busy.items()}}


def summarise(result: dict) -> dict:
    records = result["records"]
    lat = [r["latency"] for r in records]
    per_case = {}
    for name, _ in CASES:
        values = [r["latency"] for r in records if r["case"] == name]
        per_case[name] = {"iterations": len(values), "min": round(min(values), 2), "max": round(max(values), 2),
                          "avg": round(statistics.mean(values), 2), "median": round(statistics.median(values), 2)}
    failed = sum(1 for r in records if r["status"] != "success")
    total_tokens = sum(r["tokens"] for r in records)
    wall = result["wall_seconds"]
    utilisation = {k: round(v / wall, 3) for k, v in result["busy_seconds"].items()} if wall else {}
    return {
        "requests": len(records),
        "per_case": per_case,
        "p50": round(percentile(lat, 50), 2),
        "p99": round(percentile(lat, 99), 2),
        "throughput_per_min": round(len(records) / wall * 60, 2) if wall else 0,
        "error_rate": round(failed / len(records), 3),
        "tokens_total": total_tokens,
        "tokens_per_100_requests": round(total_tokens / len(records) * 100) if records else 0,
        "worker_utilisation": utilisation,
        "wall_seconds": wall,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark the multi-agent system.")
    ap.add_argument("--iterations", type=int, default=3)
    ap.add_argument("--fake", action="store_true", help="offline fake model (no tokens)")
    ap.add_argument("--out", default=str(ROOT / "benchmark_results.json"))
    args = ap.parse_args()
    db = ROOT / "data" / "sales.db"
    if not db.exists():
        db = create_sales_db(Path(tempfile.mkdtemp()) / "sales.db")
    out_dir = ROOT / "outputs"
    print(f"benchmark: {'fake' if args.fake else 'openai'} model, {args.iterations} iterations per case")
    result = asyncio.run(run(args.fake, args.iterations, db, out_dir))
    summary = summarise(result)
    payload = {"mode": "fake" if args.fake else "openai", "iterations": args.iterations, "summary": summary,
               **result}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"saved to {out}")
    return 0 if all(r["status"] == "success" for r in result["records"]) else 1


if __name__ == "__main__":
    sys.exit(main())
