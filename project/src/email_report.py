from __future__ import annotations
import logging
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List

from project.config import (
    BUDGET_THRESHOLD,
    EMAIL_PASSWORD,
    EMAIL_RECEIVER,
    EMAIL_SENDER,
    SMTP_PORT,
    SMTP_SERVER,
)

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


class EmailReporter:
    """Production-grade email reporter with retry, budget alerts, and beautiful templates."""

    def __init__(self) -> None:
        self.sender           = EMAIL_SENDER
        self.password         = EMAIL_PASSWORD
        self.receiver         = EMAIL_RECEIVER
        self.smtp_server      = SMTP_SERVER
        self.smtp_port        = SMTP_PORT
        self.budget_threshold = BUDGET_THRESHOLD

    # ── Public API ─────────────────────────────────────────────────────────────

    def send_report(
        self,
        findings: List[Dict[str, Any]],
        total_saving: float,
        github_urls: List[str],
    ) -> bool:
        """Send full scan report email."""
        if not self._is_enabled():
            logger.warning("Email skipped — SMTP not configured.")
            return False

        total_cost = sum(e["resource"].get("cost_monthly_usd", 0.0) for e in findings)
        subject = (
            f"🚨 Cloud IQ Report — {len(findings)} Issues Found | "
            f"${total_saving:,.2f} Savings Available"
        )
        html = self._render(findings, total_saving, total_cost, github_urls, "scan_report")
        return self._send(subject, html)

    def send_budget_alert(
        self,
        total_cost: float,
        total_saving: float,
        findings: List[Dict[str, Any]],
    ) -> bool:
        """Send dedicated budget over-threshold alert."""
        if not self._is_enabled():
            logger.warning("Budget alert email skipped — SMTP not configured.")
            return False

        subject = (
            f"⚠️ BUDGET ALERT — Cloud spend ${total_cost:,.2f} exceeds "
            f"limit ${self.budget_threshold:,.2f}"
        )
        html = self._render(findings, total_saving, total_cost, [], "budget_alert")
        return self._send(subject, html)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _is_enabled(self) -> bool:
        return bool(self.sender and self.password and self.receiver and self.smtp_server)

    def _send(self, subject: str, html: str) -> bool:
        msg = MIMEMultipart("alternative")
        msg["From"]    = self.sender
        msg["To"]      = self.receiver
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html"))

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as srv:
                    srv.ehlo()
                    srv.starttls()
                    srv.ehlo()
                    srv.login(self.sender, self.password)
                    srv.sendmail(self.sender, self.receiver, msg.as_string())
                logger.info("Email sent to %s (attempt %d)", self.receiver, attempt)
                return True
            except smtplib.SMTPAuthenticationError as e:
                logger.error("SMTP auth failed — check Gmail App Password: %s", e)
                return False
            except Exception as e:
                wait = 2 ** (attempt - 1)
                logger.warning("Email attempt %d/%d failed: %s — retry in %ds", attempt, _MAX_RETRIES, e, wait)
                if attempt < _MAX_RETRIES:
                    time.sleep(wait)

        logger.error("Email failed after %d attempts.", _MAX_RETRIES)
        return False

    def _render(
        self,
        findings: List[Dict[str, Any]],
        total_saving: float,
        total_cost: float,
        github_urls: List[str],
        email_type: str,
    ) -> str:
        """Try Jinja2 template; fall back to inline HTML."""
        try:
            from jinja2 import Environment, FileSystemLoader
            env  = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)
            tmpl = env.get_template("email_report.html")
            p0   = sum(1 for e in findings if e.get("analysis", {}).get("severity") == "P0")
            p1   = sum(1 for e in findings if e.get("analysis", {}).get("severity") == "P1")
            return tmpl.render(
                scan_time        = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                findings         = findings,
                total_saving     = total_saving,
                total_cost       = total_cost,
                github_urls      = github_urls,
                p0_count         = p0,
                p1_count         = p1,
                budget_threshold = self.budget_threshold,
                over_budget      = total_cost > self.budget_threshold,
                email_type       = email_type,
            )
        except Exception as e:
            logger.warning("Jinja2 template failed (%s) — using fallback HTML.", e)
            return self._fallback_html(findings, total_saving, total_cost)

    def _fallback_html(
        self,
        findings: List[Dict[str, Any]],
        total_saving: float,
        total_cost: float,
    ) -> str:
        rows = ""
        for entry in findings:
            res      = entry.get("resource", {})
            analysis = entry.get("analysis", {})
            sev      = analysis.get("severity", "P2")
            color    = "#e74c3c" if sev == "P0" else "#f39c12" if sev == "P1" else "#2ecc71"
            rows += (
                f"<tr>"
                f"<td style='padding:10px;border-bottom:1px solid #2d3748;font-weight:600'>{res.get('resource_id','')}</td>"
                f"<td style='padding:10px;border-bottom:1px solid #2d3748'>{res.get('type','')}</td>"
                f"<td style='padding:10px;border-bottom:1px solid #2d3748'>"
                f"<span style='color:{color};font-weight:700'>{sev}</span></td>"
                f"<td style='padding:10px;border-bottom:1px solid #2d3748;color:#2ecc71;font-weight:700'>"
                f"${analysis.get('estimated_saving_value',0):.2f}</td>"
                f"<td style='padding:10px;border-bottom:1px solid #2d3748;color:#94a3b8;font-size:13px'>"
                f"{analysis.get('recommendation','Review usage.')}</td>"
                f"</tr>"
            )
        scan_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:Inter,Arial,sans-serif;color:#e2e8f0">
<div style="max-width:700px;margin:0 auto;padding:32px 20px">
  <div style="background:linear-gradient(135deg,#1e3a5f,#0f2744);border-radius:20px;padding:32px;margin-bottom:24px">
    <h1 style="margin:0 0 8px;font-size:28px;color:#38bdf8">☁️ Cloud IQ Report</h1>
    <p style="margin:0;color:#94a3b8;font-size:14px">Scan completed at {scan_time}</p>
  </div>
  <div style="display:flex;gap:16px;margin-bottom:24px">
    <div style="flex:1;background:#1e293b;border-radius:16px;padding:20px;text-align:center">
      <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:1px">Issues Found</div>
      <div style="font-size:36px;font-weight:900;color:#fb7185">{len(findings)}</div>
    </div>
    <div style="flex:1;background:#1e293b;border-radius:16px;padding:20px;text-align:center">
      <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:1px">Monthly Savings</div>
      <div style="font-size:36px;font-weight:900;color:#34d399">${total_saving:,.0f}</div>
    </div>
    <div style="flex:1;background:#1e293b;border-radius:16px;padding:20px;text-align:center">
      <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:1px">Total Spend</div>
      <div style="font-size:36px;font-weight:900;color:#94a3b8">${total_cost:,.0f}</div>
    </div>
  </div>
  <div style="background:#1e293b;border-radius:16px;padding:24px;margin-bottom:24px">
    <h2 style="margin:0 0 16px;font-size:18px">Flagged Resources</h2>
    <table style="width:100%;border-collapse:collapse">
      <thead>
        <tr style="background:#0f172a">
          <th style="padding:10px;text-align:left;font-size:12px;color:#64748b;text-transform:uppercase">Resource</th>
          <th style="padding:10px;text-align:left;font-size:12px;color:#64748b;text-transform:uppercase">Type</th>
          <th style="padding:10px;text-align:left;font-size:12px;color:#64748b;text-transform:uppercase">Severity</th>
          <th style="padding:10px;text-align:left;font-size:12px;color:#64748b;text-transform:uppercase">Saving</th>
          <th style="padding:10px;text-align:left;font-size:12px;color:#64748b;text-transform:uppercase">Action</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <p style="text-align:center;color:#475569;font-size:13px">Generated by Cloud IQ — Autonomous Cloud Cost Optimizer</p>
</div>
</body></html>"""
