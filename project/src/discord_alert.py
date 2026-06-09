from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List

import requests

from project.config import DISCORD_WEBHOOK_URL

COLOR_MAP = {
    "P0": 15158332,
    "P1": 16776960,
    "P2": 3066993,
}


class DiscordAlerter:
    """Sends alerts to Discord using a webhook embed format."""

    def __init__(self, webhook_url: str = DISCORD_WEBHOOK_URL) -> None:
        self.webhook_url = webhook_url

    def send_critical_alert(self, resource: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
        severity = analysis.get("severity", "P2")
        color = COLOR_MAP.get(severity, COLOR_MAP["P2"])
        payload = {
            "embeds": [
                {
                    "title": f"Cloud Cost Alert — {resource['resource_id']}",
                    "description": analysis.get("reason", "Resource requires review."),
                    "color": color,
                    "fields": [
                        {"name": "Resource ID", "value": resource["resource_id"], "inline": True},
                        {"name": "Type", "value": resource["type"], "inline": True},
                        {"name": "CPU %", "value": f"{resource['cpu_avg_percent']}%", "inline": True},
                        {"name": "Cost", "value": f"${resource['cost_monthly_usd']:.2f}", "inline": True},
                        {"name": "Estimated Saving", "value": analysis.get("estimated_saving", "$0/month"), "inline": True},
                        {"name": "Action", "value": analysis.get("recommendation", "Review and right-size."), "inline": False},
                    ],
                    "footer": {"text": f"Cloud Cost Optimizer Agent • {datetime.utcnow().isoformat()}Z"},
                }
            ]
        }
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=15)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def send_summary(self, all_findings: List[Dict[str, Any]], total_saving: float) -> bool:
        count = len(all_findings)
        severity_breakdown = {"P0": 0, "P1": 0, "P2": 0}
        for entry in all_findings:
            severity = entry.get("severity") or entry.get("analysis", {}).get("severity", "P2")
            severity_breakdown[severity] += 1

        payload = {
            "embeds": [
                {
                    "title": "Cloud Cost Optimizer Scan Summary",
                    "description": f"Found {count} issues with ${total_saving:.2f} in monthly savings identified.",
                    "color": 3447003,
                    "fields": [
                        {"name": "P0 Critical", "value": str(severity_breakdown["P0"]), "inline": True},
                        {"name": "P1 Warning", "value": str(severity_breakdown["P1"]), "inline": True},
                        {"name": "P2 Low", "value": str(severity_breakdown["P2"]), "inline": True},
                        {"name": "Total Savings", "value": f"${total_saving:.2f}/month", "inline": False},
                    ],
                    "footer": {"text": f"Cloud Cost Optimizer Agent • {datetime.utcnow().isoformat()}Z"},
                }
            ]
        }
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=15)
            response.raise_for_status()
            return True
        except Exception:
            return False
