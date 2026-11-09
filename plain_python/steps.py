from mcp import ClientSession

from models import Model
from state import AgentState, compact_context, history_chars
from tools import READ_TOOLS, call_arguments, call_mcp, escalation_proposal
from trace_report import Trace


class AgentSteps:
    def __init__(
        self,
        model: Model,
        session: ClientSession,
        tools: list[dict],
        max_steps: int,
        context_chars: int,
        trace: Trace | None = None,
    ) -> None:
        self.model = model
        self.session = session
        self.tools = tools
        self.max_steps = max_steps
        self.context_chars = context_chars
        self.trace = trace if trace is not None else Trace()

    async def decide(self, state: AgentState) -> dict:
        if state["steps"] >= self.max_steps:
            self.trace.record("Model", "Step limit reached", {"Model turns": state["steps"]})
            return {"call": None, "answer": "Stopped at the model step limit."}

        turn = state["steps"] + 1
        print(f"Model turn {turn}")
        decision = await self.model.decide(state, self.tools)
        if isinstance(decision, str):
            self.trace.record("Model", f"Turn {turn} · Answer returned", {"Answer": decision})
            return {"steps": turn, "call": None, "answer": decision}
        self.trace.record(
            "Model", f'Turn {turn} · Request {decision["name"]}', {"Function call": decision}
        )
        return {"steps": turn, "call": decision}

    async def handle_tool(self, state: AgentState) -> dict:
        call = state["call"]
        assert call is not None
        name = call["name"]
        try:
            arguments = call_arguments(call)
            if name == "propose_escalation":
                pending = escalation_proposal(state["ticket_id"], arguments)
                self.trace.record(
                    "Approval",
                    "Save proposal locally and pause before the write",
                    {"Model call ID": call["id"], "Pending action": pending},
                )
                return {"call": None, "pending": pending}
            if name not in READ_TOOLS:
                raise ValueError(f"Tool is unavailable to the model: {name}")
            if name == "get_ticket" and arguments != {"ticket_id": state["ticket_id"]}:
                raise ValueError("The agent may only read the ticket assigned to this run")
            result = await call_mcp(
                self.session, name, arguments, trace=self.trace, model_call_id=call["id"]
            )
        except ValueError as error:
            result = {"error": str(error)}
            self.trace.record(
                "Tool", f"Reject {name}", {"Model call ID": call["id"], "Tool result": result}
            )
        exchange = {"call": call, "result": result}
        return {"call": None, "history": [*state["history"], exchange]}

    def compact(self, state: AgentState) -> dict:
        update = compact_context(state, self.context_chars)
        removed = len(state["history"]) - len(update["history"])
        if removed:
            print(f"Compacted {removed} tool exchange(s).")
        if self.trace.enabled:
            before_chars = history_chars(state["history"])
            after_chars = history_chars(update["history"])
            self.trace.record(
                "Context",
                f"Raw history {before_chars:,} → {after_chars:,} chars · {removed} compacted",
                {
                    "Budget for raw history": {"characters": self.context_chars},
                    "Before · raw exchanges and compacted facts": {
                        "history": state["history"],
                        "summaries": state["summaries"],
                    },
                    "After · raw exchanges and compacted facts": update,
                    "Pinned application state": {
                        "ticket_id": state["ticket_id"],
                        "pending": state["pending"],
                        "approved": state["approved"],
                    },
                },
            )
        return update

    async def resolve(self, state: AgentState) -> dict:
        pending, approved = state["pending"], state["approved"]
        if pending is None or type(approved) is not bool:
            raise ValueError("Resolution requires a pending action and a boolean decision")
        self.trace.record(
            "Approval",
            "Resume · approved" if approved else "Resume · declined",
            {"Decision and reviewed action": {"approved": approved, "action": pending}},
        )
        if approved:
            result = await call_mcp(self.session, "escalate_ticket", dict(pending), trace=self.trace)
            if "error" in result:
                answer = f'Escalation failed: {result["error"]}'
            else:
                answer = f'Created {result["escalation_id"]} for {pending["team"]}.'
        else:
            answer = f'Escalation declined. Ticket #{pending["ticket_id"]} was left unchanged.'
        return {"pending": None, "answer": answer}
