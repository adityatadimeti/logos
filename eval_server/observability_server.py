from __future__ import annotations

import datetime
import os
from collections import defaultdict
from typing import Any, Dict, List

from flask import Flask, jsonify, request, render_template_string

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

app = Flask(__name__)

EVENTS: List[Dict[str, Any]] = []

DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Logos Observability</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 1.25rem; }
    h1, h2 { margin: 0.2rem 0; }
    table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; }
    th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; }
    th { background: #f5f5f5; }
    .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; background: #eee; font-size: 12px; }
    .ok { background: #e8f5e9; }
    .error { background: #ffebee; }
    .muted { color: #666; }
    .pill { display: inline-block; padding: 1px 6px; border: 1px solid #ddd; border-radius: 999px; font-size: 12px; background: #fafafa; }
    .wrap { white-space: pre-wrap; word-break: break-word; }
  </style>
</head>
<body>
  <h1>Logos Observability</h1>
  <p class="muted">Total events: {{ total }} • Traces: {{ trace_count }}</p>
  <h2>Recent Traces</h2>
  <table>
    <thead>
      <tr><th>Trace</th><th>Spans</th><th>Errors</th><th>Duration (ms)</th><th>Actions</th></tr>
    </thead>
    <tbody>
    {% for row in traces %}
      <tr>
        <td><span class="pill">{{ row.trace_id }}</span></td>
        <td>{{ row.span_count }}</td>
        <td><span class="badge {% if row.error_count>0 %}error{% else %}ok{% endif %}">{{ row.error_count }}</span></td>
        <td>{{ row.duration_ms }}</td>
        <td><a href="/trace/{{ row.trace_id }}">View</a></td>
      </tr>
    {% endfor %}
    </tbody>
  </table>

  <h2 style="margin-top: 1.5rem;">Insights</h2>
  <div class="wrap">{{ insights }}</div>
</body>
</html>
"""

TRACE_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Trace {{ trace_id }}</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 1.25rem; }
    table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; }
    th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; }
    th { background: #f5f5f5; }
    .ok { background: #e8f5e9; }
    .error { background: #ffebee; }
    .muted { color: #666; }
    .wrap { white-space: pre-wrap; word-break: break-word; }
  </style>
</head>
<body>
  <h1>Trace {{ trace_id }}</h1>
  <p class="muted">{{ count }} events</p>
  <table>
    <thead>
      <tr><th>Time (UTC)</th><th>Type</th><th>Name</th><th>Status</th><th>Duration (ms)</th><th>Preview</th></tr>
    </thead>
    <tbody>
      {% for e in events %}
      <tr>
        <td class="muted">{{ e.timestamp }}</td>
        <td>{{ e.event_type }}</td>
        <td>{{ e.name }}</td>
        <td class="{% if e.status=='error' %}error{% else %}ok{% endif %}">{{ e.status or '' }}</td>
        <td>{{ e.duration_ms or '' }}</td>
        <td class="wrap">{{ e.preview or '' }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  <p><a href="/dashboard">Back</a></p>
</body>
</html>
"""


@app.route("/log", methods=["POST"])
def log_event():
    data = request.get_json(force=True, silent=True) or {}
    # add server-side timestamp
    data["server_ts"] = datetime.datetime.utcnow().isoformat()
    EVENTS.append(data)
    # keep a rolling window
    if len(EVENTS) > 5000:
        del EVENTS[:1000]
    return jsonify({"ok": True})


@app.route("/dashboard")
def dashboard():
    # Aggregate traces
    by_trace: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in EVENTS:
        t = e.get("trace_id") or "unknown"
        by_trace[t].append(e)

    rows = []
    for trace_id, items in by_trace.items():
        span_count = sum(1 for i in items if i.get("event_type") == "span_start")
        error_count = sum(1 for i in items if i.get("status") == "error")
        # duration: diff between first span_start and last span_end
        starts = [i for i in items if i.get("event_type") == "span_start"]
        ends = [i for i in items if i.get("event_type") == "span_end"]
        duration_ms = 0
        if starts and ends:
            duration_ms = max(int(e.get("duration_ms") or 0) for e in ends)
        rows.append(
            {
                "trace_id": trace_id,
                "span_count": span_count,
                "error_count": error_count,
                "duration_ms": duration_ms,
            }
        )
    rows.sort(key=lambda r: r["span_count"], reverse=True)

    insights = _generate_insights()

    return render_template_string(
        DASHBOARD_HTML,
        total=len(EVENTS),
        trace_count=len(by_trace),
        traces=rows[:100],
        insights=insights,
    )


@app.route("/trace/<trace_id>")
def trace_view(trace_id: str):
    items = [e for e in EVENTS if (e.get("trace_id") == trace_id)]
    # enrich for preview column
    enriched = []
    for e in items:
        preview = ""
        if e.get("event_type") == "span_start":
            ap = e.get("args_preview")
            kp = e.get("kwargs_preview")
            if ap or kp:
                preview = f"args={ap}  kwargs={kp}"
        elif e.get("event_type") == "span_end":
            if e.get("status") == "error":
                preview = f"{e.get('error_type')}: {e.get('error_message')}"
            else:
                preview = (e.get("result_preview") or "")
        enriched.append(
            {
                "timestamp": e.get("timestamp"),
                "event_type": e.get("event_type"),
                "name": e.get("name"),
                "status": e.get("status"),
                "duration_ms": e.get("duration_ms"),
                "preview": preview,
            }
        )
    return render_template_string(TRACE_HTML, trace_id=trace_id, count=len(items), events=enriched)


@app.route("/")
def root():
    return jsonify({"ok": True, "endpoints": ["/log", "/dashboard", "/trace/<trace_id>"]})


def _generate_insights() -> str:
    # Simple heuristic insights; optionally call Anthropic if available for smarter suggestions
    if not EVENTS:
        return "No events yet."

    # Basic aggregates
    by_name: Dict[str, Dict[str, int]] = defaultdict(lambda: {"count": 0, "errors": 0})
    long_spans: List[Dict[str, Any]] = []

    for e in EVENTS:
        name = e.get("name") or "unknown"
        if e.get("event_type") == "span_end":
            by_name[name]["count"] += 1
            if e.get("status") == "error":
                by_name[name]["errors"] += 1
            dur = int(e.get("duration_ms") or 0)
            if dur >= 1500:
                long_spans.append({"name": name, "duration_ms": dur})

    top_error = sorted(by_name.items(), key=lambda kv: kv[1]["errors"], reverse=True)[:3]
    slowest = sorted(long_spans, key=lambda r: r["duration_ms"], reverse=True)[:3]

    lines = []
    if top_error and top_error[0][1]["errors"] > 0:
        lines.append("High-error spans:")
        for n, s in top_error:
            lines.append(f"- {n}: {s['errors']} errors over {s['count']} runs")
    if slowest:
        lines.append("Potential performance hotspots (duration >= 1.5s):")
        for r in slowest:
            lines.append(f"- {r['name']}: {r['duration_ms']} ms")

    # Optional: Use Anthropic to summarize
    try:
        from llm_utils import call_anthropic

        summary = call_anthropic(
            system_prompt="You are an expert AI ops analyst.",
            user_message=(
                "Given the following telemetry summaries, suggest concrete improvements in 3-5 bullets.\n\n"
                + "\n".join(lines[:20])
            ),
            max_tokens=300,
            temperature=0.0,
        )
        if summary:
            return summary
    except Exception:
        pass

    return "\n".join(lines) or "No obvious issues detected."


def main():
    host = os.environ.get("OBS_HOST", "127.0.0.1")
    port = int(os.environ.get("OBS_PORT", "5051"))
    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    main() 