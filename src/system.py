"""MultiAgentSystem: nối Coordinator, ba worker (qua message queue) và các tool.

    async with MultiAgentSystem() as system:
        response = await system.process("Calculate revenue and create chart")

Mỗi worker chạy một vòng lặp `serve()` trong nền. Coordinator gọi worker qua `QueueWorkerProxy`,
nên mọi yêu cầu giữa coordinator và worker đều đi qua MessageQueue và được ghi vào logs/communication.log.
"""
import asyncio
import json
from pathlib import Path

from .agents import CodeAgent, DataAgent, EvaluatorAgent
from .communication import MessageQueue, QueueWorkerProxy
from .coordinator import Coordinator
from .llm import make_llm
from .sample_data import SCHEMA
from .tools.code_tools import CreateFileTool, EditFileTool, PythonREPLTool
from .tools.database_tools import QueryDatabaseTool
from .tools.evaluation_tools import ScoringTool, ValidationTool

ROOT = Path(__file__).resolve().parents[1]


class MultiAgentSystem:
    def __init__(self, model=None, db_path: str | Path | None = None, output_dir: str | Path | None = None,
                 timeout: float = 60, max_retries: int = 2):
        self.model = model if model is not None else make_llm()
        db_path = Path(db_path) if db_path else ROOT / "data" / "sales.db"
        output_dir = Path(output_dir) if output_dir else ROOT / "outputs"
        self.queue = MessageQueue()
        self.agents = {
            "data_agent": DataAgent(self.model, [QueryDatabaseTool(db_path)], schema=SCHEMA),
            "code_agent": CodeAgent(self.model, [PythonREPLTool(), CreateFileTool(output_dir),
                                                 EditFileTool(output_dir)],
                                    db_path=str(db_path.resolve()), output_dir=str(output_dir.resolve())),
            "evaluator_agent": EvaluatorAgent(self.model, [ScoringTool(), ValidationTool()]),
        }
        for name in self.agents:
            self.queue.register_agent(name)
        proxies = [QueueWorkerProxy(name, self.queue, reply_timeout=timeout + 10) for name in self.agents]
        self.coordinator = Coordinator(model=self.model, workers=proxies, timeout=timeout, max_retries=max_retries)
        self._servers: list[asyncio.Task] = []

    async def __aenter__(self):
        self._servers = [asyncio.create_task(agent.serve(self.queue)) for agent in self.agents.values()]
        return self

    async def __aexit__(self, *exc):
        for task in self._servers:
            task.cancel()
        await asyncio.gather(*self._servers, return_exceptions=True)
        self._servers = []

    async def process(self, request: str, debug: bool = False) -> dict:
        if not self._servers:
            raise RuntimeError("start the system with 'async with MultiAgentSystem() as system:'")
        response = await self.coordinator.handle_request(request)
        if debug:
            print(json.dumps(response, ensure_ascii=False, indent=2, default=str))
        return response
