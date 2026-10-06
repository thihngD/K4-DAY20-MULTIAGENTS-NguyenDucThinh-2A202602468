"""Phần 5 - debug một yêu cầu qua toàn hệ thống, in log DEBUG ra màn hình và lưu vào logs/.

    python scripts/debug_system.py "Calculate revenue and create chart"
    python scripts/debug_system.py --fake "Calculate revenue and create chart"

Xem log sau đó:  tail -f logs/coordinator.log   |   cat logs/communication.log | python -m json.tool
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm import DEMO_RULES, FakeLLM  # noqa: E402
from src.logs import get_logger  # noqa: E402
from src.system import MultiAgentSystem  # noqa: E402


async def debug_request(request: str, fake: bool) -> dict:
    model = FakeLLM(DEMO_RULES) if fake else None
    async with MultiAgentSystem(model=model) as system:
        print(f"🔍 Debugging: {request}")
        print("-" * 50)
        response = await system.process(request, debug=True)
    return response


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("request")
    ap.add_argument("--fake", action="store_true")
    args = ap.parse_args()
    # log DEBUG ra màn hình (ngoài các tệp log theo agent)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    root = get_logger("coordinator")
    root.addHandler(console)
    root.setLevel(logging.DEBUG)
    response = asyncio.run(debug_request(args.request, args.fake))
    print("✅ Success" if response["status"] == "success" else f"❌ Status: {response['status']}")
    return 0 if response["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
