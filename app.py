"""
Cloud IQ — Flask Web Application
Entry point for both local development and Render cloud deployment.
Run locally:  python app.py
Render runs:  gunicorn app:app
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, request, send_file, Response

# ── Bootstrap logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cloud_iq")

# ── Startup state ─────────────────────────────────────────────────────────────
_startup_done = threading.Event()  # set when initial scan completes
_startup_error: str = ""           # holds error message if startup fails

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "project" / "templates"),
    static_folder=str(Path(__file__).parent / "project" / "website"),
    static_url_path="/static",
)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

# ── Lazy-import project modules (safe even if some deps missing) ──────────────
from project.config import (
    ALL_WEEKS_CSV,
    BUDGET_THRESHOLD,
    CURRENT_WEEK_CSV,
    DATA_DIR,
    ENABLE_AI_AGENT,
    ENABLE_DISCORD_ALERTS,
    ENABLE_EMAIL_REPORT,
    ENABLE_GITHUB_ISSUES,
    OUTPUT_DIR,
    PORT,
)
from project.src.ai_agent import AIAnalyzerAgent
from project.src.detector import ResourceDetector
from project.src.discord_alert import DiscordAlerter
from project.src.email_report import EmailReporter
from project.src.github_issues import GitHubIssueManager
from project.src.html_report import HTMLReportGenerator
from project.src.llm_analyzer import LLMAnalyzer
from project.src.reader import CSVReader

# ── Singleton components (initialised once at startup) ────────────────────────
reader        = CSVReader()
detector      = ResourceDetector()
html_gen      = HTMLReportGenerator()
analyzer      = LLMAnalyzer()
alerter       = DiscordAlerter()
reporter      = EmailReporter()
issue_manager = GitHubIssueManager()

# Ensure output dir exists
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Background startup scan
# ─────────────────────────────────────────────────────────────────────────────

def _background_startup() -> None:
    """Run initial scan in a background thread so first HTTP request is instant."""
    global _startup_error
    dash = Path(OUTPUT_DIR) / "dashboard.html"
    if dash.exists():
        logger.info("Dashboard already exists — skipping startup scan.")
        _startup_done.set()
        return
    try:
        logger.info("☁️  Running background startup scan...")
        _run_pipeline()
        logger.info("✅  Startup scan complete — dashboard ready.")
    except Exception as exc:
        _startup_error = str(exc)
        logger.error("Startup scan failed: %s", exc)
    finally:
        _startup_done.set()


# Launch background scan immediately (works with gunicorn multi-worker too)
_t = threading.Thread(target=_background_startup, daemon=True)
_t.start()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(name: str, fn, *a, **kw) -> Any:
    try:
        return fn(*a, **kw)
    except Exception as e:
        logger.warning("Action '%s' failed: %s", name, e)
        return None


def _weekly_trends() -> List[Dict[str, Any]]:
    trends = []
    for filepath in ALL_WEEKS_CSV:
        resources = _safe(f"load {filepath}", reader.load_resources, Path(DATA_DIR) / filepath) or []
        findings  = detector.generate_report_data(resources)
        trends.append({
            "week":   Path(filepath).stem,
            "waste":  sum(f["potential_saving"] for f in findings),
            "issues": len(findings),
        })
    return trends


def _run_pipeline(
    enable_discord: bool = False,
    enable_email:   bool = False,
    enable_github:  bool = False,
) -> Dict[str, Any]:
    """Core scan pipeline — runs detection, AI analysis, and optional notifications."""
    csv_path  = Path(DATA_DIR) / CURRENT_WEEK_CSV
    resources = _safe("load CSV", reader.load_resources, csv_path) or []
    findings  = detector.generate_report_data(resources)

    analyzed = (
        _safe("AI analysis", AIAnalyzerAgent(ENABLE_AI_AGENT, analyzer).analyze, findings)
        or findings
    )

    total_saving = sum(
        e.get("analysis", {}).get("estimated_saving_value", e.get("potential_saving", 0.0))
        for e in analyzed
    )
    total_cost = sum(r.get("cost_monthly_usd", 0.0) for r in resources)
    over_budget = total_cost > BUDGET_THRESHOLD

    # ── GitHub Issues ──────────────────────────────────────────────────────────
    github_urls: List[str] = []
    if enable_github and ENABLE_GITHUB_ISSUES:
        github_urls = _safe("GitHub issues", issue_manager.file_all_issues, analyzed) or []

    # ── Discord Notifications ──────────────────────────────────────────────────
    if enable_discord:
        for entry in analyzed:
            if entry.get("analysis", {}).get("severity") == "P0":
                _safe("Discord P0 alert", alerter.send_critical_alert,
                      entry["resource"], entry["analysis"])
        _safe("Discord summary", alerter.send_summary, analyzed, total_saving)
        if over_budget:
            _safe("Discord budget alert", alerter.send_budget_alert,
                  total_cost, BUDGET_THRESHOLD, total_saving)

    # ── Email Notifications ────────────────────────────────────────────────────
    if enable_email:
        _safe("Email report", reporter.send_report, analyzed, total_saving, github_urls)
        if over_budget:
            _safe("Email budget alert", reporter.send_budget_alert,
                  total_cost, total_saving, analyzed)

    # ── Dashboard HTML ────────────────────────────────────────────────────────
    trends = _weekly_trends()
    dashboard_path = _safe(
        "dashboard",
        html_gen.generate_dashboard,
        resources, analyzed, total_saving, trends, github_urls,
        OUTPUT_DIR, False,          # open_browser=False on server
    ) or ""

    return {
        "resources":      resources,
        "findings":       analyzed,
        "total_saving":   total_saving,
        "total_cost":     total_cost,
        "over_budget":    over_budget,
        "budget_threshold": BUDGET_THRESHOLD,
        "github_urls":    github_urls,
        "trends":         trends,
        "dashboard_path": dashboard_path,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
@app.route("/dashboard")
def index() -> Response:
    """Serve the interactive cost dashboard (instant — scan runs in background)."""
    dash = Path(OUTPUT_DIR) / "dashboard.html"
    if dash.exists():
        return send_file(str(dash.absolute()), mimetype="text/html")
    # Dashboard not ready yet — serve animated loading page
    return Response(_loading_page(), mimetype="text/html")


def _loading_page() -> str:
    """Beautiful animated loading page that auto-refreshes every 4 seconds."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="4">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cloud IQ — Loading...</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
      background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
      font-family: 'Segoe UI', system-ui, sans-serif;
      color: #fff;
    }
    .card {
      text-align: center;
      padding: 60px 80px;
      background: rgba(255,255,255,0.07);
      backdrop-filter: blur(20px);
      border-radius: 24px;
      border: 1px solid rgba(255,255,255,0.15);
      box-shadow: 0 25px 60px rgba(0,0,0,0.4);
      max-width: 500px;
    }
    .logo { font-size: 3rem; margin-bottom: 16px; }
    h1 { font-size: 2rem; font-weight: 700; margin-bottom: 8px;
         background: linear-gradient(90deg,#a78bfa,#60a5fa); -webkit-background-clip:text;
         -webkit-text-fill-color:transparent; }
    p { color: rgba(255,255,255,0.6); font-size: 1rem; margin-bottom: 40px; }
    .spinner {
      width: 56px; height: 56px; margin: 0 auto 28px;
      border: 4px solid rgba(255,255,255,0.1);
      border-top-color: #a78bfa;
      border-radius: 50%;
      animation: spin 0.9s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .steps { list-style: none; text-align: left; display: inline-block; }
    .steps li { padding: 6px 0; font-size: 0.9rem; color: rgba(255,255,255,0.55); }
    .steps li::before { content: '✓ '; color: #34d399; }
    .steps li.active::before { content: '⟳ '; color: #a78bfa; animation: spin 1s linear infinite; display: inline-block; }
    .steps li.pending::before { content: '○ '; color: rgba(255,255,255,0.25); }
    .refresh-note { margin-top: 24px; font-size: 0.78rem; color: rgba(255,255,255,0.3); }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">☁️</div>
    <h1>Cloud IQ</h1>
    <p>AI-powered cloud cost optimizer is warming up...</p>
    <div class="spinner"></div>
    <ul class="steps">
      <li>Server started</li>
      <li class="active">Running cost analysis &amp; AI insights</li>
      <li class="pending">Building interactive dashboard</li>
      <li class="pending">Ready to serve</li>
    </ul>
    <p class="refresh-note">This page refreshes automatically every 4 seconds</p>
  </div>
</body>
</html>
"""


@app.route("/api/scan", methods=["GET", "POST"])
def api_scan():
    """Run the full pipeline. Query params: ?discord=1&email=1&github=1"""
    params = request.get_json(silent=True) or request.args
    enable_discord = str(params.get("discord", "0")) in ("1", "true", "yes") or ENABLE_DISCORD_ALERTS
    enable_email   = str(params.get("email",   "0")) in ("1", "true", "yes") or ENABLE_EMAIL_REPORT
    enable_github  = str(params.get("github",  "0")) in ("1", "true", "yes") or ENABLE_GITHUB_ISSUES

    result = _run_pipeline(enable_discord=enable_discord, enable_email=enable_email, enable_github=enable_github)

    findings_out = []
    for entry in result["findings"]:
        res      = entry.get("resource", {})
        analysis = entry.get("analysis", {})
        findings_out.append({
            "resource_id":      res.get("resource_id"),
            "type":             res.get("type"),
            "region":           res.get("region"),
            "cpu":              res.get("cpu_avg_percent"),
            "cost":             res.get("cost_monthly_usd"),
            "severity":         analysis.get("severity", entry.get("severity", "P2")),
            "potential_saving": analysis.get("estimated_saving", ""),
            "recommendation":   analysis.get("recommendation", ""),
        })

    return jsonify({
        "success":          True,
        "resources_scanned": len(result["resources"]),
        "issues_found":     len(result["findings"]),
        "total_saving":     round(result["total_saving"], 2),
        "total_cost":       round(result["total_cost"], 2),
        "over_budget":      result["over_budget"],
        "budget_threshold": result["budget_threshold"],
        "findings":         findings_out,
        "github_urls":      result["github_urls"],
    })


@app.route("/api/notify/email", methods=["POST"])
def api_notify_email():
    """Trigger email notification manually."""
    result = _run_pipeline(enable_email=True)
    return jsonify({
        "success":      True,
        "message":      "Email notification sent.",
        "issues_found": len(result["findings"]),
        "total_saving": round(result["total_saving"], 2),
        "over_budget":  result["over_budget"],
    })


@app.route("/api/notify/discord", methods=["POST"])
def api_notify_discord():
    """Trigger Discord notification manually."""
    result = _run_pipeline(enable_discord=True)
    return jsonify({
        "success":      True,
        "message":      "Discord notification sent.",
        "issues_found": len(result["findings"]),
        "total_saving": round(result["total_saving"], 2),
        "over_budget":  result["over_budget"],
    })


@app.route("/api/notify/all", methods=["POST"])
def api_notify_all():
    """Trigger both email and Discord at once."""
    result = _run_pipeline(enable_email=True, enable_discord=True)
    return jsonify({
        "success":      True,
        "message":      "Email and Discord notifications sent.",
        "issues_found": len(result["findings"]),
        "total_saving": round(result["total_saving"], 2),
        "over_budget":  result["over_budget"],
    })


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Answer a cloud cost question via Gemini AI."""
    data     = request.get_json(silent=True) or {}
    question = str(data.get("question", "")).strip()
    if not question:
        return jsonify({"error": "No question provided."}), 400
    answer = _safe("chat", analyzer.answer_question, question) or "Could not answer right now."
    return jsonify({"question": question, "answer": answer})


@app.route("/api/health")
def api_health():
    """Health check for Render uptime monitoring."""
    return jsonify({
        "status":   "healthy",
        "service":  "cloud-iq",
        "version":  "2.0.0",
        "ready":    _startup_done.is_set(),
        "dashboard": (Path(OUTPUT_DIR) / "dashboard.html").exists(),
    })


@app.route("/api/ping")
def api_ping():
    """Ultra-lightweight keep-alive endpoint to prevent Render free tier cold starts."""
    return "pong", 200


@app.route("/api/ready")
def api_ready():
    """Check if the dashboard is ready (used by loading page JS)."""
    ready = (Path(OUTPUT_DIR) / "dashboard.html").exists()
    return jsonify({"ready": ready})


@app.route("/api/trends")
def api_trends():
    """Return weekly trend data as JSON."""
    trends = _weekly_trends()
    return jsonify({"success": True, "trends": trends})


# ─────────────────────────────────────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("☁️  Cloud IQ starting on http://0.0.0.0:%d", PORT)
    app.run(host="0.0.0.0", port=PORT, debug=False)
