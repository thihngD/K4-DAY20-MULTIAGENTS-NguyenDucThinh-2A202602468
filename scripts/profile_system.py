"""Phần 5 - đo nơi hệ thống dành thời gian (cProfile) khi xử lý nhiều yêu cầu liên tiếp.

    python scripts/profile_system.py            # mô hình giả: đo chi phí của chính hệ thống
    python scripts/profile_system.py --real     # mô hình thật: thời gian gồm cả thời gian chờ API

Kết quả: in ra 20 hàm chậm nhất (tính cả hàm con) và lưu vào logs/profile_<mode>.txt.
"""
import argparse
import asyncio
import cProfile
import io
import pstats
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm import DEMO_RULES, FakeLLM  # noqa: E402
from src.sample_data import create_sales_db  # noqa: E402
from src.system import MultiAgentSystem  # noqa: E402

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
REQUESTS = ["What is total revenue by region?", "Write Python script to draw a chart of revenue",
            "Analyze sales data", "Calculate revenue and create chart", "Analyze the sales and evaluate it"]


async def run_all(model, db, out) -> None:
    async with MultiAgentSystem(model=model, db_path=db, output_dir=out) as system:
        for req in REQUESTS:
            await system.process(req)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="use the OpenAI model (costs tokens)")
    args = ap.parse_args()
    work = Path(tempfile.mkdtemp(prefix="rq2-profile-"))
    db = create_sales_db(work / "sales.db")
    model = None if args.real else FakeLLM(DEMO_RULES)
    profiler = cProfile.Profile()
    profiler.enable()
    asyncio.run(run_all(model, db, work / "outputs"))
    profiler.disable()
    buf = io.StringIO()
    pstats.Stats(profiler, stream=buf).sort_stats("cumulative").print_stats(20)
    text = buf.getvalue()
    mode = "real" if args.real else "fake"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / f"profile_{mode}.txt").write_text(text, encoding="utf-8")
    print(text)
    print(f"saved to logs/profile_{mode}.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
