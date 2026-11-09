import argparse
import asyncio
import json
import os
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from langgraph.types import Command

from models import open_model
from state import Escalation, initial_state
from steps import AgentSteps
from support_fixtures import TICKETS
from tools import connect_tools, model_tools
from trace_report import Trace
from workflow import build_graph


def request_approval(action: Escalation) -> bool:
    print("\nProposed escalation")
    print(json.dumps(action, indent=2))
    try:
        return input("Approve this exact action? [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


async def run(
    args: argparse.Namespace,
    trace: Trace,
    approve: Callable[[Escalation], bool] = request_approval,
) -> str:
    async with open_model(args.live, trace) as model, connect_tools() as session:
        definitions = await model_tools(session, trace)
        steps = AgentSteps(model, session, definitions, args.max_steps, args.context_chars, trace)
        graph = build_graph(steps)
        config = {
            "configurable": {"thread_id": str(uuid4())},
            "recursion_limit": 3 * args.max_steps + 4,
        }
        state = await graph.ainvoke(initial_state(args.ticket), config)
        if pauses := state.get("__interrupt__"):
            approved = approve(pauses[0].value)
            state = await graph.ainvoke(Command(resume=approved), config)
        trace.record(
            "Run", "Run complete", {"Answer": state["answer"], "Model turns": state["steps"]}
        )
        print(f'\n{state["answer"]}')
        return state["answer"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Investigate a demo support ticket.")
    parser.add_argument("--ticket", choices=list(TICKETS), default="42")
    parser.add_argument("--context-chars", type=int, default=1200)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--live", action="store_true", help="Use the OpenAI API")
    parser.add_argument("--trace", type=Path, metavar="FILE.html", help="Write a local HTML trace")
    args = parser.parse_args()
    if args.context_chars < 2 or args.max_steps < 1:
        parser.error("--context-chars must be at least 2 and --max-steps at least 1")
    if args.live and not os.getenv("OPENAI_API_KEY"):
        parser.error("--live requires OPENAI_API_KEY")
    if args.trace and args.trace.suffix.lower() != ".html":
        parser.error("--trace requires a path ending in .html")
    with Trace(args.trace) as trace:
        trace.record(
            "Run",
            "LangGraph · " + ("live model" if args.live else "scripted model"),
            {
                "Run settings": {
                    "ticket_id": args.ticket,
                    "raw_history_budget_chars": args.context_chars,
                    "max_model_turns": args.max_steps,
                }
            },
        )
        asyncio.run(run(args, trace))


if __name__ == "__main__":
    main()
