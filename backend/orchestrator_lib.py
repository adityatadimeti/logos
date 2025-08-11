"""
Deprecated: decorator-based orchestrator.

Use the LangGraph orchestrator defined in `base_agent.py` instead.
This module re-exports `build_app` and `run_orchestrator` for convenience.
"""

from __future__ import annotations

from typing import Any, Dict

# Re-export from base_agent to avoid breaking imports in existing code
from base_agent import build_app, run_orchestrator  # noqa: F401


def orchestrate(func):  # noqa: D401
    """Deprecated. This decorator no longer performs orchestration.

    It simply calls the wrapped function and returns its result.
    Please migrate to using `run_orchestrator` with the LangGraph app.
    """

    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper