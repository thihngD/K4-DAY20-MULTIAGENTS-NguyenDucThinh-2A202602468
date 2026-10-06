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

    max_attempts = 2

    def __init__(self, model, tools: list):
        super().__init__("evaluator_agent", model, tools)

    def process(self, task_content: str, parameters: dict | None = None) -> dict:
        note = ""
        for attempt in range(1, self.max_attempts + 1):
            reply = self._ask(f"{self.system_prompt}\n\n[EVAL] Evaluate the work below against the request.\n"
                              f"{task_content}\nReply with the JSON object only.{note}")
            try:
                data = parse_json(reply)
                check = self._execute_tool("validation", {"payload": data, "required": REQUIRED_KEYS})
                error = None if check.get("status") == "success" else check.get("error", "invalid format")
            except ValueError as exc:
                error = str(exc)
            if error is None:
                break
            self.logger.warning("evaluation attempt %d invalid: %s", attempt, error)
            note = f"\nYour previous reply was invalid ({error}). Reply with the JSON object only."
        if error is not None:
            return {"status": "error", "error": error}
        scored = self._execute_tool("scoring", {"scores": data["scores"], "weights": WEIGHTS})
        return {"status": "success", "scores": scored,
                "result": f"score {scored['weighted_score']}/100 (grade {scored['grade']}). {data['feedback']}"}
