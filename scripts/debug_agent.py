"""Phần 5 - chạy một worker độc lập để tìm lỗi (không qua coordinator và message queue).

    python scripts/debug_agent.py --agent data_agent --task "SELECT region, COUNT(*) FROM sales GROUP BY region"
    python scripts/debug_agent.py --agent code_agent --task "Draw a bar chart of orders per region"

Mặc định dùng mô hình thật (OPENAI_API_KEY). Thêm --fake để chạy bằng mô hình giả, không tốn token.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents import CodeAgent, DataAgent, EvaluatorAgent  # noqa: E402
from src.llm import CountingLLM, FakeLLM, make_llm  # noqa: E402
from src.sample_data import SCHEMA, create_sales_db  # noqa: E402
from src.tools.code_tools import CreateFileTool, EditFileTool, PythonREPLTool  # noqa: E402
from src.tools.database_tools import QueryDatabaseTool  # noqa: E402
from src.tools.evaluation_tools import ScoringTool, ValidationTool  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def build(agent: str, model, db: Path, out: Path):
    if agent == "data_agent":
        return DataAgent(model, [QueryDatabaseTool(db)], schema=SCHEMA)
    if agent == "code_agent":
        return CodeAgent(model, [PythonREPLTool(), CreateFileTool(out), EditFileTool(out)],
                         db_path=str(db.resolve()), output_dir=str(out.resolve()))
    return EvaluatorAgent(model, [ScoringTool(), ValidationTool()])


def main() -> int:
    ap = argparse.ArgumentParser(description="Run one worker agent standalone.")
    ap.add_argument("--agent", required=True, choices=["data_agent", "code_agent", "evaluator_agent"])
    ap.add_argument("--task", required=True)
    ap.add_argument("--parameters", default="{}", help="JSON object, for example '{\"quarter\": \"Q3\"}'")
    ap.add_argument("--fake", action="store_true", help="use the offline fake model")
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp(prefix="rq2-debug-"))
    db = ROOT / "data" / "sales.db"
    if not db.exists():
        db = create_sales_db(work / "sales.db")
    model = FakeLLM({"[SQL]": "SELECT region, COUNT(*) AS orders FROM sales GROUP BY region",
                     "[SUMMARY]": "Orders per region computed.", "[CODE]": "print('fake code ran')",
                     "[EVAL]": '{"scores": {"accuracy": 80, "completeness": 80, "clarity": 80, "performance": 80},'
                               ' "feedback": "ok", "issues": [], "suggestions": []}'}) if args.fake \
        else CountingLLM(make_llm())
    worker = build(args.agent, model, db, work / "outputs")
    print(f"[debug] agent={args.agent} model={'fake' if args.fake else 'openai'}")
    result = worker.process(args.task, json.loads(args.parameters))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if isinstance(model, CountingLLM):
        print(f"[debug] llm calls={model.calls} tokens={model.total_tokens}")
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
