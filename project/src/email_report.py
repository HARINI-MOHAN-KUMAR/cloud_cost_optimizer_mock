from __future__ import annotations
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, List
import smtplib

from project.config import EMAIL_RECEIVER, EMAIL_PASSWORD, EMAIL_SENDER, SMTP_PORT, SMTP_SERVER


class EmailReporter:
    """Sends a formatted HTML summary report via SMTP."""

    def _is_enabled(self) -> bool:
        return bool(EMAIL_SENDER and EMAIL_PASSWORD and EMAIL_RECEIVER and SMTP_SERVER)

    def send_report(self, findings: List[Any], total_saving: float, github_urls: List[str]) -> bool:
        if not self._is_enabled():
            print("⚠️  Email report skipped because SMTP configuration is missing.")
            return False

        message = MIMEMultipart("alternative")
        message["From"] = EMAIL_SENDER
        message["To"] = EMAIL_RECEIVER
        message["Subject"] = f"🚨 Cloud Cost Report — {len(findings)} Issues Found | ${total_saving:.2f} Monthly Savings Identified"

        html = self._build_html(findings, total_saving, github_urls)
        message.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
                server.starttls()
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, message.as_string())
            return True
        except Exception as error:
            print(f"⚠️  Email send failed: {error}")
            return False

    def _build_html(self, findings: List[Any], total_saving: float, github_urls: List[str]) -> str:
        issue_rows = ""
        for entry in findings:
            resource = entry["resource"]
            analysis = entry.get("analysis", {})
            issue_rows += (
                f"<tr>"
                f"<td>{resource['resource_id']}</td>"
                f"<td>{resource['type']}</td>"
                f"<td>{analysis.get('severity', 'P2')}</td>"
                f"<td>${analysis.get('estimated_saving_value', 0.0):.2f}</td>"
                f"<td>{analysis.get('recommendation', 'Review usage and resize.')}</td>"
                f"</tr>"
            )

        issue_links = "".join(f"<li><a href=\"{url}\">{url}</a></li>" for url in github_urls)
        return f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
<title>Cloud Cost Optimizer Report</title>
<style>
body {{ margin: 0; font-family: Inter, Arial, sans-serif; background: #0f1117; color: #e6edf7; }}
.container {{ max-width: 900px; margin: 0 auto; padding: 24px; }}
.header {{ background: #111827; border-radius: 22px; padding: 24px; margin-bottom: 20px; }}
.card {{ background: #131926; border-radius: 20px; padding: 20px; margin-bottom: 18px; }}
h1 {{ margin: 0 0 8px; font-size: 2rem; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 14px; }}
th, td {{ padding: 12px 10px; text-align: left; border-bottom: 1px solid #192633; }}
a {{ color: #4dabf7; text-decoration: none; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Cloud Cost Optimizer Report</h1>
    <p>Scan completed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')}</p>
  </div>
  <div class="card">
    <h2>Summary</h2>
    <p><strong>Total Issues:</strong> {len(findings)}</p>
    <p><strong>Estimated Monthly Savings:</strong> ${total_saving:.2f}</p>
    <p><strong>GitHub Issues Filed:</strong> {len(github_urls)}</p>
  </div>
  <div class="card">
    <h2>Issue Details</h2>
    <table>
      <thead><tr><th>Resource</th><th>Type</th><th>Severity</th><th>Saving</th><th>Recommendation</th></tr></thead>
      <tbody>{issue_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>GitHub Actions</h2>
    <ul>{issue_links or '<li>No GitHub issues created.</li>'}</ul>
  </div>
  <div class="card">
    <p>This report was generated automatically by Cloud Cost Optimizer. The same architecture can be reused for real AWS Cost Explorer data by swapping the reader implementation.</p>
  </div>
</div>
</body>
</html>
"""
