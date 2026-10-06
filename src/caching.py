"""Thử thách mở rộng 6c - cache kết quả cho Coordinator.

Yêu cầu giống hệt (sau khi chuẩn hóa khoảng trắng và chữ hoa/thường) được trả lời từ bộ nhớ, không gọi lại worker.
Chỉ lưu kết quả `success`: kết quả `partial` hoặc `error` luôn được tính lại.
Hạn chế: không có thời gian hết hạn; dữ liệu thay đổi thì cache trả kết quả cũ.
"""
from .coordinator import Coordinator


def cache_key(request) -> str | None:
    if not isinstance(request, str) or not request.strip():
        return None
    return " ".join(request.lower().split())


class CachingCoordinator(Coordinator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache: dict[str, dict] = {}
        self.hits = 0
        self.misses = 0

    async def handle_request(self, request: str) -> dict:
        key = cache_key(request)
        if key is not None and key in self.cache:
            self.hits += 1
            return {**self.cache[key], "cache": "hit"}
        self.misses += 1
        response = await super().handle_request(request)
        if key is not None and response["status"] == "success":
            self.cache[key] = response
        return {**response, "cache": "miss"}
