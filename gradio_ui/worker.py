import argparse
import asyncio
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

from openai import APIConnectionError, APIStatusError


def failure_message(error: Exception) -> str:
    causes = [error]
    while causes:
        cause = causes.pop()
        if isinstance(cause, APIStatusError):
            return f"OpenAI returned HTTP {cause.status_code}."
        if isinstance(cause, APIConnectionError):
            return "The lab could not connect to OpenAI."
        if isinstance(cause, ExceptionGroup):
            causes.extend(reversed(cause.exceptions))
    return f"The lab stopped with {type(error).__name__}."


def main() -> None:
    sys.path.insert(0, str(Path.cwd()))
    from support_fixtures import TICKETS

    parser = argparse.ArgumentParser()
    parser.add_argument("implementation")
    parser.add_argument("ticket", choices=list(TICKETS))
    parser.add_argument("context_chars", type=int)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    args.max_steps = 6

    from main import run
    from trace_report import Trace, TraceEvent

    protocol_output = sys.stdout

    def send(message_type: str, **data) -> None:
        print(json.dumps({"type": message_type, **data}), file=protocol_output, flush=True)

    def publish(event: TraceEvent) -> None:
        send("trace", kind=event.kind, title=event.title, sections=event.sections)

    def approve(action: dict) -> bool:
        send("approval", action=action)
        return sys.stdin.readline().strip() == "approve"

    trace = Trace(sink=publish)
    trace.record(
        "Run",
        args.implementation + " · " + ("live model" if args.live else "scripted model"),
        {
            "Run settings": {
                "ticket_id": args.ticket,
                "raw_history_budget_chars": args.context_chars,
                "max_model_turns": args.max_steps,
            }
        },
    )
    try:
        with redirect_stdout(sys.stderr):
            answer = asyncio.run(run(args, trace, approve))
    except Exception as error:
        send("error", message=failure_message(error))
    else:
        send("complete", answer=answer)


if __name__ == "__main__":
    main()
