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
    viz_result: Dict[str, Any]
    web_result: Dict[str, Any]
    route: str
    result: Any
    error: str


# -------- Orchestrator (LLM decides which agent) ---------
ORCH_SYSTEM = (
    "You are the Orchestrator for a banking assistant. "
    "Decide which specialized agent to call based on the user's question.\n"
    "Available agents: 'db_agent' (fetch and filter rows), 'viz_agent' (simple chart), and 'web_agent' (web search).\n\n"
    "Respond with JSON only: {action: 'db_agent'|'viz_agent'|'web_agent'}"
)


# Optional observability
try:
    from observability import trace  # type: ignore
except Exception:
    def trace(*args, **kwargs):  # type: ignore
        def _decorator(fn):
            return fn
        return _decorator


@trace(name="node.plan", category="node")
def _node_orchestrator_plan(state: AgentState) -> AgentState:
    user_q = str(state.get("user_input", ""))
    action: Optional[str] = None
    try:
        from llm_utils import call_anthropic_json

        out = call_anthropic_json(system_prompt=ORCH_SYSTEM, user_message=user_q)
        if isinstance(out, dict):
            action = out.get("action")
            # Optional debug logging
            if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
                print("[ORCH] LLM route decision:", out)
    except Exception:
        # Swallow LLM errors and fall back to a simple keyword heuristic
        action = None

    if action not in {"db_agent", "viz_agent", "web_agent"}:
        lower_q = user_q.lower()
        if any(k in lower_q for k in ["visual", "chart", "plot", "graph", "bar chart", "line chart", "visualize", "visualise"]):
            action = "viz_agent"
        elif any(k in lower_q for k in ["search", "google", "web", "news", "latest", "look up", "find online"]):
            action = "web_agent"
        else:
            action = "db_agent"
    if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
        print("[ORCH] Final route:", action)
    return {"route": action}


# -------- DB Agent (fetch + LLM filter) ---------

@trace(name="node.db_agent", category="node")
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


# -------- Viz Agent ---------

@trace(name="node.viz_agent", category="node")
def _node_viz_agent(state: AgentState) -> AgentState:
    try:
        from viz_agent import execute_viz_agent

        user_q = str(state.get("user_input", ""))
        out = execute_viz_agent(user_q)
        if "error" in out:
            return {"error": out["error"]}
        return {"viz_result": out}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


# -------- Web Agent (Tavily) ---------

@trace(name="node.web_agent", category="node")
def _node_web_agent(state: AgentState) -> AgentState:
    try:
        from web_agent import execute_web_agent

        user_q = str(state.get("user_input", ""))
        out = execute_web_agent(user_q)
        if "error" in out:
            return {"error": out["error"]}
        return {"web_result": out}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


# -------- Respond ---------

@trace(name="node.respond", category="node")
def _node_orchestrator_respond(state: AgentState) -> AgentState:
    if "error" in state:
        return {"result": {"error": state["error"]}}
    if "viz_result" in state:
        return {"result": state.get("viz_result")}
    if "web_result" in state:
        return {"result": state.get("web_result")}
    return {"result": state.get("db_result")}


# -------- Build graph ---------

def build_app():
    """Compile and return the LangGraph app linking orchestrator and DB agent."""
    _lazy_imports()
    from langgraph.graph import StateGraph, END

    graph = StateGraph(AgentState)

    graph.add_node("plan", _node_orchestrator_plan)
    graph.add_node("db_agent", _node_db_agent)
    graph.add_node("viz_agent", _node_viz_agent)
    graph.add_node("web_agent", _node_web_agent)
    graph.add_node("respond", _node_orchestrator_respond)

    graph.set_entry_point("plan")

    def _route_from_plan(state: AgentState) -> str:
        if "error" in state:
            return "error"
        action = state.get("route")
        return action or "db_agent"

    def _route_on_error(state: AgentState) -> str:
        return "error" if "error" in state else "ok"

    graph.add_conditional_edges(
        "plan",
        _route_from_plan,
        {"db_agent": "db_agent", "viz_agent": "viz_agent", "web_agent": "web_agent", "error": "respond"},
    )
    graph.add_conditional_edges("db_agent", _route_on_error, {"ok": "respond", "error": "respond"})
    graph.add_conditional_edges("viz_agent", _route_on_error, {"ok": "respond", "error": "respond"})
    graph.add_conditional_edges("web_agent", _route_on_error, {"ok": "respond", "error": "respond"})

    graph.add_edge("respond", END)
    return graph.compile()


@trace(name="orchestrator.run", category="orchestrator")
def run_orchestrator(user_input: Any) -> Dict[str, Any]:
    """Run the orchestrator flow with provided user_input (NL)."""
    from typing import cast

    app = build_app()
    initial_state: AgentState = {"user_input": user_input}
    final_state: AgentState = cast(AgentState, app.invoke(initial_state))
    return {k: v for k, v in final_state.items() if k in {"result", "error"}}