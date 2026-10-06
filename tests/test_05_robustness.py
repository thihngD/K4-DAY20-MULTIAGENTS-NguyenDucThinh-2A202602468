"""Kiểm tra bổ sung (offline, không tốn token): log từng bước và timeout của mô hình mặc định."""
from langchain_core.messages import AIMessage

from lab.agent import MODEL_MAX_RETRIES, MODEL_TIMEOUT, default_model
from lab.runner import run_task


def test_progress_log_has_one_line_per_step(tmp_path, scripted):
    first = AIMessage(content="", tool_calls=[{"name": "ls", "args": {"path": "workspace"}, "id": "1"}])
    run_task("data-learn", "baseline", results_dir=tmp_path, model=scripted(first, AIMessage(content="done")))
    lines = (tmp_path / "baseline" / "data-learn" / "progress.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 3                                   # user, assistant (tool call), tool result, assistant
    assert lines[0].startswith("step=1 ") and "last=human" in lines[0]
    assert any("tools=['ls']" in ln for ln in lines)
    assert (tmp_path / "baseline" / "data-learn" / "trace.md").exists()


def test_default_model_has_timeout_and_retries(monkeypatch):
    monkeypatch.setenv("LAB_MODEL", "openai:gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.delenv("LAB_BASE_URL", raising=False)
    model = default_model()
    assert model.request_timeout == MODEL_TIMEOUT
    assert model.max_retries == MODEL_MAX_RETRIES
