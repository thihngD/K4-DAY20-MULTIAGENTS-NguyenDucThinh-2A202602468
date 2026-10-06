"""Phần 4 - kiểm tra worker dùng tool thật: Data Agent truy vấn DB, Code Agent vẽ biểu đồ, Evaluator chấm điểm.

Dùng mô hình giả nên không tốn token; tool (SQLite, REPL, file, chấm điểm) là thật.
    python scripts/test_tool_integration.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents import CodeAgent, DataAgent, EvaluatorAgent  # noqa: E402
from src.llm import FakeLLM  # noqa: E402
from src.sample_data import SCHEMA, create_sales_db  # noqa: E402
from src.tools.code_tools import CreateFileTool, EditFileTool, PythonREPLTool  # noqa: E402
from src.tools.database_tools import QueryDatabaseTool  # noqa: E402
from src.tools.evaluation_tools import ScoringTool, ValidationTool  # noqa: E402


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="rq2-tools-"))
    db = create_sales_db(work / "sales.db")
    out_dir = work / "outputs"
    model = FakeLLM({
        "[SQL]": "SELECT region, COUNT(*) AS orders FROM sales GROUP BY region",
        "[SUMMARY]": "There are four regions with orders spread across them.",
        "[CODE]": ("import sqlite3\nimport matplotlib.pyplot as plt\n"
                   "rows = sqlite3.connect(DB_URI, uri=True).execute('SELECT region, COUNT(*) FROM sales "
                   "GROUP BY region').fetchall()\nplt.bar([r[0] for r in rows], [r[1] for r in rows])\n"
                   "plt.savefig(OUTPUT_DIR + '/chart.png')\nprint('chart saved with', len(rows), 'bars')"),
        "[EVAL]": ('{"scores": {"accuracy": 90, "completeness": 85, "clarity": 80, "performance": 88},'
                   ' "feedback": "Correct and clear.", "issues": [], "suggestions": []}'),
    })
    data_agent = DataAgent(model, [QueryDatabaseTool(db)], schema=SCHEMA)
    code_agent = CodeAgent(model, [PythonREPLTool(), CreateFileTool(out_dir), EditFileTool(out_dir)],
                           db_path=str(db.resolve()), output_dir=str(out_dir.resolve()))
    evaluator = EvaluatorAgent(model, [ScoringTool(), ValidationTool()])

    checks = []
    print("Test: Data Agent queries database")
    out = data_agent.process("How many orders per region?")
    ok = out["status"] == "success" and len(out["rows"]) == 4
    checks.append(ok)
    print(f"  SQL: {out.get('query')}\n  Rows: {len(out.get('rows', []))}  {'✓' if ok else '✗ FAIL'}\n")

    print("Test: Code Agent creates visualization")
    out = asyncio.run(code_agent.process_async("Draw a bar chart of orders per region"))
    ok = out["status"] == "success" and (out_dir / "chart.png").exists()
    checks.append(ok)
    print(f"  Output: {out.get('result', out.get('error', '')).splitlines()[-1] if out.get('result') else out}")
    print(f"  File created: {(out_dir / 'chart.png').exists()}  {'✓' if ok else '✗ FAIL'}\n")

    print("Test: Evaluator scores the result")
    out = asyncio.run(evaluator.process_async("Evaluate: 4 regions, orders counted per region"))
    ok = out["status"] == "success" and out["scores"]["grade"] == "B"
    checks.append(ok)
    print(f"  {out.get('result', out.get('error'))}  {'✓' if ok else '✗ FAIL'}\n")

    print(f"All tool tests passed ({sum(checks)}/{len(checks)})" if all(checks) else
          f"{len(checks) - sum(checks)} test(s) FAILED")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
