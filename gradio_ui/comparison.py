import json
from dataclasses import dataclass
from time import perf_counter

from runner import LabRun


@dataclass
class RunResult:
    workflow: str
    phase: str
    message: str
    pending: dict | None
    events: list[dict]
    elapsed_ms: float

    def sections(self, name: str) -> list:
        return [event["sections"][name] for event in self.events if name in event["sections"]]

    def tool_exchanges(self) -> list[dict]:
        exchanges = []
        for event in self.events:
            sections = event["sections"]
            if request := sections.get("MCP request method and params"):
                exchanges.append({"request": request, "result": None})
            if "MCP result" in sections and exchanges:
                exchanges[-1]["result"] = sections["MCP result"]
        return exchanges

    def model_outputs(self) -> list[list[dict]]:
        return [
            [comparable_output(item) for item in items]
            for items in self.sections("OpenAI output items")
        ]


def comparable_output(item: dict) -> dict:
    output = {key: value for key, value in item.items() if key not in {"id", "call_id"}}
    if output["type"] == "function_call":
        try:
            output["arguments"] = json.loads(output["arguments"])
        except json.JSONDecodeError:
            pass
    return output


async def run_until_review(workflow: str, ticket: str, budget: int) -> RunResult:
    run = LabRun()
    started = perf_counter()
    try:
        await run.start(workflow, ticket, budget, live=True)
        async for _ in run.read():
            pass
    except (OSError, ValueError, TimeoutError):
        run.fail("The connection to the lab worker ended.")
    finally:
        elapsed_ms = (perf_counter() - started) * 1000
        await run.close()
    return RunResult(workflow, run.phase, run.message, run.pending, run.events, elapsed_ms)
