from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from state import AgentState
from steps import AgentSteps


def after_model(state: AgentState) -> Literal["tool", "__end__"]:
    return "tool" if state["call"] is not None else END


def after_compaction(state: AgentState) -> Literal["approval", "model"]:
    return "approval" if state["pending"] is not None else "model"


def approval(state: AgentState) -> dict:
    approved = interrupt(state["pending"])
    return {"approved": approved}


def build_graph(steps: AgentSteps):
    graph = StateGraph(AgentState)
    graph.add_node("model", steps.decide)
    graph.add_node("tool", steps.handle_tool)
    graph.add_node("compact", steps.compact)
    graph.add_node("approval", approval)
    graph.add_node("resolve", steps.resolve)

    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", after_model)
    graph.add_edge("tool", "compact")
    graph.add_conditional_edges("compact", after_compaction)
    graph.add_edge("approval", "resolve")
    graph.add_edge("resolve", END)
    return graph.compile(checkpointer=InMemorySaver())
