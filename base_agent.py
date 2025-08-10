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
    db_result: Dict[str, Any]
    result: Any
    error: str


# -------- Orchestrator (LLM decides which agent) ---------
ORCH_SYSTEM = (
    "You are the Orchestrator for a banking assistant. "
    "For now, always select the 'db_agent' to answer questions using the database.\n\n"
    "Return JSON: {action: 'db_agent'}"
)


def _node_orchestrator_plan(state: AgentState) -> AgentState:
    try:
        # In this phase, we always choose db_agent. LLM call kept for extensibility.
        from llm_utils import call_anthropic_json

        _ = call_anthropic_json(system_prompt=ORCH_SYSTEM, user_message=str(state.get("user_input", "")))
        return {}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


# -------- DB Agent (fetch + LLM filter) ---------

def _node_db_agent(state: AgentState) -> AgentState:
    try:
        from database_agent import execute_db_agent

        user_q = str(state.get("user_input", ""))
        out = execute_db_agent(user_q)
        if "error" in out:
            return {"error": out["error"]}
        return {"db_result": out}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


# -------- Respond ---------

def _node_orchestrator_respond(state: AgentState) -> AgentState:
    if "error" in state:
        return {"result": {"error": state["error"]}}
    return {"result": state.get("db_result")}


# -------- Build graph ---------

def build_app():
    """Compile and return the LangGraph app linking orchestrator and DB agent."""
    _lazy_imports()
    from langgraph.graph import StateGraph, END

    graph = StateGraph(AgentState)

    graph.add_node("plan", _node_orchestrator_plan)
    graph.add_node("db_agent", _node_db_agent)
    graph.add_node("respond", _node_orchestrator_respond)

    graph.set_entry_point("plan")

    def _route_on_error(state: AgentState) -> str:
        return "error" if "error" in state else "ok"

    graph.add_conditional_edges("plan", _route_on_error, {"ok": "db_agent", "error": "respond"})
    graph.add_conditional_edges("db_agent", _route_on_error, {"ok": "respond", "error": "respond"})

    graph.add_edge("respond", END)
    return graph.compile()


def run_orchestrator(user_input: Any) -> Dict[str, Any]:
    """Run the orchestrator flow with provided user_input (NL)."""
    from typing import cast

    app = build_app()
    initial_state: AgentState = {"user_input": user_input}
    final_state: AgentState = cast(AgentState, app.invoke(initial_state))
    return {k: v for k, v in final_state.items() if k in {"result", "error"}}