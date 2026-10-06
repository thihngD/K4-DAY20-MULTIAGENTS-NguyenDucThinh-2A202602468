"""Hàng đợi tin nhắn bất đồng bộ giữa các agent (asyncio.Queue trong bộ nhớ, một hộp thư cho mỗi agent).

Mỗi tin nhắn được gắn `from`, `to`, `timestamp`, `id` và ghi vào `logs/communication.log` dưới dạng JSON.
Giới hạn: không bền vững và chỉ chạy trong một tiến trình (xem báo cáo, mục hạn chế).
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone

from ..logs import get_logger


class MessageQueue:
    def __init__(self):
        self.queues: dict[str, asyncio.Queue] = {}
        self.message_log: list[dict] = []
        self.logger = get_logger("communication")

    def register_agent(self, agent_name: str) -> None:
        """Tạo hộp thư cho agent (gọi một lần khi khởi tạo hệ thống)."""
        self.queues.setdefault(agent_name, asyncio.Queue())

    async def send_message(self, from_agent: str, to_agent: str, message: dict) -> str:
        if to_agent not in self.queues:
            raise ValueError(f"Agent {to_agent} not registered")
        envelope = {**message, "from": from_agent, "to": to_agent,
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    "id": str(uuid.uuid4())}
        self.message_log.append(envelope)
        self.logger.info(json.dumps(envelope, ensure_ascii=False, default=str))
        await self.queues[to_agent].put(envelope)
        return envelope["id"]

    async def receive_message(self, agent_name: str, timeout: float = 30) -> dict:
        """Nhận tin nhắn tiếp theo của agent. Hết thời gian thì ném TimeoutError."""
        try:
            return await asyncio.wait_for(self.queues[agent_name].get(), timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"No message for {agent_name} within {timeout}s") from exc

    def get_message_log(self, agent_name: str | None = None) -> list[dict]:
        if agent_name is None:
            return list(self.message_log)
        return [m for m in self.message_log if m["from"] == agent_name or m["to"] == agent_name]
