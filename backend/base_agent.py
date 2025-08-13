from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict
from pathlib import Path
import os

# Optional observability import before usage
try:
    from eval_server.observability import trace  # type: ignore
except Exception:
    def trace(*args, **kwargs):  # type: ignore
        def _decorator(fn):
            return fn
        return _decorator


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
    original_user_input: Any
    current_query: str
    db_result: Dict[str, Any]
    viz_result: Dict[str, Any]
    web_result: Dict[str, Any]
    route: str
    result: Any
    error: str
    guardrails_passed: bool
    step_count: int
    workflow_plan: List[str]
    current_step_index: int


# -------- Multi-Step Orchestrator ---------
WORKFLOW_PLANNING_SYSTEM = (
    "You are a workflow planning assistant for a banking data analysis system. "
    "Given a user's request, determine if it requires multiple steps and plan the workflow.\n"
    "Available agents:\n"
    "- 'web_agent': Search for external information (interest rates, news, regulations, etc.)\n"
    "- 'db_agent': Query and filter banking transaction data\n"
    "- 'viz_agent': Create charts and visualizations from data\n\n"
    "Analyze the request and decide:\n"
    "1. If it needs multiple steps (e.g., search for context then analyze data, or get data then visualize)\n"
    "2. What sequence of agents to use\n\n"
    "Respond with JSON only:\n"
    "{\n"
    "  \"workflow\": [\"agent1\", \"agent2\", ...],\n"
    "  \"reasoning\": \"brief explanation\"\n"
    "}\n\n"
    "Examples:\n"
    "- \"Show me my spending compared to inflation rates\" → [\"web_agent\", \"db_agent\", \"viz_agent\"]\n"
    "- \"Visualize my monthly expenses\" → [\"db_agent\", \"viz_agent\"]\n"
    "- \"What are current mortgage rates?\" → [\"web_agent\"]\n"
    "- \"How much did I spend on groceries?\" → [\"db_agent\"]"
)

QUERY_REFINEMENT_SYSTEM = (
    "You are a query refinement assistant. Based on previous results, refine the user's query for the next step.\n"
    "Make the query more specific and actionable for the next agent, incorporating insights from previous steps.\n\n"
    "Respond with JSON only: {\"refined_query\": \"the refined query string\"}"
)

@trace(name="node.plan_workflow", category="node")
def _node_plan_workflow(state: AgentState) -> AgentState:
    user_q = str(state.get("user_input", ""))
    
    # Initialize workflow state
    if "step_count" not in state:
        try:
            from llm_utils import call_anthropic_json
            
            out = call_anthropic_json(system_prompt=WORKFLOW_PLANNING_SYSTEM, user_message=user_q)
            if isinstance(out, dict) and "workflow" in out:
                workflow = out.get("workflow", [])
                reasoning = out.get("reasoning", "")
                
                if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
                    print(f"[WORKFLOW] Planned steps: {workflow}, reasoning: {reasoning}")
                
                return {
                    "original_user_input": user_q,
                    "current_query": user_q,
                    "workflow_plan": workflow,
                    "current_step_index": 0,
                    "step_count": 0,
                    "route": workflow[0] if workflow else "db_agent"
                }
        except Exception:
            if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
                print("[WORKFLOW] Planning failed, using single-step fallback")
        
        # Fallback to single-step heuristic
        lower_q = user_q.lower()
        if any(k in lower_q for k in ["visual", "chart", "plot", "graph", "bar chart", "line chart", "visualize", "visualise"]):
            if any(k in lower_q for k in ["compare", "vs", "versus", "against", "trend", "over time"]):
                workflow = ["web_agent", "db_agent", "viz_agent"]
            else:
                workflow = ["db_agent", "viz_agent"]
        elif any(k in lower_q for k in ["search", "google", "web", "news", "latest", "look up", "find online", "rate", "market", "economy"]):
            workflow = ["web_agent"]
        else:
            workflow = ["db_agent"]
        
        return {
            "original_user_input": user_q,
            "current_query": user_q,
            "workflow_plan": workflow,
            "current_step_index": 0,
            "step_count": 0,
            "route": workflow[0]
        }
    
    # Continue with existing workflow
    step_count = state.get("step_count", 0)
    workflow = state.get("workflow_plan", [])
    current_index = state.get("current_step_index", 0)
    
    if current_index >= len(workflow):
        return {"route": "respond"}
    
    next_agent = workflow[current_index]
    
    # Refine query based on previous results if this isn't the first step
    current_query = str(state.get("current_query", state.get("user_input", "")))
    if step_count > 0:
        try:
            from llm_utils import call_anthropic_json
            
            # Build context from previous results
            context_parts = []
            if "web_result" in state and state["web_result"]:
                web_ans = (state["web_result"] or {}).get("answer", "")
                if web_ans:
                    context_parts.append(f"Web search found: {web_ans}")
            
            if "db_result" in state and state["db_result"]:
                count = (state["db_result"] or {}).get("count", 0)
                context_parts.append(f"Database query returned {count} relevant records")
            
            context = "\n".join(context_parts) if context_parts else "No previous results"
            
            refinement_prompt = (
                f"Original user request: {state.get('original_user_input')}\n"
                f"Previous results: {context}\n"
                f"Next step: {next_agent}\n"
                f"Current query: {current_query}\n\n"
                f"Refine the query for the {next_agent} based on what we've learned:"
            )
            
            out = call_anthropic_json(system_prompt=QUERY_REFINEMENT_SYSTEM, user_message=refinement_prompt)
            if isinstance(out, dict) and "refined_query" in out:
                current_query = out["refined_query"]
                
                if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
                    print(f"[WORKFLOW] Refined query for {next_agent}: {current_query}")
        except Exception:
            if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
                print("[WORKFLOW] Query refinement failed, using original")
    
    return {
        "route": next_agent,
        "current_query": current_query
    }


# -------- DB Agent (fetch + LLM filter) ---------

@trace(name="node.db_agent", category="node")
def _node_db_agent(state: AgentState) -> AgentState:
    try:
        from backend.database_agent import execute_db_agent

        # Use current_query if available, fallback to user_input
        query = str(state.get("current_query", state.get("user_input", "")))
        out = execute_db_agent(query)
        if "error" in out:
            return {"error": out["error"]}
        
        # Increment step tracking
        current_step = state.get("current_step_index", 0)
        step_count = state.get("step_count", 0)
        
        return {
            "db_result": out,
            "current_step_index": current_step + 1,
            "step_count": step_count + 1
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


# -------- Viz Agent ---------

@trace(name="node.viz_agent", category="node")
def _node_viz_agent(state: AgentState) -> AgentState:
    try:
        from backend.viz_agent import execute_viz_agent

        # Use current_query if available, fallback to user_input
        query = str(state.get("current_query", state.get("user_input", "")))
        out = execute_viz_agent(query)
        if "error" in out:
            return {"error": out["error"]}
        
        # Increment step tracking
        current_step = state.get("current_step_index", 0)
        step_count = state.get("step_count", 0)
        
        return {
            "viz_result": out,
            "current_step_index": current_step + 1,
            "step_count": step_count + 1
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


# -------- Guardrails Agent ---------

GUARDRAILS_SYSTEM = (
    "You are a content guardrails agent for a personal banking assistant. "
    "Your job is to determine if a user's request is related to personal finance, banking, or money management.\n"
    "Personal finance topics include: banking, investments, spending, budgeting, loans, credit, savings, "
    "financial planning, transactions, accounts, payments, financial markets, economic indicators, etc.\n\n"
    "Respond with JSON only: {\"allowed\": true|false, \"reason\": \"brief explanation\"}"
)

@trace(name="node.guardrails", category="node")
def _node_guardrails(state: AgentState) -> AgentState:
    # Use current_query if available, fallback to user_input
    query = str(state.get("current_query", state.get("user_input", "")))
    
    try:
        from llm_utils import call_anthropic_json
        
        out = call_anthropic_json(system_prompt=GUARDRAILS_SYSTEM, user_message=query)
        if isinstance(out, dict):
            allowed = out.get("allowed", False)
            reason = out.get("reason", "")
            
            if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
                print("[GUARDRAILS] Decision:", out)
            
            if not allowed:
                return {
                    "error": f"I'm a personal finance assistant and can only help with banking and financial topics. {reason} Please ask me about your banking data, spending patterns, or financial information instead."
                }
            
            return {"guardrails_passed": True}
    except Exception:
        # If guardrails check fails, err on the side of caution for web searches
        # but allow the request to proceed to avoid blocking legitimate requests
        if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
            print("[GUARDRAILS] Check failed, allowing request")
        return {"guardrails_passed": True}

# -------- Web Agent (Tavily) ---------

@trace(name="node.web_agent", category="node")
def _node_web_agent(state: AgentState) -> AgentState:
    try:
        from eval_server.web_agent import execute_web_agent

        # Use current_query if available, fallback to user_input
        query = str(state.get("current_query", state.get("user_input", "")))
        out = execute_web_agent(query)
        if "error" in out:
            return {"error": out["error"]}
        
        # Increment step tracking
        current_step = state.get("current_step_index", 0)
        step_count = state.get("step_count", 0)
        
        return {
            "web_result": out,
            "current_step_index": current_step + 1,
            "step_count": step_count + 1
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


# -------- Respond ---------

@trace(name="node.respond", category="node")
def _node_orchestrator_respond(state: AgentState) -> AgentState:
    if "error" in state:
        return {"result": {"error": state["error"]}}

    user_q = str(state.get("user_input", ""))

    # Build a compact context from available results
    context_parts = []

    if "db_result" in state and state["db_result"]:
        db_res = state["db_result"] or {}
        rows = db_res.get("rows") or []
        count = db_res.get("count") or len(rows)
        preview = rows[:10]
        try:
            import json as _json
            preview_json = _json.dumps(preview, default=str)
        except Exception:
            preview_json = str(preview)
        context_parts.append(f"DB rows ({min(len(preview), count)}/{count} shown):\n{preview_json}")

    if "viz_result" in state and state["viz_result"]:
        viz = state["viz_result"] or {}
        spec = viz.get("spec") or {}
        chartjs = viz.get("chartjs") or {}
        labels = ((chartjs.get("data") or {}).get("labels") or [])[:10]
        datasets = (chartjs.get("data") or {}).get("datasets") or []
        first_ds = datasets[0] if datasets else {}
        values = (first_ds.get("data") or [])[:10]
        context_parts.append(f"Chart spec: {spec}. Sample labels: {labels}. Sample values: {values}.")

    if "web_result" in state and state["web_result"]:
        web = state["web_result"] or {}
        web_ans = web.get("answer") or ""
        context_parts.append(f"Web answer (if any): {web_ans}")
        sources = web.get("sources") or []
        if sources:
            src_lines = []
            for i, s in enumerate(sources[:5], 1):
                t = s.get("title") or ""
                u = s.get("url") or ""
                snippet = (s.get("snippet") or "")[:200]
                src_lines.append(f"[{i}] {t} - {u} - {snippet}")
            context_parts.append("Sources:\n" + "\n".join(src_lines))

    ctx = "\n\n".join(context_parts) if context_parts else "(No structured data.)"

    # Ask the LLM for a concise answer that uses the data
    answer = ""
    try:
        from llm_utils import call_anthropic
        
        # Get original user input for context
        original_q = str(state.get("original_user_input", user_q))
        step_count = state.get("step_count", 0)
        
        system_prompt = (
            "You are an expert banking assistant. Use the provided data to answer the user's "
            "question clearly and concisely in 3-6 sentences. If a visualization is present, "
            "describe the key insight. If web sources are present, incorporate key facts. "
            f"This analysis involved {step_count} steps to gather comprehensive information. "
            "Synthesize all the data to provide a complete answer. Do not invent data."
        )
        user_message = f"Original user question:\n{original_q}\n\nGathered data from multi-step analysis:\n{ctx}\n\nFinal comprehensive answer:"
        answer = call_anthropic(system_prompt=system_prompt, user_message=user_message, max_tokens=500, temperature=0.2)
    except Exception:
        # Graceful fallback when LLM is unavailable
        if "web_result" in state and (state["web_result"] or {}).get("answer"):
            answer = (state["web_result"] or {}).get("answer") or ""
        elif "db_result" in state:
            cnt = (state["db_result"] or {}).get("count") or len((state["db_result"] or {}).get("rows") or [])
            answer = f"I found {cnt} matching rows for your question."
        else:
            answer = "I could not generate a natural language answer due to missing LLM credentials."

    # Combine all outputs; keep original shapes so UI components still work
    payload: Dict[str, Any] = {"answer": answer}
    if "viz_result" in state and state["viz_result"]:
        payload.update(state["viz_result"])  # keeps chartjs/spec at top-level for the UI
    if "web_result" in state and state["web_result"]:
        payload["web"] = state["web_result"]
    if "db_result" in state and state["db_result"]:
        payload["db"] = state["db_result"]

    return {"result": payload}


# -------- Build graph ---------

def build_app():
    """Compile and return the LangGraph app linking orchestrator and DB agent."""
    _lazy_imports()
    from langgraph.graph import StateGraph, END

    graph = StateGraph(AgentState)

    graph.add_node("plan_workflow", _node_plan_workflow)
    graph.add_node("guardrails", _node_guardrails)
    graph.add_node("db_agent", _node_db_agent)
    graph.add_node("viz_agent", _node_viz_agent)
    graph.add_node("web_agent", _node_web_agent)
    graph.add_node("respond", _node_orchestrator_respond)

    graph.set_entry_point("plan_workflow")

    def _route_from_workflow_plan(state: AgentState) -> str:
        if "error" in state:
            return "error"
        action = state.get("route")
        # If web_agent is selected, go through guardrails first
        if action == "web_agent":
            return "guardrails"
        return action or "respond"

    def _route_from_guardrails(state: AgentState) -> str:
        if "error" in state:
            return "error"
        if state.get("guardrails_passed"):
            return "web_agent"
        return "error"

    def _route_after_agent_execution(state: AgentState) -> str:
        if "error" in state:
            return "error"
        
        # Check if we have more steps in the workflow
        current_index = state.get("current_step_index", 0)
        workflow = state.get("workflow_plan", [])
        
        if current_index < len(workflow):
            # Continue with workflow planning to get next step
            return "continue_workflow"
        else:
            # Workflow complete, respond
            return "respond"

    graph.add_conditional_edges(
        "plan_workflow",
        _route_from_workflow_plan,
        {
            "db_agent": "db_agent", 
            "viz_agent": "viz_agent", 
            "guardrails": "guardrails", 
            "respond": "respond",
            "error": "respond"
        },
    )
    graph.add_conditional_edges(
        "guardrails",
        _route_from_guardrails,
        {"web_agent": "web_agent", "error": "respond"},
    )
    graph.add_conditional_edges(
        "db_agent", 
        _route_after_agent_execution, 
        {"continue_workflow": "plan_workflow", "respond": "respond", "error": "respond"}
    )
    graph.add_conditional_edges(
        "viz_agent", 
        _route_after_agent_execution, 
        {"continue_workflow": "plan_workflow", "respond": "respond", "error": "respond"}
    )
    graph.add_conditional_edges(
        "web_agent", 
        _route_after_agent_execution, 
        {"continue_workflow": "plan_workflow", "respond": "respond", "error": "respond"}
    )

    graph.add_edge("respond", END)
    return graph.compile()


@trace(name="orchestrator.run", category="orchestrator")
def run_orchestrator(user_input: Any) -> Dict[str, Any]:
    """Run the orchestrator flow with provided user_input (NL)."""
    from typing import cast

    app = build_app()
    # pp.get_graph()
    # output_path = Path("orchestrator_graph.png")
    # output_path.write_bytes(png_bytes)
    # print("hi", app.get_graph())
    # print(f"Graph image saved to {output_path.resolve()}")
    initial_state: AgentState = {
        "user_input": user_input,
        "original_user_input": user_input,
        "current_query": str(user_input)
    }
    final_state: AgentState = cast(AgentState, app.invoke(initial_state))
    return {k: v for k, v in final_state.items() if k in {"result", "error"}}