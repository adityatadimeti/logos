"""
Database access helper for Supabase.

Exposes a minimal function to execute read-only queries against Supabase.

Env vars required:
  - SUPABASE_URL
  - SUPABASE_ANON_KEY

Example:
    from database_agent import execute_query

    rows = execute_query({
        "table": "your_table",
        "select": ["id", "name"],
        "filters": {"status": "active"},
        "limit": 5,
    })

Notes:
  - Filters are applied as equality (eq) predicates.
  - Returns a dict with keys: {"data": [...], "count": int}.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


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



