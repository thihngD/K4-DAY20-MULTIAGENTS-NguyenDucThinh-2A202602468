"""Cầu nối để Coordinator gọi worker qua message queue.

Coordinator gọi `proxy.process_async(...)` như gọi worker trực tiếp. Proxy gửi `task_request` vào hộp thư của
worker, rồi chờ `task_result` có cùng `task_id` trong hộp thư của chính nó.
"""
import uuid

from .message_queue import MessageQueue


class QueueWorkerProxy:
    def __init__(self, worker_name: str, queue: MessageQueue, reply_timeout: float = 120):
        self.name = worker_name
        self.queue = queue
        self.inbox = f"coordinator/{worker_name}"
        self.reply_timeout = reply_timeout
        queue.register_agent(self.inbox)

    async def process_async(self, task_content, parameters=None) -> dict:
        task_id = str(uuid.uuid4())
        await self.queue.send_message(self.inbox, self.name, {
            "type": "task_request", "task_id": task_id, "content": task_content, "parameters": parameters or {},
        })
        while True:
            reply = await self.queue.receive_message(self.inbox, timeout=self.reply_timeout)
            if reply.get("task_id") == task_id:          # bỏ qua trả lời muộn của tác vụ trước đã timeout
                break
        if reply.get("status") == "success":
            return {"status": "success", "result": reply.get("result")}
        return {"status": "error", "error": reply.get("error", "worker error")}
