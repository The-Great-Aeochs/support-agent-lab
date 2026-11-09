import json
from typing import TypedDict


class ToolCall(TypedDict):
    id: str
    name: str
    arguments: str


class Exchange(TypedDict):
    call: ToolCall
    result: dict[str, str]


class Escalation(TypedDict):
    ticket_id: str
    team: str
    reason: str


class AgentState(TypedDict):
    ticket_id: str
    steps: int
    history: list[Exchange]
    summaries: dict[str, dict[str, str]]
    call: ToolCall | None
    pending: Escalation | None
    approved: bool | None
    answer: str


def initial_state(ticket_id: str) -> AgentState:
    return {
        "ticket_id": ticket_id,
        "steps": 0,
        "history": [],
        "summaries": {},
        "call": None,
        "pending": None,
        "approved": None,
        "answer": "",
    }


SUMMARY_FIELDS = {
    "get_ticket": ("summary", "severity", "runbook"),
    "get_runbook": ("summary", "team"),
}


def summarize(exchange: Exchange) -> dict[str, str]:
    result = exchange["result"]
    fields = ("error",) if "error" in result else SUMMARY_FIELDS[exchange["call"]["name"]]
    return {key: result[key][:240] for key in fields}


def history_chars(history: list[Exchange]) -> int:
    return len(json.dumps(history, ensure_ascii=False))


def compact_context(state: AgentState, budget: int) -> dict:
    history = state["history"].copy()
    summaries = state["summaries"].copy()
    while history and history_chars(history) > budget:
        oldest = history.pop(0)
        name = oldest["call"]["name"]
        key = name if name in SUMMARY_FIELDS else "last_tool_error"
        summaries[key] = summarize(oldest)
    return {"history": history, "summaries": summaries}


def latest_tool_facts(state: AgentState) -> dict[str, dict[str, str]]:
    facts = state["summaries"].copy()
    for exchange in state["history"]:
        facts[exchange["call"]["name"]] = exchange["result"]
    return facts
