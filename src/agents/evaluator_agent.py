"""Evaluator Agent: chấm kết quả theo bốn tiêu chí (ScoringTool) và kiểm tra cấu trúc đầu ra (ValidationTool)."""
from .base_worker import BaseWorker
from .common import parse_json

REQUIRED_KEYS = ["scores", "feedback", "issues", "suggestions"]
WEIGHTS = {"accuracy": 30, "completeness": 30, "clarity": 20, "performance": 20}


class EvaluatorAgent(BaseWorker):
    system_prompt = (
        "You are a Quality Evaluation Specialist. Score the work on accuracy, completeness, clarity and "
        "performance, each from 0 to 100. Reply with JSON only: "
        '{"scores": {"accuracy": n, "completeness": n, "clarity": n, "performance": n}, '
        '"feedback": "...", "issues": ["..."], "suggestions": ["..."]}'
    )

    def __init__(self, model, tools: list):
        super().__init__("evaluator_agent", model, tools)

    def process(self, task_content: str, parameters: dict | None = None) -> dict:
        reply = self._ask(f"[EVAL] Evaluate the work below against the request.\n{task_content}\n"
                          f"Reply with the JSON object only.")
        data = parse_json(reply)
        check = self._execute_tool("validation", {"payload": data, "required": REQUIRED_KEYS})
        if check.get("status") != "success":
            return {"status": "error", "error": check.get("error", "invalid evaluation format")}
        scored = self._execute_tool("scoring", {"scores": data["scores"], "weights": WEIGHTS})
        return {"status": "success", "scores": scored,
                "result": f"score {scored['weighted_score']}/100 (grade {scored['grade']}). {data['feedback']}"}
