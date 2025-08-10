from flask import Flask, request, jsonify, render_template_string
import datetime
from rules_engine import RuleEngine
from intervention_rules import get_intervention_rules
import json

app = Flask(__name__)

# In-memory store for intervention history
intervention_history = []

# Initialize the rule engine
rules = get_intervention_rules()
rule_engine = RuleEngine(rules)

@app.route('/intervene', methods=['POST'])
def intervene():
    """
    Analyzes the content fetched by the agent and returns an instruction.
    """
    data = request.json
    print(f"[Brain Server] Received data for function: {data.get('function_name')}")
    
    # Use the rule engine to decide on an action
    action_result = rule_engine.evaluate(data)
    
    if action_result:
        print(f"[Brain Server] Intervening with action: {action_result}")
        if callable(action_result):
            response = action_result(data)
        else:
            response = action_result
    else:
        # Default action: No intervention, proceed with original content
        print("[Brain Server] No intervention rule matched. Allowing original content.")
        response = {"action": "allow_original", "value": data.get('content')}

    # Log the event for the dashboard
    log_entry = {
        'timestamp': datetime.datetime.now().isoformat(),
        'request': {
            'function_name': data.get('function_name'),
            'url': data.get('kwargs', {}).get('url')
        },
        'content_preview': str(data.get('content'))[:200] + '...' if data.get('content') else 'N/A',
        'content_length': data.get('content_length'),
        'decision': response.get('action'),
        'final_output': str(response.get('value'))[:200] + '...' if response.get('value') else 'N/A'
    }
    intervention_history.append(log_entry)
    
    return jsonify(response)

@app.route('/history')
def get_history():
    """Returns the history of all interventions."""
    return jsonify(list(reversed(intervention_history)))

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Logos AI - Content Analysis Dashboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background-color: #f9fafb; color: #111827; }
        .header { background-color: #ffffff; padding: 1rem 2rem; border-bottom: 1px solid #e5e7eb; display: flex; align-items: center; justify-content: space-between; }
        .header h1 { font-size: 1.5rem; font-weight: 600; color: #111827; }
        .container { padding: 2rem; max-width: 80rem; margin-left: auto; margin-right: auto; }
        .card { background-color: #ffffff; border-radius: 0.5rem; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06); margin-bottom: 1.5rem; }
        .card-header { padding: 1rem 1.5rem; border-bottom: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center; }
        .card-header h2 { font-size: 1.125rem; font-weight: 600; margin: 0; }
        .card-body { padding: 1.5rem; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
        .grid-item { background-color: #f3f4f6; padding: 1rem; border-radius: 0.375rem; }
        .grid-item strong { display: block; color: #4b5563; font-weight: 500; font-size: 0.875rem; margin-bottom: 0.25rem; }
        pre { background-color: #1f2937; color: #f3f4f6; padding: 1rem; border-radius: 0.375rem; white-space: pre-wrap; word-wrap: break-word; font-family: "SF Mono", "Fira Code", "Fira Mono", "Roboto Mono", monospace; font-size: 0.875rem; max-height: 200px; overflow-y: auto; }
        .badge { display: inline-block; padding: 0.35em 0.65em; font-size: 0.75em; font-weight: 700; line-height: 1; text-align: center; white-space: nowrap; vertical-align: baseline; border-radius: 0.375rem; }
        .badge-red { color: #991b1b; background-color: #fee2e2; }
        .badge-green { color: #065f46; background-color: #d1fae5; }
        .badge-gray { color: #374151; background-color: #f3f4f6; }
    </style>
</head>
<body>
    <header class="header">
        <h1>Content Analysis Dashboard</h1>
    </header>
    <div class="container" id="history-container">
        <!-- History cards will be inserted here -->
    </div>

    <script>
        function getDecisionBadge(decision) {
            if (decision === 'return_value') {
                return `<span class="badge badge-red">Intervened</span>`;
            } else if (decision === 'allow_original') {
                return `<span class="badge badge-green">Allowed</span>`;
            }
            return `<span class="badge badge-gray">Unknown</span>`;
        }

        async function fetchHistory() {
            try {
                const response = await fetch('/history');
                const history = await response.json();
                const container = document.getElementById('history-container');
                container.innerHTML = ''; // Clear existing

                if (history.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #6b7280;">No agent activity recorded yet. Run `python base_agent.py` to see data.</p>';
                    return;
                }

                history.forEach(entry => {
                    const card = document.createElement('div');
                    card.className = 'card';
                    card.innerHTML = `
                        <div class="card-header">
                            <h2>${entry.request.function_name}</h2>
                            <span style="font-size: 0.875rem; color: #6b7280;">${new Date(entry.timestamp).toLocaleString()}</span>
                        </div>
                        <div class="card-body">
                            <div class="grid">
                                <div class="grid-item">
                                    <strong>Agent Input (URL)</strong>
                                    <span>${entry.request.url}</span>
                                </div>
                                <div class="grid-item">
                                    <strong>Content Length</strong>
                                    <span>${entry.content_length} bytes</span>
                                </div>
                                <div class="grid-item">
                                    <strong>Brain Decision</strong>
                                    ${getDecisionBadge(entry.decision)}
                                </div>
                            </div>
                            <div style="margin-top: 1.5rem;">
                                <strong>Content Preview</strong>
                                <pre>${escapeHtml(entry.content_preview)}</pre>
                            </div>
                            <div style="margin-top: 1.5rem;">
                                <strong>Final Output</strong>
                                <pre>${escapeHtml(entry.final_output)}</pre>
                            </div>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch (error) {
                console.error("Failed to fetch history:", error);
                const container = document.getElementById('history-container');
                container.innerHTML = '<p style="text-align: center; color: red;">Could not load history.</p>';
            }
        }
        
        function escapeHtml(unsafe) {
            if (!unsafe) return '';
            return unsafe
                 .replace(/&/g, "&amp;")
                 .replace(/</g, "&lt;")
                 .replace(/>/g, "&gt;")
                 .replace(/"/g, "&quot;")
                 .replace(/'/g, "&#039;");
        }

        fetchHistory();
        setInterval(fetchHistory, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Serves the main dashboard HTML page."""
    return render_template_string(HTML_TEMPLATE)


if __name__ == '__main__':
    # Run on http://127.0.0.1:5000
    app.run(port=5000, debug=True)