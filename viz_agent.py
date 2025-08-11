from __future__ import annotations

import base64
import io
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv  # type: ignore

load_dotenv()

# Observability must be imported before usage
try:
    from observability import trace, traceback  # type: ignore
except Exception:
    def trace(*args, **kwargs):  # type: ignore
        def _decorator(fn):
            return fn
        return _decorator

    def traceback(*args, **kwargs):  # type: ignore
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
    # Force non-GUI backend for server environments (Flask background thread)
    os.environ.setdefault("MPLBACKEND", "Agg")
    _require_dependency("matplotlib")
    try:  # ensure backend stickiness even if default is GUI
        import matplotlib  # type: ignore
        if getattr(matplotlib, "get_backend", None) and matplotlib.get_backend() != "Agg":
            matplotlib.use("Agg")
    except Exception:
        pass


@traceback(name="viz._to_png_base64", category="viz")
def _to_png_base64(fig) -> str:
    import matplotlib.pyplot as plt  # type: ignore

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


@trace(name="viz._choose_chart_spec", category="llm")
def _choose_chart_spec(user_question: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Use the LLM to pick a minimal chart spec from the question and sample rows.

    Returns a dict like:
      {"chart": "bar"|"line", "x": "column", "y": "column"|null, "agg": "count"|"sum"|"avg"|"none"}
    """
    sample = rows[:200] if rows else []
    try:
        from llm_utils import call_anthropic_json
        import json as _json

        system = (
            "You design a very simple chart from tabular rows. Respond with JSON only.\n"
            "Return keys: {chart: 'bar'|'line', x: string, y: string|null, agg: 'count'|'sum'|'avg'|'none'}.\n"
            "Pick columns that exist. Prefer bar with count by category; line for time series."
        )
        msg = (
            "User question:\n"
            + user_question
            + "\n\nRows (JSON, sample):\n"
            + _json.dumps(sample)
        )
        spec = call_anthropic_json(system_prompt=system, user_message=msg)
        if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
            print("[VIZ] Spec from LLM:", spec)
        # Minimal validation
        if not isinstance(spec, dict) or not spec.get("chart") or not spec.get("x"):
            raise ValueError("Model did not return a valid chart spec")
        return {
            "chart": spec.get("chart", "bar"),
            "x": spec.get("x"),
            "y": spec.get("y"),
            "agg": spec.get("agg", "count"),
        }
    except Exception:
        # Heuristic fallback: bar count of first string-like column
        x_col = None
        if rows:
            for key in rows[0].keys():
                # choose first non-numeric column as category
                val = rows[0].get(key)
                if not isinstance(val, (int, float)):
                    x_col = key
                    break
        x_col = x_col or (list(rows[0].keys())[0] if rows else "category")
        fallback = {"chart": "bar", "x": x_col, "y": None, "agg": "count"}
        if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
            print("[VIZ] Spec fallback:", fallback)
        return fallback


@traceback(name="viz._aggregate", category="viz")
def _aggregate(rows: List[Dict[str, Any]], x: str, y: Optional[str], agg: str) -> Dict[str, List[Any]]:
    from collections import defaultdict

    xs: List[Any] = []
    ys: List[float] = []

    if agg == "count" or y is None:
        counts = defaultdict(int)
        for r in rows:
            key = r.get(x)
            counts[key] += 1
        # sort by count desc
        items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:20]
        xs = [k for k, _ in items]
        ys = [v for _, v in items]
        return {"x": xs, "y": ys}

    # numeric aggregates
    if agg in ("sum", "avg") and y is not None:
        sums = defaultdict(float)
        counts = defaultdict(int)
        for r in rows:
            key = r.get(x)
            try:
                val = float(r.get(y) or 0)
            except Exception:
                val = 0.0
            sums[key] += val
            counts[key] += 1
        items = sorted(sums.items(), key=lambda kv: kv[1], reverse=True)[:20]
        xs = [k for k, _ in items]
        if agg == "sum":
            ys = [sums[k] for k in xs]
        else:
            ys = [sums[k] / max(counts[k], 1) for k in xs]
        return {"x": xs, "y": ys}

    # default passthrough: first 100 rows as sequence
    xs = list(range(min(len(rows), 100)))
    ys = []
    for i in xs:
        try:
            ys.append(float(list(rows[i].values())[0]))
        except Exception:
            ys.append(0.0)
    return {"x": xs, "y": ys}


@traceback(name="viz._render_chart_png", category="viz")
def _render_chart_png(spec: Dict[str, Any], series: Dict[str, List[Any]]) -> str:
    _lazy_imports()
    import matplotlib.pyplot as plt  # type: ignore

    chart = (spec.get("chart") or "bar").lower()
    fig, ax = plt.subplots(figsize=(6, 4))
    x_vals = series.get("x", [])
    y_vals = series.get("y", [])

    if chart == "line":
        ax.plot(x_vals, y_vals, marker="o")
    else:
        ax.bar(x_vals, y_vals)

    ax.set_xlabel(str(spec.get("x") or "x"))
    if spec.get("y"):
        ax.set_ylabel(str(spec.get("y")))
    else:
        ax.set_ylabel(str(spec.get("agg") or "count"))
    ax.set_title("Simple Visualization")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    return _to_png_base64(fig)


@trace(name="agent.execute_viz_agent", category="agent")
def execute_viz_agent(user_question: str, table: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
    """Fetch rows, decide a minimal chart spec, render a PNG, and return base64.

    Returns {"image_base64": str, "alt": str} or {"error": str}.
    """
    try:
        from database_agent import QuerySpec, _execute_supabase_query  # type: ignore

        target_table = table or os.environ.get("DB_DEFAULT_TABLE") or "wellsdummydata"
        fetched = _execute_supabase_query(QuerySpec(table=target_table, limit=limit))
        rows = fetched.get("data") or []

        spec = _choose_chart_spec(user_question, rows)
        series = _aggregate(rows, x=spec.get("x"), y=spec.get("y"), agg=spec.get("agg", "count"))
        png_b64 = _render_chart_png(spec, series)
        alt = (
            f"{spec.get('chart','bar')} chart of {spec.get('agg','count')}"
            f" by {spec.get('x')}"
            + (f" vs {spec.get('y')}" if spec.get("y") else "")
        )
        return {"image_base64": png_b64, "alt": alt, "spec": spec}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


