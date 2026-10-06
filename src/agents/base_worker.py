"""BaseWorker: khuôn chung cho worker agent.

Worker nhận `task` (nội dung và tham số), gọi mô hình, dùng tool khi cần và trả về
{"status": "success", "result": ...} hoặc {"status": "error", "error": ...}.
`serve()` lắng nghe hộp thư trong message queue, xử lý từng tin nhắn và gửi kết quả về cho người gửi.
"""
import asyncio

from ..base_agent import BaseAgent


class BaseWorker(BaseAgent):
    system_prompt = ""           # worker con ghi đè: vai trò, phạm vi, định dạng đầu ra

    def __init__(self, name: str, model, tools: list):
        super().__init__(name, model)
        self.tools = {t.name: t for t in tools}
        self._executed_tools: list[str] = []

    def _build_prompt(self, task_content: str, parameters: dict | None) -> str:
        return (f"{self.system_prompt}\n\nTask: {task_content}\nParameters: {parameters or {}}\n"
                f"Available tools: {list(self.tools)}")

    def _execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        tool = self.tools[tool_name]
        try:
            tool.validate_input(tool_input)
            result = tool.invoke(tool_input)
        except Exception as exc:
            self.logger.error("tool %s failed: %s", tool_name, exc)
            raise
        self._executed_tools.append(tool_name)
        self.logger.info("tool %s ok", tool_name)
        return result

    def _ask(self, prompt: str) -> str:
        return str(self.model.invoke(prompt).content).strip()

    def process(self, task_content: str, parameters: dict | None = None) -> dict:
        raise NotImplementedError

    async def process_async(self, task_content: str, parameters: dict | None = None) -> dict:
        """Chạy `process` trong luồng riêng để không chặn vòng lặp sự kiện. Lỗi trả về dạng error."""
        self._executed_tools = []
        try:
            return await asyncio.to_thread(self.process, task_content, parameters)
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("task failed")
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    async def serve(self, queue, poll_timeout: float = 1.0) -> None:
        """Vòng lặp của worker trong message queue: nhận task_request, gửi task_result về người gửi."""
        while True:
            try:
                msg = await queue.receive_message(self.name, timeout=poll_timeout)
            except TimeoutError:
                continue
            if msg.get("type") == "shutdown":
                break
            if msg.get("type") != "task_request":
                continue
            result = await self.process_async(msg["content"], msg.get("parameters"))
            await queue.send_message(self.name, msg["from"], {
                "type": "task_result", "task_id": msg["task_id"], "status": result["status"],
                "result": result.get("result"), "error": result.get("error"),
            })
