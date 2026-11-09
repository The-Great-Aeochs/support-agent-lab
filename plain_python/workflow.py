from state import AgentState, initial_state
from steps import AgentSteps


async def investigate(steps: AgentSteps, ticket_id: str) -> AgentState:
    state = initial_state(ticket_id)
    while True:
        state.update(await steps.decide(state))
        if state["call"] is None:
            return state

        state.update(await steps.handle_tool(state))
        state.update(steps.compact(state))
        if state["pending"] is not None:
            return state


async def resume(steps: AgentSteps, state: AgentState, approved: bool) -> AgentState:
    state["approved"] = approved
    state.update(await steps.resolve(state))
    return state
