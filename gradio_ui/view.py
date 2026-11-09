import json
from html import escape

import gradio as gr

STAGES = ["All", "Model", "MCP", "Context", "Approval", "Run", "Tool"]
EMPTY_TRACE = """
<div class="trace-empty">
  <h3>Each decision has a trace</h3>
  <p>Run ticket #42 to inspect the model request, follow the MCP calls, and
  see what the agent keeps when its context budget fills up.</p>
</div>
"""


def event_detail(events: list[dict], selected: int | None) -> str:
    if selected is None or not 0 <= selected < len(events):
        return EMPTY_TRACE
    event = events[selected]
    sections = []
    for label, value in event["sections"].items():
        text = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)
        opened = "" if label in {
            "Full request body",
            "Tool definitions · names, descriptions, and schemas",
        } else " open"
        sections.append(
            f'<details{opened}><summary>{escape(label)}</summary>'
            f'<pre tabindex="0">{escape(text)}</pre></details>'
        )
    kind = escape(event["kind"].lower())
    ticket_id = events[0]["sections"].get("Run settings", {}).get("ticket_id")
    ticket_label = f" · Ticket #{escape(ticket_id)}" if ticket_id else ""
    return (
        f'<article class="event-detail {kind}"><p class="event-kicker">'
        f'{selected + 1:02} · {escape(event["kind"])}{ticket_label}</p>'
        f'<h3>{escape(event["title"])}</h3>'
        f'<div class="event-sections">{"".join(sections)}</div></article>'
    )


def select_events(
    events: list[dict], stage: str, *, prefer_model: bool = False
) -> tuple[dict, str]:
    choices = [
        (f'{index + 1:02} · {event["kind"]} · {event["title"]}', index)
        for index, event in enumerate(events)
        if stage == "All" or event["kind"] == stage
    ]
    selected = choices[-1][1] if choices else None
    if prefer_model and stage in {"All", "Model"}:
        selected = next(
            (
                index for _, index in reversed(choices)
                if "Full request body" in events[index]["sections"]
            ),
            selected,
        )
    detail = event_detail(events, selected)
    if events and selected is None:
        detail = '<div class="trace-empty"><p>No events in this stage yet.</p></div>'
    return gr.update(choices=choices, value=selected), detail


def status(phase: str, message: str) -> str:
    label = {
        "ready": "Ready",
        "setup": "OpenAI setup required",
        "running": "Running",
        "approval": "Awaiting approval",
        "complete": "Complete",
        "error": "Run stopped",
    }[phase]
    return (
        f'<div class="run-status {phase}" role="status" aria-live="polite">'
        f'<strong>{label}</strong><p>{escape(message)}</p></div>'
    )


def proposal(action: dict | None) -> str:
    if action is None:
        return ""
    fields = (
        ("Ticket", "#" + action["ticket_id"]),
        ("Team", action["team"]),
        ("Reason", action["reason"]),
    )
    return "<dl>" + "".join(
        f"<dt>{label}</dt><dd>{escape(value)}</dd>" for label, value in fields
    ) + "</dl>"
