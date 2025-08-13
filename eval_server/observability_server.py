from __future__ import annotations

import datetime
import os
import json
from collections import defaultdict
from typing import Any, Dict, List
from textwrap import dedent

from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

app = Flask(__name__)
CORS(app)

EVENTS: List[Dict[str, Any]] = []

# Supabase database functions
def _get_supabase_client():
    """Create and return a Supabase client using env vars."""
    try:
        from supabase import create_client
        
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment.")
        return create_client(url, key)
    except Exception as e:
        print(f"Failed to create Supabase client: {e}")
        return None

def _insert_trace_event(event_data: Dict[str, Any]) -> bool:
    """Insert a trace event into the Supabase database."""
    try:
        client = _get_supabase_client()
        if not client:
            return False
            
        # Prepare data for insertion
        insert_data = {
            'trace_id': event_data.get('trace_id'),
            'span_id': event_data.get('span_id'),
            'parent_span_id': event_data.get('parent_span_id'),
            'event_type': event_data.get('event_type'),
            'name': event_data.get('name'),
            'category': event_data.get('category'),
            'status': event_data.get('status'),
            'timestamp': event_data.get('timestamp'),
            'server_ts': event_data.get('server_ts'),
            'duration_ms': event_data.get('duration_ms'),
            'args_preview': event_data.get('args_preview'),
            'kwargs_preview': event_data.get('kwargs_preview'),
            'result_preview': event_data.get('result_preview'),
            'error_type': event_data.get('error_type'),
            'error_message': event_data.get('error_message'),
            'metadata': json.dumps(event_data.get('metadata', {}))
        }
        
        # Remove None values
        insert_data = {k: v for k, v in insert_data.items() if v is not None}
        
        result = client.table('traces').insert(insert_data).execute()
        return True
    except Exception as e:
        print(f"Failed to insert trace event: {e}")
        return False

def _get_traces_from_db(limit: int = 1000) -> List[Dict[str, Any]]:
    """Fetch recent trace events from the database."""
    try:
        client = _get_supabase_client()
        if not client:
            return []
            
        result = client.table('traces')\
            .select('*')\
            .order('timestamp', desc=True)\
            .limit(limit)\
            .execute()
            
        return result.data if result.data else []
    except Exception as e:
        print(f"Failed to fetch traces from database: {e}")
        return []

def _get_trace_by_id_from_db(trace_id: str) -> List[Dict[str, Any]]:
    """Fetch all events for a specific trace from the database."""
    try:
        client = _get_supabase_client()
        if not client:
            return []
            
        result = client.table('traces')\
            .select('*')\
            .eq('trace_id', trace_id)\
            .order('timestamp', desc=False)\
            .execute()
            
        return result.data if result.data else []
    except Exception as e:
        print(f"Failed to fetch trace {trace_id} from database: {e}")
        return []






@app.route("/log", methods=["POST"])
def log_event():
    data = request.get_json(force=True, silent=True) or {}
    # add server-side timestamp
    data["server_ts"] = datetime.datetime.utcnow().isoformat()
    
    # Store in memory (for fallback)
    EVENTS.append(data)
    # keep a rolling window, sorted by timestamp
    if len(EVENTS) > 5000:
        # Sort by timestamp before trimming to keep most recent
        EVENTS.sort(key=lambda e: e.get("timestamp") or e.get("server_ts") or "", reverse=True)
        del EVENTS[1000:]  # Keep most recent 1000
    
    # Also store in database
    _insert_trace_event(data)
    
    return jsonify({"ok": True})


@app.route("/dashboard")
def dashboard():
    """JSON endpoint for dashboard data."""
    # Try to load from database first, fallback to in-memory
    events = _get_traces_from_db(limit=1000)
    if not events:
        events = EVENTS
    
    # Aggregate traces and track latest timestamp per trace
    by_trace: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    trace_timestamps: Dict[str, str] = {}  # track latest timestamp per trace
    
    for e in events:
        t = e.get("trace_id") or "unknown"
        by_trace[t].append(e)
        
        # Track the latest timestamp for this trace
        ts = e.get("timestamp") or e.get("server_ts")
        if ts:
            current_latest = trace_timestamps.get(t, "")
            if not current_latest or ts > current_latest:
                trace_timestamps[t] = ts

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
                "latest_timestamp": trace_timestamps.get(trace_id, ""),  # include for sorting
            }
        )
    # Sort by latest timestamp descending
    rows.sort(key=lambda r: r["latest_timestamp"] or "", reverse=True)

    insights = _generate_insights(events)

    return jsonify({
        "total": len(events),
        "trace_count": len(by_trace),
        "traces": rows[:100],
        "insights": insights,
    })


@app.route("/trace/<trace_id>")
def trace_view(trace_id: str):
    """JSON endpoint for trace details."""
    # Try to load from database first, fallback to in-memory
    items = _get_trace_by_id_from_db(trace_id)
    if not items:
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
                "args_preview": e.get("args_preview"),
                "kwargs_preview": e.get("kwargs_preview"),
                "result_preview": e.get("result_preview"),
                "error_type": e.get("error_type"),
                "error_message": e.get("error_message"),
            }
        )
    
    return jsonify({
        "trace_id": trace_id,
        "count": len(items),
        "events": enriched
    })


@app.route("/status")
def status():
    """Return system status including database connectivity."""
    db_connected = False
    db_status = "disconnected"
    trace_count_db = 0
    trace_count_memory = len(EVENTS)
    
    try:
        client = _get_supabase_client()
        if client:
            # Test database connection
            result = client.table('traces').select('id').limit(1).execute()
            db_connected = True
            db_status = "connected"
            
            # Get count from database
            count_result = client.table('traces').select('id', count='exact').execute()
            trace_count_db = count_result.count if count_result.count else 0
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return jsonify({
        "ok": True,
        "database": {
            "connected": db_connected,
            "status": db_status,
            "trace_count": trace_count_db
        },
        "memory": {
            "trace_count": trace_count_memory
        },
        "data_source": "database" if db_connected else "memory"
    })


@app.route("/")
def root():
    return jsonify({"ok": True, "endpoints": ["/log", "/dashboard", "/trace/<trace_id>", "/diagnose", "/agent-graph"]})


@app.route("/agent-graph", methods=["GET"])
def get_agent_graph():
    """Return the agent graph structure for visualization"""
    try:
        # Import here to avoid circular imports
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.base_agent import build_app
        
        app = build_app()
        graph = app.get_graph()
        
        # Convert the graph to a JSON-serializable format
        nodes = []
        edges = []
        
        # Extract nodes - handle different graph structures
        if hasattr(graph, 'nodes'):
            node_ids = list(graph.nodes.keys()) if hasattr(graph.nodes, 'keys') else list(graph.nodes)
        else:
            node_ids = []
        
        for node_id in node_ids:
            nodes.append({
                "id": str(node_id),
                "label": str(node_id).replace("_", " ").title(),
                "type": "agent" if "agent" in str(node_id) else "control"
            })
        
        # Extract edges - handle different edge structures
        if hasattr(graph, 'edges'):
            if hasattr(graph.edges, 'items'):
                # Dictionary structure
                for source, targets in graph.edges.items():
                    if isinstance(targets, (list, tuple)):
                        for target in targets:
                            edges.append({
                                "source": str(source),
                                "target": str(target),
                                "label": str(target)
                            })
                    elif hasattr(targets, '__iter__') and not isinstance(targets, str):
                        # Iterable but not string
                        for target in targets:
                            edges.append({
                                "source": str(source),
                                "target": str(target),
                                "label": str(target)
                            })
                    else:
                        # Single target
                        edges.append({
                            "source": str(source),
                            "target": str(targets),
                            "label": str(targets)
                        })
            elif hasattr(graph.edges, '__iter__'):
                # List of edges
                for edge in graph.edges:
                    if hasattr(edge, 'source') and hasattr(edge, 'target'):
                        edges.append({
                            "source": str(edge.source),
                            "target": str(edge.target),
                            "label": str(edge.target)
                        })
                    elif isinstance(edge, (list, tuple)) and len(edge) >= 2:
                        edges.append({
                            "source": str(edge[0]),
                            "target": str(edge[1]),
                            "label": str(edge[1])
                        })
        
        # If we still don't have nodes, create a simple fallback
        if not nodes:
            nodes = [
                {"id": "plan_workflow", "label": "Plan Workflow", "type": "control"},
                {"id": "guardrails", "label": "Guardrails", "type": "control"},
                {"id": "db_agent", "label": "DB Agent", "type": "agent"},
                {"id": "viz_agent", "label": "Viz Agent", "type": "agent"},
                {"id": "web_agent", "label": "Web Agent", "type": "agent"},
                {"id": "respond", "label": "Respond", "type": "control"}
            ]
            edges = [
                {"source": "plan_workflow", "target": "db_agent", "label": "db_agent"},
                {"source": "plan_workflow", "target": "viz_agent", "label": "viz_agent"},
                {"source": "plan_workflow", "target": "guardrails", "label": "guardrails"},
                {"source": "guardrails", "target": "web_agent", "label": "web_agent"},
                {"source": "db_agent", "target": "respond", "label": "respond"},
                {"source": "viz_agent", "target": "respond", "label": "respond"},
                {"source": "web_agent", "target": "respond", "label": "respond"}
            ]
        
        return jsonify({
            "nodes": nodes,
            "edges": edges,
            "description": "LangGraph Agent Workflow"
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/diagnose", methods=["POST"])
def diagnose_issue():
    """Analyze trace events and user feedback to provide diagnosis and fix suggestions"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        trace_id = data.get("traceId")
        events = data.get("events", [])
        feedback = data.get("feedback", {})
        
        if not trace_id or not events:
            return jsonify({"error": "Missing required data: traceId and events"}), 400
        
        diagnosis = _generate_diagnosis(trace_id, events, feedback)
        return jsonify({"diagnosis": diagnosis})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _generate_diagnosis(trace_id: str, events: List[Dict[str, Any]], feedback: Dict[str, Any]) -> str:
    """Generate AI diagnosis based on trace events and user feedback"""
    try:
        # Import here to avoid circular imports
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.llm_utils import call_anthropic
        
        # Prepare context for the LLM
        events_summary = []
        for event in events[-10:]:  # Last 10 events for context
            events_summary.append({
                "timestamp": event.get("timestamp", ""),
                "event_type": event.get("event_type", ""),
                "name": event.get("name", ""),
                "status": event.get("status", ""),
                "error_type": event.get("error_type", ""),
                "error_message": event.get("error_message", ""),
                "args_preview": event.get("args_preview", ""),
                "result_preview": event.get("result_preview", "")
            })
        
        system_prompt = """You are an expert software engineer analyzing a failed system trace and user feedback. 
        Your task is to provide a clear diagnosis of what went wrong and specific recommendations for fixing the code.

        Based on the trace events and user feedback, analyze:
        1. What the user expected vs what actually happened
        2. Which specific components or functions caused the issue
        3. Concrete code changes needed to fix the problem
        4. Root cause analysis

        Provide a structured response with:
        - Issue Summary
        - Root Cause Analysis  
        - Recommended Code Changes
        - Prevention Strategies

        Be specific about file names, function names, and code modifications when possible."""


        react_snippet = dedent("""\
import React from 'react'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend } from 'chart.js'
import { Bar, Line } from 'react-chartjs-2'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend)

type Props = {
  payload: any
}

export default function ResultCard({ payload }: Props) {
  const chartPayload = payload && payload.chartjs
  const hasImage = payload && payload.image_base64
  const answer = payload && payload.answer
  const alt = (payload && payload.alt) || 'Visualization'

  const renderChart = () => {
    if (!chartPayload) return null
    const type = (chartPayload.type || 'bar').toLowerCase()
    const data = chartPayload.data || { labels: [], datasets: [] }
    const options = chartPayload.options || {}
    
    if (type === 'line') {
      return <Line data={data} options={options} />
    }
    return <Bar data={data} options={options} />
  }

  return (
    <section className="card">
      <h3>Result</h3>

      {answer && typeof answer === 'string' && answer.trim() && (
        <div style={{ 
          margin: '0 0 20px', 
          padding: '16px', 
          background: 'rgba(79, 70, 229, 0.05)', 
          border: '1px solid rgba(79, 70, 229, 0.1)', 
          borderRadius: '8px',
          fontSize: '16px',
          lineHeight: '1.6'
        }}>
          {answer}
        </div>
      )}

      {chartPayload && (
        <div className="img-wrap">
          {renderChart()}
        </div>
      )}

      {hasImage && !chartPayload && (
        <div className="img-wrap">
          <img src={`data:image/png;base64,${payload.image_base64}`} alt={alt} />
        </div>
      )}

      <details className="details" style={{ marginTop: '20px' }}>
        <summary style={{ cursor: 'pointer', color: 'var(--muted)', fontSize: '14px' }}>
          View raw data
        </summary>
        <pre style={{ 
          marginTop: '12px', 
          fontSize: '12px', 
          background: 'rgba(0,0,0,0.2)', 
          padding: '12px', 
          borderRadius: '6px',
          maxHeight: '300px',
          overflow: 'auto'
        }}>
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    </section>
  )
}
""")
        
        user_message = f"""
        Trace ID: {trace_id}
        
        User Feedback:
        - Sentiment: {feedback.get('sentiment', 'Unknown')}
        - Categories: {feedback.get('categories', 'Unknown')}
        - Comments: {feedback.get('comments', 'No comments provided')}
        
        Recent Trace Events:
        {json.dumps(events_summary, indent=2)}
        
        Please analyze this trace and provide a diagnosis with specific fix recommendations.
        Additionally, please provide a code snippet that fixes the issue given the problem code: {react_snippet}
        please be concise with words and code solution. For the solution, reference the file and line numbers.
        """
        
        diagnosis = call_anthropic(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=2000
        )
        
        return diagnosis.strip()
        
    except Exception as e:
        return f"Error generating diagnosis: {str(e)}"


def _generate_insights(events: List[Dict[str, Any]] = None) -> str:
    # Use provided events or fallback to in-memory
    if events is None:
        events = _get_traces_from_db(limit=1000)
        if not events:
            events = EVENTS
    
    if not events:
        return "No events yet."

    # Basic aggregates
    by_name: Dict[str, Dict[str, int]] = defaultdict(lambda: {"count": 0, "errors": 0})
    long_spans: List[Dict[str, Any]] = []

    for e in events:
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