from __future__ import annotations

from typing import Any, Dict, Optional, TypedDict

import os


def _require_dependency(import_name: str, pip_name: Optional[str] = None) -> None:
    try:
        __import__(import_name)
    except ImportError as exc:
        pkg = pip_name or import_name
        raise ImportError(
            f"Missing optional dependency '{import_name}'. Install with: pip install {pkg}"
        ) from exc


def _lazy_imports() -> None:
    _require_dependency("langgraph")


class AgentState(TypedDict, total=False):
    user_input: Any
    db_query: Dict[str, Any]
    db_result: Dict[str, Any]
    result: Any
    error: str


def _node_orchestrator_plan(state: AgentState) -> AgentState:
    """Plan next action from user_input.

    For now, expect either a dict that already represents a DB query or a
    structured state containing 'db_query'. If natural language is provided,
    we return an error (placeholder for future NL->Query planning).
    """
    if "db_query" in state and isinstance(state["db_query"], dict):
        return {}

    user_input = state.get("user_input")
    if isinstance(user_input, dict) and "table" in user_input:
        return {"db_query": user_input}

    return {"error": "Planner cannot interpret user_input. Provide a DB query dict for now."}


def _node_db_agent(state: AgentState) -> AgentState:
    if "db_query" not in state:
        return {"error": "Missing db_query for DB agent"}

    try:
        from database_agent import execute_query

        output = execute_query(state["db_query"])  # {"data": [...], "count": int}
        return {"db_result": output}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def _node_orchestrator_respond(state: AgentState) -> AgentState:
    if "error" in state:
        return {"result": {"error": state["error"]}}
    return {"result": state.get("db_result")}


def build_app():
    """Compile and return the LangGraph app linking orchestrator and DB agent."""
    _lazy_imports()
    from langgraph.graph import StateGraph, END

    graph = StateGraph(AgentState)

    graph.add_node("plan", _node_orchestrator_plan)
    graph.add_node("db_agent", _node_db_agent)
    graph.add_node("respond", _node_orchestrator_respond)

    graph.set_entry_point("plan")

    # plan -> db_agent -> respond -> END
    graph.add_edge("plan", "db_agent")
    graph.add_edge("db_agent", "respond")
    graph.add_edge("respond", END)

    return graph.compile()


def run_orchestrator(user_input: Any) -> Dict[str, Any]:
    """Run the orchestrator flow with provided user_input.

    If user_input is a dict describing a DB query, the DB agent will be invoked.
    Returns a dict with {"result": ..., "error": ...?}
    """
    app = build_app()
    initial_state: AgentState = {"user_input": user_input}
    final_state: AgentState = app.invoke(initial_state)
    return {k: v for k, v in final_state.items() if k in {"result", "error"}}