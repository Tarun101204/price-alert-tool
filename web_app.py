#!/usr/bin/env python3
"""
Interactive Web Interface for Price Alert Tool.
Runs on Python Standard Library (http.server) - ZERO dependencies required!
Allows uploading CSV and JSON files or running samples directly in the browser.
"""

import cgi
import http.server
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import urllib.parse
from decimal import Decimal
from alerts import process_alerts, load_prices, load_rules

PORT = 8080
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Price Alert Tool - Interactive Runner</title>
    <style>
        :root {
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --border: #334155;
            --success: #10b981;
            --danger: #ef4444;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        body { background: var(--bg); color: var(--text); padding: 2rem 1rem; line-height: 1.5; }
        .container { max-width: 900px; margin: 0 auto; }
        header { margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; }
        h1 { font-size: 1.875rem; font-weight: 700; color: #fff; margin-bottom: 0.5rem; }
        p.subtitle { color: var(--text-muted); font-size: 0.95rem; }
        .badge { display: inline-block; background: #1e3a8a; color: #93c5fd; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; margin-bottom: 0.5rem; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }
        @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
        .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.25rem; }
        .card-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; color: #e2e8f0; display: flex; align-items: center; justify-content: space-between; }
        textarea { width: 100%; height: 220px; background: #0b1120; border: 1px solid var(--border); border-radius: 0.5rem; color: #f1f5f9; padding: 0.75rem; font-family: 'Courier New', Courier, monospace; font-size: 0.85rem; resize: vertical; outline: none; }
        textarea:focus { border-color: var(--primary); }
        .btn-group { display: flex; gap: 0.75rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
        button { cursor: pointer; border: none; border-radius: 0.5rem; padding: 0.75rem 1.25rem; font-size: 0.95rem; font-weight: 600; transition: background 0.15s ease; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-secondary { background: #334155; color: #e2e8f0; }
        .btn-secondary:hover { background: #475569; }
        .btn-test { background: #065f46; color: #a7f3d0; }
        .btn-test:hover { background: #047857; }
        .output-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.25rem; }
        pre.output-box { background: #0b1120; border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem; color: #38bdf8; font-family: 'Courier New', Courier, monospace; font-size: 0.95rem; min-height: 120px; white-space: pre-wrap; overflow-x: auto; }
        .empty-state { color: var(--text-muted); font-style: italic; }
        .footer { margin-top: 2rem; text-align: center; color: var(--text-muted); font-size: 0.85rem; border-top: 1px solid var(--border); padding-top: 1.5rem; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="badge">Wissen Technology Campus Assessment</div>
            <h1>Price Alert Tool - Live Interactive Runner</h1>
            <p class="subtitle">Evaluates daily prices against configured alert rules (level & ma_cross) in pure Python.</p>
        </header>

        <div class="btn-group">
            <button class="btn-primary" onclick="runAlerts()">Run Alert Rules</button>
            <button class="btn-secondary" onclick="loadSample()">Load Sample Data</button>
            <button class="btn-secondary" onclick="loadExtended()">Load 30-Day Extended Data</button>
            <button class="btn-test" onclick="runTests()">Run Unit Tests (31 Cases)</button>
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-title">
                    <span>Prices CSV (date,instrument,close)</span>
                </div>
                <textarea id="pricesCsv" placeholder="date,instrument,close..."></textarea>
            </div>
            <div class="card">
                <div class="card-title">
                    <span>Rules JSON (level, ma_cross)</span>
                </div>
                <textarea id="rulesJson" placeholder='[{"id":"r1",...}]'></textarea>
            </div>
        </div>

        <div class="output-card">
            <div class="card-title">
                <span>Tool Output (Standard Output)</span>
                <span id="statusIndicator" style="font-size:0.85rem; font-weight:normal; color:var(--text-muted);">Ready</span>
            </div>
            <pre class="output-box" id="outputBox"><span class="empty-state">Click 'Run Alert Rules' or 'Load Sample Data' to evaluate...</span></pre>
        </div>

        <div class="footer">
            Zero-dependency Python 3 CLI &bull; Runs <code>python alerts.py prices.csv rules.json</code> behind the scenes
        </div>
    </div>

    <script>
        const samplePrices = `date,instrument,close\\n2026-09-01,INFY,1520.50\\n2026-09-01,TCS,3890.00\\n2026-09-02,INFY,1534.10\\n2026-09-02,TCS,3902.25\\n2026-09-03,INFY,1498.00`;
        const sampleRules = `[\\n  {\\n    "id": "r1",\\n    "instrument": "INFY",\\n    "type": "level",\\n    "direction": "below",\\n    "level": 1500\\n  },\\n  {\\n    "id": "r2",\\n    "instrument": "TCS",\\n    "type": "ma_cross",\\n    "short": 5,\\n    "long": 20,\\n    "direction": "above"\\n  }\\n]`;

        function loadSample() {
            document.getElementById('pricesCsv').value = samplePrices.replace(/\\\\n/g, '\\n');
            document.getElementById('rulesJson').value = sampleRules.replace(/\\\\n/g, '\\n');
            document.getElementById('statusIndicator').innerText = "Loaded Brief Sample Data";
        }

        async function loadExtended() {
            const res = await fetch('/api/extended_data');
            const data = await res.json();
            document.getElementById('pricesCsv').value = data.prices;
            document.getElementById('rulesJson').value = data.rules;
            document.getElementById('statusIndicator').innerText = "Loaded 30-Day Extended Data";
        }

        async function runAlerts() {
            const prices = document.getElementById('pricesCsv').value;
            const rules = document.getElementById('rulesJson').value;
            const outputBox = document.getElementById('outputBox');
            const status = document.getElementById('statusIndicator');

            if (!prices.trim() || !rules.trim()) {
                outputBox.innerText = "Please provide both Prices CSV and Rules JSON (or click 'Load Sample Data').";
                return;
            }

            status.innerText = "Running evaluation...";
            outputBox.innerText = "Processing...";

            try {
                const res = await fetch('/api/run_alerts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prices, rules })
                });
                const result = await res.json();
                if (result.error) {
                    outputBox.style.color = "#ef4444";
                    outputBox.innerText = "Error:\\n" + result.error;
                    status.innerText = "Error encountered";
                } else {
                    outputBox.style.color = "#38bdf8";
                    outputBox.innerText = result.output || "(No alerts fired for the given rules and prices)";
                    status.innerText = "Completed successfully";
                }
            } catch (err) {
                outputBox.style.color = "#ef4444";
                outputBox.innerText = "Failed to communicate with server: " + err;
                status.innerText = "Request failed";
            }
        }

        async function runTests() {
            const outputBox = document.getElementById('outputBox');
            const status = document.getElementById('statusIndicator');
            status.innerText = "Running full test suite...";
            outputBox.style.color = "#38bdf8";
            outputBox.innerText = "Executing 31 unit & integration tests...";

            try {
                const res = await fetch('/api/run_tests');
                const result = await res.json();
                outputBox.style.color = result.success ? "#34d399" : "#ef4444";
                outputBox.innerText = result.output;
                status.innerText = result.success ? "All 31 Tests Passed!" : "Tests Failed";
            } catch (err) {
                outputBox.style.color = "#ef4444";
                outputBox.innerText = "Failed to run tests: " + err;
                status.innerText = "Test run error";
            }
        }

        // Auto load sample on start
        loadSample();
    </script>
</body>
</html>
"""

class AlertServerHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path == "/api/extended_data":
            ext_path = os.path.join(PROJECT_DIR, "data", "extended_prices.csv")
            rule_path = os.path.join(PROJECT_DIR, "data", "sample_rules.json")
            prices_txt = ""
            rules_txt = ""
            if os.path.exists(ext_path):
                with open(ext_path, "r", encoding="utf-8") as f:
                    prices_txt = f.read()
            if os.path.exists(rule_path):
                with open(rule_path, "r", encoding="utf-8") as f:
                    rules_txt = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"prices": prices_txt, "rules": rules_txt}).encode("utf-8"))
        elif self.path == "/api/run_tests":
            runner_script = os.path.join(PROJECT_DIR, "run_tests.py")
            res = subprocess.run([sys.executable, runner_script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": res.returncode == 0, "output": res.stdout}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == "/api/run_alerts":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                prices_content = data.get("prices", "")
                rules_content = data.get("rules", "")

                with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as pf:
                    pf.write(prices_content)
                    pf_name = pf.name
                with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as rf:
                    rf.write(rules_content)
                    rf_name = rf.name

                alerts_script = os.path.join(PROJECT_DIR, "alerts.py")
                res = subprocess.run([sys.executable, alerts_script, pf_name, rf_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                os.remove(pf_name)
                os.remove(rf_name)

                if res.returncode == 0:
                    resp = {"output": res.stdout.strip()}
                else:
                    resp = {"error": res.stderr.strip() or "Evaluation error occurred."}

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")


def run_web_server(port=PORT):
    server_address = ("", port)
    httpd = socketserver.TCPServer(server_address, AlertServerHandler)
    print(f"Price Alert Tool Web Server running at: http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_web_server(port)
