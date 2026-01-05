from __future__ import annotations

# REVIEW-FIX: Safe sync wrapper parity; resilient thread/loop lifecycle.

import asyncio
import threading
import warnings
from concurrent.futures import Future
from typing import Any, Coroutine

from langchain.tools import BaseTool

from cuga.mcp.adapters.mcp_tool import MCPToolHandle
from cuga.mcp.interfaces import ToolRequest


class AsyncWorker:
    """Async worker running a dedicated event loop."""

    def __init__(self, loop_ready_timeout: float = 5.0) -> None:
        self._instance_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_ready = threading.Event()
        self._stopping = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if not self._loop_ready.wait(timeout=loop_ready_timeout):
            with self._instance_lock:
                self._stopping = True
            self._thread.join(timeout=1)
            warnings.warn("AsyncWorker loop did not start within timeout")
            raise RuntimeError("AsyncWorker loop failed to start")

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        with self._instance_lock:
            return self._get_loop_locked()

    def _get_loop_locked(self) -> asyncio.AbstractEventLoop:
        if self._stopping:
            raise RuntimeError("AsyncWorker is stopping")

        loop = self._loop
        if loop is None or loop.is_closed() or not self._loop_ready.is_set():
            raise RuntimeError("AsyncWorker loop is not running")
        return loop

    def submit(self, coro: Coroutine[Any, Any, Any]) -> Future[Any]:
        """Submit coroutine to the shared loop."""

        with self._instance_lock:
            loop = self._get_loop_locked()
            return asyncio.run_coroutine_threadsafe(coro, loop)

    def stop(self) -> None:
        with self._instance_lock:
            if self._stopping:
                return
            self._stopping = True
            loop = self._loop
            if loop and not loop.is_closed():
                loop.call_soon_threadsafe(loop.stop)

        self._thread.join(timeout=1)
        if self._thread.is_alive():
            warnings.warn("AsyncWorker thread did not terminate within timeout")
            return

        with self._instance_lock:
            self._loop = None
            self._loop_ready.clear()

    @property
    def _is_running(self) -> bool:
        with self._instance_lock:
            return (
                self._loop_ready.is_set()
                and self._loop is not None
                and not self._loop.is_closed()
                and not self._stopping
            )

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        with self._instance_lock:
            self._loop = loop
            asyncio.set_event_loop(loop)
            self._loop_ready.set()
        try:
            loop.run_forever()
        finally:
            tasks = asyncio.all_tasks(loop)
            if tasks:
                for task in tasks:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
            with self._instance_lock:
                self._loop_ready.clear()
                self._stopping = True


class LangChainMCPTool(BaseTool):
    name: str
    description: str = "MCP tool"

    def __init__(
        self, handle: MCPToolHandle, description: str = "MCP tool", worker: AsyncWorker | None = None
    ):
        super().__init__()
        self.handle = handle
        self.name = handle.alias
        self.description = description
        self._owned_worker = worker is None
        self.worker = worker or AsyncWorker()

    def _run(self, tool_input: str, run_manager=None):  # type: ignore[override]
        coro = self._arun(tool_input, run_manager)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result = self.worker.submit(coro)
        try:
            return result.result()
        except KeyboardInterrupt:
            result.cancel()
            raise

    def close(self) -> None:
        if self._owned_worker:
            self.worker.stop()

    async def _arun(self, tool_input: str, run_manager=None):  # type: ignore[override]
        req = ToolRequest(method="invoke", params={"input": tool_input})
        resp = await self.handle.call(req)
        if resp.ok:
            return resp.result
        raise RuntimeError(resp.error or "unknown MCP error")
