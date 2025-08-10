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


# -------- Orchestrator (LLM) ---------
ORCH_SYSTEM = (
    "You are the Orchestrator for a banking assistant. "
    "Decide which specialized agent to call based on the user's question. "
    "Right now, the only available agent is 'db_agent' for fetching rows from a Supabase database.\n\n"
    "Output strict JSON with keys: action (one of: db_agent, unknown), and if action is db_agent, "
    "include db_query with: {table: 'wellsdummydata', select: array|null, filters: object|null, limit: int|null}.\n"
    "- select should be an array of column names or null for all columns.\n"
    "- filters is a JSON object of equality predicates (e.g., {\"status\": \"active\"}).\n"
    "- limit is an integer or null.\n"
)


def _node_orchestrator_plan(state: AgentState) -> AgentState:
    try:
        from llm_utils import call_anthropic_json

        user_q = state.get("user_input", "")
        if not isinstance(user_q, str) and not isinstance(user_q, dict):
            return {"error": "Unsupported input type"}

        # If caller already provided a db query dict, bypass LLM planning
        if isinstance(user_q, dict) and "table" in user_q:
            return {"db_query": user_q}

        # Use LLM to decide and shape initial db_query
        resp = call_anthropic_json(
            system_prompt=ORCH_SYSTEM,
            user_message=str(user_q),
        )
        action = resp.get("action")
        print("anthropic response: ", resp)
        if action != "db_agent":
            return {"error": "Orchestrator could not route this question to a known agent"}
        db_query = resp.get("db_query") or {}
        if not isinstance(db_query, dict) or not db_query.get("table"):
            return {"error": "Orchestrator did not produce a valid db_query"}
        return {"db_query": db_query}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


# -------- DB Agent (LLM plan -> execute) ---------
DB_PLAN_SYSTEM = (
    "You are the DB Agent for a banking assistant. "
    "Given the user question and an initial db_query proposal, produce a finalized db_query JSON \n"
    "with keys: {table: string, select: array|null, filters: object|null, limit: int|null}. "
    "Only include equality filters. Do not include SQL."
)


def _node_db_agent_plan(state: AgentState) -> AgentState:
    try:
        from llm_utils import call_anthropic_json

        user_q = state.get("user_input", "")
        initial = state.get("db_query", {})
        msg = (
            "User question:\n" + str(user_q) + "\n\n"
            "Initial db_query proposal (may be partial):\n" + str(initial)
        )
        out = call_anthropic_json(
            system_prompt=DB_PLAN_SYSTEM,
            user_message=msg,
        )
        if not isinstance(out, dict) or not out.get("table"):
            return {"error": "DB Agent could not produce a valid db_query"}
        return {"db_query": out}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def _node_db_agent_execute(state: AgentState) -> AgentState:
    if "db_query" not in state:
        return {"error": "Missing db_query for DB agent"}

    try:
        from database_agent import execute_query

        output = execute_query(state["db_query"])  # {"data": [...], "count": int}
        return {"db_result": output}
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
    graph.add_node("db_plan", _node_db_agent_plan)
    graph.add_node("db_execute", _node_db_agent_execute)
    graph.add_node("respond", _node_orchestrator_respond)

    graph.set_entry_point("plan")

    def _route_on_error(state: AgentState) -> str:
        return "error" if "error" in state else "ok"

    # plan -> (error? respond : db_plan)
    graph.add_conditional_edges(
        "plan",
        _route_on_error,
        {"ok": "db_plan", "error": "respond"},
    )

    # db_plan -> (error? respond : db_execute)
    graph.add_conditional_edges(
        "db_plan",
        _route_on_error,
        {"ok": "db_execute", "error": "respond"},
    )

    # db_execute -> respond
    graph.add_edge("db_execute", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


def run_orchestrator(user_input: Any) -> Dict[str, Any]:
    """Run the orchestrator flow with provided user_input (NL or dict)."""
    from typing import cast

    app = build_app()
    initial_state: AgentState = {"user_input": user_input}
    final_state: AgentState = cast(AgentState, app.invoke(initial_state))
    return {k: v for k, v in final_state.items() if k in {"result", "error"}}