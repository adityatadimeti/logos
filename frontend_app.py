from __future__ import annotations

import os
from flask import Flask, request, render_template_string

from base_agent import run_orchestrator

app = Flask(__name__)

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Banking Assistant</title>
    <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 2rem; }
    .container { max-width: 800px; margin: auto; }
    textarea { width: 100%; height: 120px; font-size: 16px; padding: 10px; }
    button { padding: 10px 16px; font-size: 16px; }
    pre { background: #f5f5f5; padding: 12px; overflow: auto; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-top: 16px; }
    .img-wrap { margin-top: 12px; }
    .img-wrap img { max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 6px; }
    </style>
</head>
<body>
  <div class="container">
    <h1>Banking Assistant</h1>
    <p>Ask a question about your banking data. Example: <code>get id,amount,merchant from transactions where category=shopping limit 10</code></p>
    <form method="POST">
      <textarea name="question" placeholder="What did my shopping transactions look like this week?">{{ question or '' }}</textarea>
      <div style="margin-top: 8px;">
        <button type="submit">Ask</button>
      </div>
    </form>

    {% if payload %}
    <div class="card">
      <h3>Result</h3>
      {% if payload.image_base64 %}
        <div class="img-wrap">
          <img src="data:image/png;base64,{{ payload.image_base64 }}" alt="{{ payload.alt or 'Visualization' }}" />
        </div>
        <details style="margin-top: 12px;">
          <summary>Raw result JSON</summary>
          <pre>{{ result | tojson(indent=2) }}</pre>
        </details>
      {% else %}
        <pre>{{ payload | tojson(indent=2) }}</pre>
      {% endif %}
    </div>
    {% endif %}
  </div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    question = None
    result = None
    payload = None
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if question:
            result = run_orchestrator(question)
            # Normalize for UI: backend returns {result: {...}} on success
            if isinstance(result, dict) and "result" in result:
                payload = result.get("result")
            else:
                payload = result
    return render_template_string(INDEX_HTML, question=question, result=result, payload=payload)


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5001"))
    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    main() 