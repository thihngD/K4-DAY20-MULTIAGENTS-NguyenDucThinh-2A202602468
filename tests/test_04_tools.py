"""Phần 4 - Tools, an toàn đầu vào và tích hợp end-to-end (offline, REPL và SQLite thật, mô hình giả)."""
import asyncio

import pytest

from src.llm import FakeLLM
from src.sample_data import create_sales_db
from src.system import MultiAgentSystem
from src.tools import code_tools
from src.tools.code_tools import CreateFileTool, EditFileTool, PythonREPLTool
from src.tools.database_tools import QueryDatabaseTool
from src.tools.evaluation_tools import ScoringTool, ValidationTool


@pytest.fixture
def db(tmp_path):
    return create_sales_db(tmp_path / "sales.db", rows=50)


def test_query_tool_runs_select_and_adds_limit(db):
    out = QueryDatabaseTool(db).invoke({"query": "SELECT region, COUNT(*) AS n FROM sales GROUP BY region;"})
    assert out["status"] == "success" and out["rows"] == 4 and set(out["columns"]) == {"region", "n"}


def test_query_tool_accepts_with_clause(db):
    query = "WITH q AS (SELECT region, amount FROM sales) SELECT region, SUM(amount) AS total FROM q GROUP BY region"
    assert QueryDatabaseTool(db).invoke({"query": query})["status"] == "success"


@pytest.mark.parametrize("bad", [
    "DROP TABLE sales",
    "DELETE FROM sales",
    "SELECT * FROM sales; DROP TABLE sales",           # SQL injection bằng nhiều câu lệnh
    "SELECT 1 UNION SELECT 2 FROM sales UPDATE sales SET amount=0",
    "PRAGMA table_info(sales)",
    "",
])
def test_query_tool_blocks_writes_and_injection(db, bad):
    with pytest.raises(ValueError):
        QueryDatabaseTool(db).invoke({"query": bad})


def test_query_tool_connection_is_read_only(db, tmp_path):
    import sqlite3
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("UPDATE sales SET amount = 0")
    conn.close()


def test_repl_runs_code_and_captures_output():
    out = PythonREPLTool().invoke({"code": "total = sum([1, 2, 3])\nprint('total', total)"})
    assert out == {"status": "success", "stdout": "total 6\n"}


@pytest.mark.parametrize("bad", ["import os\nprint(os.getcwd())", "from subprocess import run",
                                 "open('x.txt', 'w')", "exec('print(1)')", "__import__('os')"])
def test_repl_blocks_dangerous_code(bad):
    with pytest.raises(ValueError):
        PythonREPLTool().invoke({"code": bad})


def test_repl_reports_runtime_errors():
    out = PythonREPLTool().invoke({"code": "print(undefined_name)"})
    assert out["status"] == "error" and "NameError" in out["error"]


def test_repl_timeout_returns_error(monkeypatch):
    monkeypatch.setattr(code_tools, "TIMEOUT", 0.3)
    out = PythonREPLTool().invoke({"code": "x = 0\nwhile True:\n    x += 1"})
    assert out["status"] == "error" and "timeout" in out["error"]


def test_repl_can_draw_a_chart_into_output_folder(tmp_path):
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()
    code = f"import matplotlib.pyplot as plt\nplt.bar(['a', 'b'], [1, 2])\nplt.savefig({str(out_dir / 'chart.png')!r})\nprint('saved')"
    assert PythonREPLTool().invoke({"code": code})["stdout"] == "saved\n"
    assert (out_dir / "chart.png").stat().st_size > 0


@pytest.mark.parametrize("name", ["../escape.txt", "/etc/passwd", "C:/x.txt", "sub/../../x.txt", "bad name!.txt"])
def test_create_file_blocks_path_escape(tmp_path, name):
    with pytest.raises(ValueError):
        CreateFileTool(tmp_path / "outputs").invoke({"filename": name, "content": "x"})


def test_create_and_edit_file_inside_output_folder(tmp_path):
    create = CreateFileTool(tmp_path / "outputs")
    assert create.invoke({"filename": "report/summary.md", "content": "revenue: 0"})["status"] == "success"
    edit = EditFileTool(tmp_path / "outputs")
    out = edit.invoke({"filename": "report/summary.md", "old": "0", "new": "1234"})
    assert out["replacements"] == 1
    assert (tmp_path / "outputs" / "report" / "summary.md").read_text(encoding="utf-8") == "revenue: 1234"
    with pytest.raises(ValueError):
        edit.invoke({"filename": "missing.md", "old": "a", "new": "b"})


def test_scoring_tool_weights_and_grade():
    out = ScoringTool().invoke({"scores": {"accuracy": 90, "completeness": 80, "clarity": 70, "performance": 60},
                                "weights": {"accuracy": 30, "completeness": 30, "clarity": 20, "performance": 20}})
    # (90*30 + 80*30 + 70*20 + 60*20) / 100 = 77.0 -> hạng C
    assert out["weighted_score"] == 77.0 and out["grade"] == "C"
    with pytest.raises(ValueError):
        ScoringTool().invoke({"scores": {"accuracy": 120, "completeness": 1, "clarity": 1, "performance": 1},
                              "weights": {"accuracy": 1}})


def test_validation_tool_checks_keys_and_ranges():
    tool = ValidationTool()
    good = {"scores": {"accuracy": 1, "completeness": 2, "clarity": 3, "performance": 4}, "feedback": "x",
            "issues": [], "suggestions": []}
    assert tool.invoke({"payload": good, "required": ["scores", "feedback"]})["status"] == "success"
    assert tool.invoke({"payload": {"scores": good["scores"]}, "required": ["feedback"]})["status"] == "error"
    bad_scores = {**good, "scores": {**good["scores"], "clarity": 300}}
    assert tool.invoke({"payload": bad_scores, "required": ["scores"]})["status"] == "error"


def test_end_to_end_system_with_real_database_and_repl(tmp_path):
    db_path = create_sales_db(tmp_path / "sales.db", rows=60)
    model = FakeLLM({
        "[SQL]": "SELECT region, ROUND(SUM(amount), 2) AS revenue FROM sales GROUP BY region",
        "[SUMMARY]": "Revenue by region is computed from the sales table.",
        "[CODE]": ("import sqlite3\nimport matplotlib.pyplot as plt\n"
                   "conn = sqlite3.connect(DB_URI, uri=True)\n"
                   "rows = conn.execute('SELECT region, SUM(amount) FROM sales GROUP BY region').fetchall()\n"
                   "plt.bar([r[0] for r in rows], [r[1] for r in rows])\n"
                   "plt.savefig(OUTPUT_DIR + '/chart.png')\nprint(len(rows), 'regions')"),
        "[EVAL]": ('{"scores": {"accuracy": 90, "completeness": 85, "clarity": 80, "performance": 88},'
                   ' "feedback": "Clear answer with a chart.", "issues": [], "suggestions": []}'),
    })

    async def scenario():
        async with MultiAgentSystem(model=model, db_path=db_path, output_dir=tmp_path / "outputs") as system:
            return await system.process("Calculate revenue by region, create a chart and evaluate the result")

    response = asyncio.run(scenario())
    assert response["status"] == "success"
    assert "Revenue by region" in response["data"]
    assert "4 regions" in response["code"] and "chart" in response["code"]
    assert "score" in response["evaluation"]
    assert (tmp_path / "outputs" / "chart.png").exists()
