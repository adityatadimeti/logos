from __future__ import annotations

import os
from flask import Flask, request, render_template_string, jsonify

from base_agent import run_orchestrator

app = Flask(__name__)

# Minimal index page (frontend uses Vite; this is just a placeholder)
INDEX_HTML = """
<!doctype html>
<html>
  <head><meta charset="utf-8" /><title>Logos API</title></head>
  <body>
    <h3>Logos Backend</h3>
    <p>POST JSON to <code>/api/ask</code> with {"question": "..."}</p>
  </body>
</html>
"""

@app.route("/", methods=["GET"])  # frontend runs separately; keep simple index
def index():
    return render_template_string(INDEX_HTML)


@app.route("/api/ask", methods=["POST"])  # React UI calls this
def api_ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Empty question"}), 400

    result = run_orchestrator(question)
    # Normalize for API: backend returns {result: {...}} on success
    if isinstance(result, dict) and "result" in result:
        payload = result
    else:
        payload = {"result": result}
    return jsonify(payload)


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5001"))
    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    main() 