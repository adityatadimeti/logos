"""
Database Agent (LangGraph + Supabase)

Provides a minimal agent graph using LangGraph that can query Supabase.

Env vars required:
  - SUPABASE_URL
  - SUPABASE_ANON_KEY

Usage (CLI):
  python database_agent.py --table your_table --limit 5 --select id,name --filter status=active

Programmatic:
  from database_agent import run_query
  rows = run_query(table="your_table", select=["id","name"], filters={"status":"active"}, limit=5)

Notes:
  - Filters are applied as equality (eq) predicates.
  - Results are returned as a dict with keys: {"data": [...], "count": int} or an error.

Install with UV:
  uv add langgraph supabase
  uv run python database_agent.py --table your_table
"""

from __future__ import annotations

import os
import sys
import argparse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict


def _require_dependency(import_name: str, pip_name: Optional[str] = None) -> None:
    try:
        __import__(import_name)
    except ImportError as exc:
        pkg = pip_name or import_name
        raise ImportError(
            f"Missing optional dependency '{import_name}'. Install with: pip install {pkg}"
        ) from exc


# Defer heavy deps until needed for friendlier import behavior
def _lazy_imports() -> None:
    _require_dependency("langgraph")
    _require_dependency("supabase")


class AgentState(TypedDict, total=False):
    input: Dict[str, Any]
    result: Any
    error: str


@dataclass
class QuerySpec:
    table: str
    select: Optional[List[str]] = None  # columns to select; None means "*"
    filters: Optional[Dict[str, Any]] = None  # equality filters
    limit: Optional[int] = None


def _get_supabase_client():
    """Create a Supabase client using env vars.

    Returns the Client instance. Raises RuntimeError if env vars are missing.
    """
    _lazy_imports()
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment."
        )
    return create_client(url, key)


def _execute_supabase_query(spec: QuerySpec) -> Dict[str, Any]:
    client = _get_supabase_client()
    query = client.table(spec.table)

    # Select
    select_clause = "*" if not spec.select else ",".join(spec.select)
    query = query.select(select_clause)

    # Filters (eq only for now)
    if spec.filters:
        for column, value in spec.filters.items():
            query = query.eq(column, value)

    # Limit
    if spec.limit is not None:
        query = query.limit(spec.limit)

    # Execute
    result = query.execute()

    # supabase-py returns a response with .data in recent versions; also expose count
    data = getattr(result, "data", None)
    if data is None and isinstance(result, dict):
        data = result.get("data")
    count = getattr(result, "count", None)
    if count is None and isinstance(result, dict):
        count = result.get("count")

    return {"data": data, "count": count}


def _node_run_query(state: AgentState) -> AgentState:
    spec_dict = state.get("input", {})
    try:
        spec = QuerySpec(
            table=spec_dict["table"],
            select=spec_dict.get("select"),
            filters=spec_dict.get("filters"),
            limit=spec_dict.get("limit"),
        )
        output = _execute_supabase_query(spec)
        return {"result": output}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def build_app():
    """Compile and return the LangGraph app for the database agent."""
    _lazy_imports()
    from langgraph.graph import StateGraph, END

    graph = StateGraph(AgentState)
    graph.add_node("run_query", _node_run_query)
    graph.set_entry_point("run_query")
    graph.add_edge("run_query", END)
    return graph.compile()


def run_query(
    table: str,
    select: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute a single Supabase query via the agent graph.

    Returns a dict with either {"data": [...], "count": int} or {"error": str}.
    """
    app = build_app()
    state_in: AgentState = {
        "input": {
            "table": table,
            "select": select,
            "filters": filters,
            "limit": limit,
        }
    }
    result_state: AgentState = app.invoke(state_in)
    return {k: v for k, v in result_state.items() if k in {"result", "error"}}


def _parse_cli_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Database Agent (Supabase + LangGraph)")
    parser.add_argument("--table", required=True, help="Supabase table name")
    parser.add_argument(
        "--select",
        default=None,
        help="Comma-separated column list (default: all columns)",
    )
    parser.add_argument(
        "--filter",
        action="append",
        default=[],
        help="Equality filter as key=value (can be provided multiple times)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Row limit")
    return parser.parse_args(argv)


def _parse_filters(pairs: List[str]) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid --filter value: '{pair}', expected key=value")
        key, value = pair.split("=", 1)
        filters[key] = value
    return filters


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = _parse_cli_args(argv)
        select_cols = None if not args.select else [c.strip() for c in args.select.split(",") if c.strip()]
        filters = _parse_filters(args.filter) if args.filter else None
        output = run_query(
            table=args.table,
            select=select_cols,
            filters=filters,
            limit=args.limit,
        )
        print(output)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())



