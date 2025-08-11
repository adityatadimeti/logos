from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def _require_dependency(import_name: str, pip_name: Optional[str] = None) -> None:
    try:
        __import__(import_name)
    except ImportError as exc:
        pkg = pip_name or import_name
        raise ImportError(
            f"Missing optional dependency '{import_name}'. Install with: pip install {pkg}"
        ) from exc


def _choose_chart_spec(user_question: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Use the LLM to pick a minimal chart spec from the question and sample rows.

    Returns a dict like:
      {"chart": "bar"|"line"|"pie", "x": "column", "y": "column"|null, "agg": "count"|"sum"|"avg"|"none"}
    """
    sample = rows[:200] if rows else []
    try:
        from llm_utils import call_anthropic_json
        import json as _json

        system = (
            "You design a very simple chart from tabular rows. Respond with JSON only.\n"
            "Return keys: {chart: 'bar'|'line'|'pie', x: string, y: string|null, agg: 'count'|'sum'|'avg'|'none'}.\n"
            "Guidance: Use 'bar' for category comparisons (counts/sums), 'line' for time series or sequences, 'pie' for share of whole across categories (counts or sums)."
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
        chart_val = (spec.get("chart") or "bar").lower()
        if chart_val not in {"bar", "line", "pie"}:
            chart_val = "bar"
        return {
            "chart": chart_val,
            "x": spec.get("x"),
            "y": spec.get("y"),
            "agg": spec.get("agg", "count"),
        }
    except Exception:
        # Heuristic fallback: pie or bar for categories, line if looks like time series
        chart_val = "bar"
        if rows:
            # crude time-series detection: any key containing 'date' or 'time'
            keys = list(rows[0].keys())
            if any("date" in k.lower() or "time" in k.lower() for k in keys):
                chart_val = "line"
        x_col = None
        if rows:
            for key in rows[0].keys():
                val = rows[0].get(key)
                if not isinstance(val, (int, float)):
                    x_col = key
                    break
        x_col = x_col or (list(rows[0].keys())[0] if rows else "category")
        fallback = {"chart": chart_val, "x": x_col, "y": None, "agg": "count"}
        if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
            print("[VIZ] Spec fallback:", fallback)
        return fallback


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


def _build_chartjs_payload(spec: Dict[str, Any], series: Dict[str, List[Any]]) -> Dict[str, Any]:
    labels = [str(x) for x in series.get("x", [])]
    data = series.get("y", [])
    dataset_label = f"{spec.get('agg','count')} of {spec.get('y') or spec.get('x')}"
    chart_type = (spec.get("chart") or "bar").lower()

    # Provide a palette for pie slices
    slice_colors = [
        "#4f46e5", "#06b6d4", "#22c55e", "#f59e0b", "#ef4444",
        "#8b5cf6", "#14b8a6", "#84cc16", "#eab308", "#f97316",
    ]

    if chart_type == "pie":
        chartjs = {
            "type": "pie",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": dataset_label,
                        "data": data,
                        "backgroundColor": slice_colors[: max(1, len(data))],
                        "borderColor": "#111827",
                    }
                ],
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "legend": {"display": True},
                    "title": {"display": True, "text": "Simple Visualization"},
                },
            },
        }
        return chartjs

    # Bar / Line
    chartjs = {
        "type": chart_type if chart_type in {"bar", "line"} else "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": dataset_label,
                    "data": data,
                    "backgroundColor": "rgba(79,70,229,0.5)",
                    "borderColor": "rgba(79,70,229,1)",
                }
            ],
        },
        "options": {
            "responsive": True,
            "plugins": {
                "legend": {"display": True},
                "title": {"display": True, "text": "Simple Visualization"},
            },
            "scales": {
                "x": {"ticks": {"autoSkip": True, "maxRotation": 45}},
                "y": {"beginAtZero": True},
            },
        },
    }
    return chartjs


def execute_viz_agent(user_question: str, table: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
    """Fetch rows, decide a minimal chart spec, and return Chart.js payload.

    Returns {"chartjs": {...}, "spec": {...}} or {"error": str}.
    """
    try:
        from database_agent import QuerySpec, _execute_supabase_query  # type: ignore

        target_table = table or os.environ.get("DB_DEFAULT_TABLE") or "wellsdummydata"
        fetched = _execute_supabase_query(QuerySpec(table=target_table, limit=limit))
        rows = fetched.get("data") or []

        spec = _choose_chart_spec(user_question, rows)
        series = _aggregate(rows, x=spec.get("x"), y=spec.get("y"), agg=spec.get("agg", "count"))
        chartjs = _build_chartjs_payload(spec, series)
        return {"chartjs": chartjs, "spec": spec}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


