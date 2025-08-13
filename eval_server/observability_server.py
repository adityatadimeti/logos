from __future__ import annotations

import datetime
import os
import json
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

DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Logos Observability Dashboard</title>
  <style>
    :root {
      --bg: #0b0c10;
      --panel: #12131a;
      --text: #e6e6e6;
      --muted: #a3a3a3;
      --accent: #4f46e5;
      --border: #262738;
      --success: #10b981;
      --error: #ef4444;
      --warning: #f59e0b;
    }

    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; }
    body { 
      background: var(--bg); 
      color: var(--text); 
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
    }

    .page { min-height: 100vh; }
    .container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }

    .header { margin-bottom: 32px; }
    .header h1 { 
      margin: 0 0 8px; 
      font-size: 32px; 
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent), #7c3aed);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .header .subtitle { 
      color: var(--muted); 
      font-size: 16px;
      margin: 0;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }

    .stat-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      text-align: center;
    }

    .stat-card .value {
      font-size: 28px;
      font-weight: 700;
      color: var(--accent);
      margin: 0;
    }

    .stat-card .label {
      color: var(--muted);
      font-size: 14px;
      margin: 4px 0 0;
    }

    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      margin-bottom: 24px;
      overflow: hidden;
    }

    .card-header {
      padding: 20px 24px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .card-header h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
    }

    .card-body {
      padding: 0;
    }

    .table {
      width: 100%;
      border-collapse: collapse;
    }

    .table th,
    .table td {
      padding: 16px 24px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }

    .table th {
      background: rgba(79, 70, 229, 0.05);
      color: var(--text);
      font-weight: 600;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.025em;
    }

    .table tr:hover {
      background: rgba(79, 70, 229, 0.02);
    }

    .badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.025em;
    }

    .badge-success {
      background: rgba(16, 185, 129, 0.1);
      color: var(--success);
      border: 1px solid rgba(16, 185, 129, 0.2);
    }

    .badge-error {
      background: rgba(239, 68, 68, 0.1);
      color: var(--error);
      border: 1px solid rgba(239, 68, 68, 0.2);
    }

    .pill {
      display: inline-block;
      background: rgba(79, 70, 229, 0.1);
      color: var(--accent);
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 500;
      font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
      border: 1px solid rgba(79, 70, 229, 0.2);
    }

    .btn {
      display: inline-flex;
      align-items: center;
      padding: 6px 12px;
      background: var(--accent);
      color: white;
      text-decoration: none;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s ease;
    }

    .btn:hover {
      background: #3730a3;
      transform: translateY(-1px);
    }

    .insights {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
    }

    .insights h3 {
      margin: 0 0 16px;
      color: var(--text);
      font-size: 18px;
      font-weight: 600;
    }

    .insights pre {
      background: rgba(15, 16, 32, 0.5);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      color: var(--text);
      font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
      font-size: 14px;
      line-height: 1.5;
      overflow-x: auto;
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .nav-links {
      display: flex;
      gap: 16px;
      margin-bottom: 24px;
    }

    .nav-link {
      color: var(--muted);
      text-decoration: none;
      padding: 8px 12px;
      border-radius: 6px;
      transition: all 0.2s ease;
      font-size: 14px;
    }

    .nav-link:hover,
    .nav-link.active {
      color: var(--text);
      background: rgba(79, 70, 229, 0.1);
    }

    .empty-state {
      text-align: center;
      padding: 48px 24px;
      color: var(--muted);
    }

    .empty-state h3 {
      margin: 0 0 8px;
      color: var(--text);
    }

    .status-bar {
      margin-top: 16px;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .status-bar.connected {
      background-color: rgba(16, 185, 129, 0.1);
      color: var(--success);
      border: 1px solid rgba(16, 185, 129, 0.2);
    }

    .status-bar.disconnected {
      background-color: rgba(239, 68, 68, 0.1);
      color: var(--error);
      border: 1px solid rgba(239, 68, 68, 0.2);
    }

    .status-bar.error {
      background-color: rgba(239, 68, 68, 0.1);
      color: var(--error);
      border: 1px solid rgba(239, 68, 68, 0.2);
    }

    @media (max-width: 768px) {
      .container { padding: 16px; }
      .stats-grid { grid-template-columns: 1fr; }
      .table th, .table td { padding: 12px 16px; }
      .nav-links { flex-wrap: wrap; }
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="container">
      <div class="nav-links">
        <a href="/dashboard" class="nav-link active">Observability</a>
        <a href="http://127.0.0.1:5000" class="nav-link" target="_blank">Brain Server</a>
        <a href="http://127.0.0.1:3000" class="nav-link" target="_blank">Main App</a>
      </div>

      <header class="header">
        <h1>Observability Dashboard</h1>
        <p class="subtitle">Monitor traces, spans, and system performance in real-time</p>
        <div class="status-bar" id="status-bar">
          <!-- Status will be populated by JavaScript -->
        </div>
      </header>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="value">{{ total }}</div>
          <div class="label">Total Events</div>
        </div>
        <div class="stat-card">
          <div class="value">{{ trace_count }}</div>
          <div class="label">Active Traces</div>
        </div>
        <div class="stat-card">
          <div class="value">{{ traces|selectattr('error_count', 'gt', 0)|list|length }}</div>
          <div class="label">Traces with Errors</div>
        </div>
        <div class="stat-card" id="data-source-card">
          <div class="value" id="data-source-value">Loading...</div>
          <div class="label">Data Source</div>
        </div>
      </div>

      {% if traces %}
      <div class="card">
        <div class="card-header">
          <h2>Recent Traces</h2>
          <button onclick="location.reload()" class="btn">Refresh</button>
        </div>
        <div class="card-body">
          <table class="table">
            <thead>
              <tr>
                <th>Trace ID</th>
                <th>Spans</th>
                <th>Errors</th>
                <th>Duration</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {% for row in traces %}
              <tr>
                <td><span class="pill">{{ row.trace_id[:8] }}...</span></td>
                <td>{{ row.span_count }}</td>
                <td>
                  {% if row.error_count > 0 %}
                    <span class="badge badge-error">{{ row.error_count }}</span>
                  {% else %}
                    <span class="badge badge-success">0</span>
                  {% endif %}
                </td>
                <td>{{ row.duration_ms }}ms</td>
                <td>
                  <a href="/trace/{{ row.trace_id }}" class="btn">View Details</a>
                </td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
      {% else %}
      <div class="card">
        <div class="empty-state">
          <h3>No traces yet</h3>
          <p>Start making API calls to see observability data appear here.</p>
        </div>
      </div>
      {% endif %}

      {% if insights %}
      <div class="insights">
        <h3>System Insights</h3>
        <pre>{{ insights }}</pre>
      </div>
      {% endif %}
    </div>
  </div>

  <script>
    async function updateStatus() {
      try {
        const response = await fetch('/status');
        const status = await response.json();
        
        const statusBar = document.getElementById('status-bar');
        const dataSourceValue = document.getElementById('data-source-value');
        
        if (status.database.connected) {
          statusBar.className = 'status-bar connected';
          statusBar.innerHTML = `
            <span class="status-indicator online"></span>
            Database Connected (${status.database.trace_count} traces)
          `;
          dataSourceValue.textContent = 'Database';
          dataSourceValue.style.color = 'var(--success)';
        } else {
          statusBar.className = 'status-bar disconnected';
          statusBar.innerHTML = `
            <span class="status-indicator offline"></span>
            Using Memory Storage (${status.memory.trace_count} traces)
          `;
          dataSourceValue.textContent = 'Memory';
          dataSourceValue.style.color = 'var(--warning)';
        }
      } catch (error) {
        const statusBar = document.getElementById('status-bar');
        const dataSourceValue = document.getElementById('data-source-value');
        
        statusBar.className = 'status-bar error';
        statusBar.innerHTML = `
          <span class="status-indicator offline"></span>
          Status Check Failed
        `;
        dataSourceValue.textContent = 'Unknown';
        dataSourceValue.style.color = 'var(--error)';
      }
    }

    // Update status on page load and every 15 seconds
    updateStatus();
    setInterval(updateStatus, 15000);

    // Auto-refresh every 10 seconds
    setInterval(() => {
      if (!document.hidden) {
        location.reload();
      }
    }, 10000);
  </script>
</body>
</html>
"""

TRACE_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Trace {{ trace_id[:8] }}... - Logos Observability</title>
  <style>
    :root {
      --bg: #0b0c10;
      --panel: #12131a;
      --text: #e6e6e6;
      --muted: #a3a3a3;
      --accent: #4f46e5;
      --border: #262738;
      --success: #10b981;
      --error: #ef4444;
      --warning: #f59e0b;
    }

    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; }
    body { 
      background: var(--bg); 
      color: var(--text); 
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
    }

    .page { min-height: 100vh; }
    .container { max-width: 1400px; margin: 0 auto; padding: 32px 24px; }

    .header { margin-bottom: 32px; }
    .header h1 { 
      margin: 0 0 8px; 
      font-size: 28px; 
      font-weight: 700;
      color: var(--text);
    }
    .header .subtitle { 
      color: var(--muted); 
      font-size: 16px;
      margin: 0 0 16px;
    }

    .trace-id {
      background: rgba(79, 70, 229, 0.1);
      color: var(--accent);
      padding: 6px 12px;
      border-radius: 8px;
      font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
      font-size: 14px;
      border: 1px solid rgba(79, 70, 229, 0.2);
      display: inline-block;
      margin-bottom: 24px;
    }

    .nav-links {
      display: flex;
      gap: 16px;
      margin-bottom: 24px;
    }

    .nav-link {
      color: var(--muted);
      text-decoration: none;
      padding: 8px 12px;
      border-radius: 6px;
      transition: all 0.2s ease;
      font-size: 14px;
    }

    .nav-link:hover {
      color: var(--text);
      background: rgba(79, 70, 229, 0.1);
    }

    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
    }

    .card-header {
      padding: 20px 24px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .card-header h2 {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
    }

    .table {
      width: 100%;
      border-collapse: collapse;
    }

    .table th,
    .table td {
      padding: 12px 16px;
      text-align: left;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }

    .table th {
      background: rgba(79, 70, 229, 0.05);
      color: var(--text);
      font-weight: 600;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.025em;
    }

    .table tr:hover {
      background: rgba(79, 70, 229, 0.02);
    }

    .table td.timestamp {
      color: var(--muted);
      font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
      font-size: 12px;
      width: 140px;
    }

    .table td.type {
      font-weight: 500;
      font-size: 13px;
    }

    .table td.name {
      font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
      font-size: 13px;
      max-width: 200px;
      word-break: break-word;
    }

    .status-ok {
      background: rgba(16, 185, 129, 0.1);
      color: var(--success);
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      border: 1px solid rgba(16, 185, 129, 0.2);
    }

    .status-error {
      background: rgba(239, 68, 68, 0.1);
      color: var(--error);
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      border: 1px solid rgba(239, 68, 68, 0.2);
    }

    .preview {
      background: rgba(15, 16, 32, 0.5);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px;
      font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
      font-size: 12px;
      line-height: 1.4;
      color: var(--muted);
      white-space: pre-wrap;
      word-break: break-word;
      max-width: 300px;
      max-height: 100px;
      overflow-y: auto;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      padding: 8px 16px;
      background: var(--accent);
      color: white;
      text-decoration: none;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s ease;
    }

    .btn:hover {
      background: #3730a3;
      transform: translateY(-1px);
    }

    .btn-secondary {
      background: rgba(79, 70, 229, 0.1);
      color: var(--accent);
      border: 1px solid rgba(79, 70, 229, 0.2);
    }

    .btn-secondary:hover {
      background: rgba(79, 70, 229, 0.2);
      transform: translateY(-1px);
    }

    @media (max-width: 768px) {
      .container { padding: 16px; }
      .table th, .table td { padding: 8px; font-size: 12px; }
      .card-header { flex-direction: column; gap: 12px; align-items: flex-start; }
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="container">
      <div class="nav-links">
        <a href="/dashboard" class="nav-link">← Back to Dashboard</a>
        <a href="http://127.0.0.1:5000" class="nav-link" target="_blank">Brain Server</a>
        <a href="http://127.0.0.1:3000" class="nav-link" target="_blank">Main App</a>
      </div>

      <header class="header">
        <h1>Trace Details</h1>
        <p class="subtitle">{{ count }} events in this trace</p>
        <div class="trace-id">{{ trace_id }}</div>
      </header>

      <div class="card">
        <div class="card-header">
          <h2>Trace Events</h2>
          <div style="display: flex; gap: 8px;">
            <button onclick="location.reload()" class="btn btn-secondary">Refresh</button>
            <a href="/dashboard" class="btn">Back to Dashboard</a>
          </div>
        </div>
        <div style="overflow-x: auto;">
          <table class="table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Event Type</th>
                <th>Name</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Preview</th>
              </tr>
            </thead>
            <tbody>
              {% for e in events %}
              <tr>
                <td class="timestamp">{{ e.timestamp[-12:-4] if e.timestamp else '' }}</td>
                <td class="type">{{ e.event_type or '' }}</td>
                <td class="name">{{ e.name or '' }}</td>
                <td>
                  {% if e.status == 'error' %}
                    <span class="status-error">Error</span>
                  {% elif e.status == 'ok' %}
                    <span class="status-ok">OK</span>
                  {% endif %}
                </td>
                <td>
                  {% if e.duration_ms %}
                    {{ e.duration_ms }}ms
                  {% endif %}
                </td>
                <td>
                  {% if e.preview %}
                    <div class="preview">{{ e.preview }}</div>
                  {% endif %}
                </td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""


@app.route("/log", methods=["POST"])
def log_event():
    data = request.get_json(force=True, silent=True) or {}
    # add server-side timestamp
    data["server_ts"] = datetime.datetime.utcnow().isoformat()
    
    # Store in memory (for fallback)
    EVENTS.append(data)
    # keep a rolling window
    if len(EVENTS) > 5000:
        del EVENTS[:1000]
    
    # Also store in database
    _insert_trace_event(data)
    
    return jsonify({"ok": True})


@app.route("/dashboard")
def dashboard():
    # Try to load from database first, fallback to in-memory
    events = _get_traces_from_db(limit=1000)
    if not events:
        events = EVENTS
    
    # Aggregate traces
    by_trace: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
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

    insights = _generate_insights(events)

    return render_template_string(
        DASHBOARD_HTML,
        total=len(events),
        trace_count=len(by_trace),
        traces=rows[:100],
        insights=insights,
    )


@app.route("/trace/<trace_id>")
def trace_view(trace_id: str):
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
            }
        )
    return render_template_string(TRACE_HTML, trace_id=trace_id, count=len(items), events=enriched)


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
    return jsonify({"ok": True, "endpoints": ["/log", "/dashboard", "/trace/<trace_id>"]})


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