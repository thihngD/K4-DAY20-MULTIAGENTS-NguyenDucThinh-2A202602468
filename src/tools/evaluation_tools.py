"""Công cụ cho Evaluator Agent: chấm điểm theo trọng số và kiểm tra cấu trúc đầu ra."""
from .base_tool import BaseTool

CRITERIA = ("accuracy", "completeness", "clarity", "performance")


def grade_for(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


class ScoringTool(BaseTool):
    def __init__(self):
        super().__init__("scoring", "Compute the weighted score (0-100) and letter grade from criterion scores.")

    def validate_input(self, input_dict: dict) -> None:
        scores = input_dict.get("scores")
        weights = input_dict.get("weights")
        if not isinstance(scores, dict) or not isinstance(weights, dict):
            raise ValueError("scores and weights must be objects")
        for key in CRITERIA:
            value = scores.get(key)
            if not isinstance(value, (int, float)) or not 0 <= value <= 100:
                raise ValueError(f"score {key} must be a number from 0 to 100")
        if sum(weights.values()) <= 0:
            raise ValueError("weights must add up to a positive number")

    def invoke(self, input_dict: dict) -> dict:
        self.validate_input(input_dict)
        scores, weights = input_dict["scores"], input_dict["weights"]
        total = sum(weights.values())
        weighted = sum(float(scores[k]) * w for k, w in weights.items() if k in scores) / total
        return {"status": "success", "scores": {k: scores[k] for k in CRITERIA},
                "weighted_score": round(weighted, 2), "grade": grade_for(weighted)}


class ValidationTool(BaseTool):
    def __init__(self):
        super().__init__("validation", "Check that an evaluation reply has the required keys and valid scores.")

    def validate_input(self, input_dict: dict) -> None:
        if not isinstance(input_dict.get("payload"), dict) or not isinstance(input_dict.get("required"), list):
            raise ValueError("payload must be an object and required a list")

    def invoke(self, input_dict: dict) -> dict:
        self.validate_input(input_dict)
        payload, required = input_dict["payload"], input_dict["required"]
        missing = [k for k in required if k not in payload]
        if missing:
            return {"status": "error", "error": f"missing keys: {missing}"}
        scores = payload.get("scores")
        if not isinstance(scores, dict) or any(
                not isinstance(scores.get(k), (int, float)) or not 0 <= scores[k] <= 100 for k in CRITERIA):
            return {"status": "error", "error": "scores must contain accuracy, completeness, clarity, performance (0-100)"}
        return {"status": "success"}
