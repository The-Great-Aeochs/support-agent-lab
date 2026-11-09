import asyncio
import json
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
LABS = {"Plain Python": "plain_python", "LangGraph": "langgraph_version"}


@dataclass
class LabRun:
    events: list[dict] = field(default_factory=list)
    process: asyncio.subprocess.Process | None = None
    pending: dict | None = None
    phase: str = "running"
    message: str = "The agent is investigating the ticket."
    expiry: asyncio.Task | None = None

    async def start(self, implementation: str, ticket: str, budget: int, live: bool) -> None:
        command = [
            sys.executable,
            "-B",
            str(Path(__file__).with_name("worker.py")),
            implementation,
            ticket,
            str(budget),
        ]
        if live:
            command.append("--live")
        self.process = await asyncio.create_subprocess_exec(
            *command,
            cwd=LAB_ROOT / LABS[implementation],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=1024 * 1024,
        )

    async def read(self) -> AsyncIterator[None]:
        assert self.process is not None and self.process.stdout is not None
        while line := await asyncio.wait_for(self.process.stdout.readline(), timeout=120):
            data = json.loads(line)
            message_type = data.pop("type")
            if message_type == "trace":
                self.events.append(data)
            elif message_type == "approval":
                self.pending = data["action"]
                self.phase = "approval"
                self.message = "Review the proposed action before the agent can continue."
            elif message_type == "complete":
                self.phase = "complete"
                self.message = data["answer"]
            elif message_type == "error":
                self.phase = "error"
                self.message = data["message"]
            yield
            if message_type != "trace":
                return
        self.fail("The lab worker exited before returning a result.")
        yield

    async def decide(self, approved: bool) -> None:
        assert self.phase == "approval" and self.pending is not None
        assert self.process is not None and self.process.stdin is not None
        self.phase = "running"
        self.pending = None
        self.message = "The agent is resuming with your decision."
        if self.expiry is not None:
            self.expiry.cancel()
        self.process.stdin.write(b"approve\n" if approved else b"decline\n")
        await self.process.stdin.drain()

    def fail(self, message: str) -> None:
        self.phase = "error"
        self.pending = None
        self.message = message

    async def close(self) -> None:
        if self.process is None:
            return
        if self.process.stdin is not None:
            self.process.stdin.close()
        if self.process.returncode is not None:
            return
        try:
            await asyncio.wait_for(self.process.wait(), timeout=2)
        except TimeoutError:
            try:
                self.process.kill()
            except ProcessLookupError:
                pass
            await self.process.wait()
