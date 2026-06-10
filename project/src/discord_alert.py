from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

from project.config import BUDGET_THRESHOLD, DISCORD_WEBHOOK_URL

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_DELAY = 1   # seconds, doubles each retry

# Discord embed colours (decimal)
_COLOR = {
    "P0":      0xE74C3C,  # red
    "P1":      0xF39C12,  # orange
    "P2":      0x2ECC71,  # green
    "budget":  0xFF6B35,  # bright orange-red
    "summary": 0x00D4AA,  # teal
    "weekly":  0x3498DB,  # blue
}

_SAMPLE_WEBHOOK = "https://discord.com/api/webhooks/SAMPLE_ID/SAMPLE_TOKEN"


class DiscordAlerter:
    """Production-grade Discord alerter — retry, rate-limit handling, rich embeds."""

    def __init__(
        self,
        webhook_url: str = DISCORD_WEBHOOK_URL,
        budget_threshold: float = BUDGET_THRESHOLD,
    ) -> None:
        self.webhook_url      = webhook_url or _SAMPLE_WEBHOOK
        self.budget_threshold = budget_threshold
        self._sample_mode     = (not webhook_url) or webhook_url == _SAMPLE_WEBHOOK

    # ── Public API ─────────────────────────────────────────────────────────────

    def send_critical_alert(self, resource: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
        """Send a P0/P1 critical resource finding embed."""
        sev  = analysis.get("severity", "P2")
        icon = {"P0": "🚨", "P1": "⚠️", "P2": "💡"}.get(sev, "💡")
        payload = {
            "username":   "Cloud IQ Bot",
            "embeds": [{
                "title":       f"{icon} {sev} Alert — {resource.get('resource_id', 'Unknown')}",
                "description": analysis.get("reason", "Resource requires review."),
                "color":       _COLOR.get(sev, _COLOR["P2"]),
                "timestamp":   self._ts(),
                "fields": [
                    {"name": "🖥️ Resource",       "value": f"`{resource.get('resource_id','N/A')}`", "inline": True},
                    {"name": "📦 Type",            "value": resource.get("type", "N/A"),              "inline": True},
                    {"name": "🌍 Region",          "value": resource.get("region", "N/A"),            "inline": True},
                    {"name": "📊 CPU Avg",         "value": f"{resource.get('cpu_avg_percent',0)}%",  "inline": True},
                    {"name": "💾 Memory Avg",      "value": f"{resource.get('memory_avg_percent',0)}%","inline": True},
                    {"name": "⏰ Last Active",     "value": f"{resource.get('last_active_days',0)} days ago","inline": True},
                    {"name": "💰 Monthly Cost",    "value": f"${resource.get('cost_monthly_usd',0):,.2f}", "inline": True},
                    {"name": "💚 Potential Saving","value": f"**{analysis.get('estimated_saving','$0/month')}**","inline": True},
                    {"name": "🎯 Severity",        "value": f"**{sev}**",                             "inline": True},
                    {"name": "✅ Action",           "value": analysis.get("recommendation","Review and right-size."), "inline": False},
                ],
                "footer": {"text": "Cloud IQ — Autonomous Cost Optimizer"},
            }],
        }
        return self._post(payload)

    def send_summary(self, findings: List[Dict[str, Any]], total_saving: float) -> bool:
        """Send a post-scan summary embed."""
        counts     = {"P0": 0, "P1": 0, "P2": 0}
        total_cost = 0.0
        for e in findings:
            sev = e.get("severity") or e.get("analysis", {}).get("severity", "P2")
            counts[sev] = counts.get(sev, 0) + 1
            total_cost += e.get("resource", {}).get("cost_monthly_usd", 0.0)

        over_budget  = total_cost > self.budget_threshold
        budget_note  = (
            f"\n\n💸 **Budget exceeded!** Spend **${total_cost:,.2f}** > limit **${self.budget_threshold:,.2f}**"
            if over_budget else ""
        )
        payload = {
            "username": "Cloud IQ Bot",
            "embeds": [{
                "title":       "📊 Cloud IQ — Scan Complete",
                "description": f"Scan found **{len(findings)} issues** in your cloud infrastructure.{budget_note}",
                "color":       _COLOR["budget"] if over_budget else _COLOR["summary"],
                "timestamp":   self._ts(),
                "fields": [
                    {"name": "🚨 P0 Critical",      "value": str(counts["P0"]),              "inline": True},
                    {"name": "⚠️ P1 Warning",       "value": str(counts["P1"]),              "inline": True},
                    {"name": "💡 P2 Low",            "value": str(counts["P2"]),              "inline": True},
                    {"name": "💸 Total Spend",       "value": f"${total_cost:,.2f}/month",    "inline": True},
                    {"name": "💚 Savings Found",     "value": f"**${total_saving:,.2f}/mo**", "inline": True},
                    {"name": "📅 Annual Savings",    "value": f"${total_saving*12:,.2f}/yr",  "inline": True},
                ],
                "footer": {"text": "Cloud IQ — Autonomous Cost Optimizer"},
            }],
        }
        return self._post(payload)

    def send_budget_alert(
        self,
        total_cost: float,
        budget_threshold: float,
        total_saving: float,
    ) -> bool:
        """Send a dedicated budget-exceeded alert with @here ping."""
        overage = total_cost - budget_threshold
        pct     = (total_cost / budget_threshold * 100) if budget_threshold > 0 else 0
        payload = {
            "username": "Cloud IQ Bot",
            "content":  "@here 🚨 **BUDGET ALERT** — Cloud spend has exceeded the configured threshold!",
            "embeds": [{
                "title":       "💸 Budget Threshold Exceeded",
                "description": "Your cloud spend has exceeded the configured budget limit. Immediate action recommended.",
                "color":       _COLOR["budget"],
                "timestamp":   self._ts(),
                "fields": [
                    {"name": "💰 Current Spend",      "value": f"**${total_cost:,.2f}/month**",    "inline": True},
                    {"name": "🎯 Budget Limit",        "value": f"${budget_threshold:,.2f}/month",  "inline": True},
                    {"name": "📈 Over Budget",         "value": f"**+${overage:,.2f} ({pct:.0f}%)**","inline": True},
                    {"name": "💚 Recoverable Savings", "value": f"${total_saving:,.2f}/month",      "inline": True},
                    {"name": "📅 Annual Savings",      "value": f"${total_saving*12:,.2f}/year",    "inline": True},
                    {"name": "⚡ Action Required",
                     "value": "Review the Cloud IQ dashboard and remediate P0 critical issues immediately.",
                     "inline": False},
                ],
                "footer": {"text": "Cloud IQ — Autonomous Cost Optimizer"},
            }],
        }
        return self._post(payload)

    def send_weekly_report(self, trends: List[Dict[str, Any]], total_saving: float) -> bool:
        """Send weekly 4-week trend report."""
        if not trends:
            return False
        lines = [
            f"`{t.get('week','?')}` — ${t.get('waste',0):,.2f} waste — {t.get('issues',0)} issues"
            for t in trends
        ]
        payload = {
            "username": "Cloud IQ Bot",
            "embeds": [{
                "title":       "📈 Weekly Cloud Cost Report",
                "description": "4-week cloud spend trend summary:",
                "color":       _COLOR["weekly"],
                "timestamp":   self._ts(),
                "fields": [
                    {"name": "📅 Weekly Trend",           "value": "\n".join(lines), "inline": False},
                    {"name": "💚 Current Savings",        "value": f"**${total_saving:,.2f}/month**","inline": True},
                    {"name": "📅 Annual Opportunity",     "value": f"${total_saving*12:,.2f}/year",  "inline": True},
                ],
                "footer": {"text": "Cloud IQ — Autonomous Cost Optimizer"},
            }],
        }
        return self._post(payload)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _post(self, payload: Dict[str, Any]) -> bool:
        """POST to Discord with retry and 429 rate-limit handling."""
        if self._sample_mode:
            logger.info("[SAMPLE MODE] Discord payload:\n%s", payload.get("embeds", [{}])[0].get("title", ""))
            return True   # Simulate success in sample mode

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    self.webhook_url,
                    json=payload,
                    timeout=15,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 429:
                    retry_after = float(resp.json().get("retry_after", 2))
                    logger.warning("Discord rate-limited — waiting %.1fs", retry_after)
                    time.sleep(retry_after + 0.5)
                    continue
                resp.raise_for_status()
                logger.info("Discord message sent (attempt %d/%d).", attempt, _MAX_RETRIES)
                return True
            except requests.RequestException as e:
                wait = _RETRY_DELAY * (2 ** (attempt - 1))
                logger.warning("Discord attempt %d/%d failed: %s — retry in %ds", attempt, _MAX_RETRIES, e, wait)
                if attempt < _MAX_RETRIES:
                    time.sleep(wait)

        logger.error("Discord notification failed after %d attempts.", _MAX_RETRIES)
        return False
