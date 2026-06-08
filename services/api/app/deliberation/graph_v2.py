"""Supervisor-driven war room graph with PostgreSQL checkpointing."""

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app.config import get_settings
from app.deliberation.checkpointer import get_checkpointer
from app.deliberation.nodes.persist import persist_node
from app.deliberation.nodes.prep import prep_node
from app.deliberation.nodes.specialist import specialist_node
from app.deliberation.nodes.summarizer import summarizer_node
from app.deliberation.nodes.supervisor import supervisor_node
from app.deliberation.state import WarRoomState

settings = get_settings()

_compiled_graph: Any = None


def _route_after_supervisor(
    state: WarRoomState,
) -> Literal["specialist", "summarizer", "persist"]:
    action = state.get("supervisor_action", "call_agent")
    if action == "call_agent":
        return "specialist"
    if action == "finish":
        return "summarizer"
    return "persist"


def _route_after_persist(
    state: WarRoomState,
) -> Literal["supervisor", "__end__"]:
    if state.get("mode") == "followup":
        return END
    if state.get("awaiting_user") or state.get("status") == "awaiting_user":
        return END
    if state.get("status") in ("completed", "partial", "failed"):
        return END
    return "supervisor"


def _route_entry(state: WarRoomState) -> Literal["prep", "supervisor"]:
    if state.get("mode") == "followup":
        return "supervisor"
    if state.get("resume_to_supervisor"):
        return "supervisor"
    return "prep"


def build_war_room_graph() -> StateGraph:
    graph = StateGraph(WarRoomState)

    graph.add_node("prep", prep_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("specialist", specialist_node)
    graph.add_node("summarizer", summarizer_node)
    graph.add_node("persist", persist_node)

    graph.set_conditional_entry_point(_route_entry, {"prep": "prep", "supervisor": "supervisor"})
    graph.add_edge("prep", "supervisor")
    graph.add_conditional_edges("supervisor", _route_after_supervisor)
    graph.add_edge("specialist", "persist")
    graph.add_conditional_edges("persist", _route_after_persist)
    graph.add_edge("summarizer", "persist")

    return graph


async def get_compiled_graph() -> Any:
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph
    checkpointer = await get_checkpointer()
    builder = build_war_room_graph()
    _compiled_graph = builder.compile(checkpointer=checkpointer)
    return _compiled_graph


def graph_config(discussion_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": str(discussion_id)}}
