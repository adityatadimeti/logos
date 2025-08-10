"""
Database access helper for Supabase.

Exposes functions to execute read-only queries against Supabase, and an
LLM-powered DB agent that filters rows based on a natural-language question.

Env vars required:
  - SUPABASE_URL
  - SUPABASE_ANON_KEY

Optional env:
  - DB_DEFAULT_TABLE (used by higher-level orchestrator)

Example:
    from database_agent import execute_db_agent

    result = execute_db_agent(
        user_question="What did my shopping transactions look like this week?",
        table="wellsdummydata",
        limit=500,
    )
    # => {"rows": [...], "count": N}

Notes:
  - Filters are applied by the LLM; we first fetch a broad slice of rows.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Load .env variables if present
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass


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
    _require_dependency("supabase")


@dataclass
class QuerySpec:
    table: str
    select: Optional[List[str]] = None  # columns to select; None means "*"
    filters: Optional[Dict[str, Any]] = None  # equality filters
    limit: Optional[int] = None


def _get_supabase_client():
    """Create and return a Supabase client using env vars.

    Raises RuntimeError if env vars are missing.
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


def execute_query(query: Dict[str, Any] | QuerySpec) -> Dict[str, Any]:
    """Execute a Supabase query.

    Input can be a QuerySpec or a dict with keys:
      - table: str (required)
      - select: Optional[List[str]]
      - filters: Optional[Dict[str, Any]]
      - limit: Optional[int]

    Returns {"data": [...], "count": int}
    """
    if isinstance(query, dict):
        spec = QuerySpec(
            table=query["table"],
            select=query.get("select"),
            filters=query.get("filters"),
            limit=query.get("limit"),
        )
    else:
        spec = query

    return _execute_supabase_query(spec)


# ---------- LLM-based row filtering ----------

DB_FILTER_SYSTEM = (
    "You are a data filtering assistant for banking data.\n"
    "You will be provided with a JSON array of rows and a natural-language question.\n"
    "Return ONLY a JSON object with the following shape: {\"rows\": [...]} where rows is the subset\n"
    "of the provided rows that best matches the user's request. Do not invent rows.\n"
)


def llm_filter_rows(user_question: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Use an LLM to select a subset of rows matching the user's question.

    Returns a dict: {"rows": [...]}.
    """
    # Avoid huge payloads: cap rows count
    MAX_ROWS = 800
    sample = rows[:MAX_ROWS] if rows else []
    try:
        from llm_utils import call_anthropic_json

        user_msg = (
            "User question:\n" + user_question + "\n\n"
            "Rows (JSON array):\n" + __import__("json").dumps(sample)
        )
        out = call_anthropic_json(
            system_prompt=DB_FILTER_SYSTEM,
            user_message=user_msg,
            max_tokens=2000,
        )
        # Expect out to contain {"rows": [...]}.
        rows_out = out.get("rows") if isinstance(out, dict) else None
        if not isinstance(rows_out, list):
            raise ValueError("Model did not return a 'rows' array")
        return {"rows": rows_out}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def execute_db_agent(user_question: str, table: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
    """Fetch a broad set of rows from Supabase, then use the LLM to filter them.

    Returns {"rows": [...], "count": int} or {"error": str}.
    """
    target_table = table or os.environ.get("DB_DEFAULT_TABLE") or "wellsdummydata"
    try:
        fetched = _execute_supabase_query(QuerySpec(table=target_table, limit=limit))
        data = fetched.get("data") or []
        filtered = llm_filter_rows(user_question, data)
        if "error" in filtered:
            return filtered
        rows_out = filtered.get("rows") or []
        return {"rows": rows_out, "count": len(rows_out)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}



