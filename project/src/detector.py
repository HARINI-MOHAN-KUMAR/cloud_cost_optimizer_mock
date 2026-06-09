from __future__ import annotations
from typing import Any, Dict, List

from project.config import CPU_THRESHOLD, COST_THRESHOLD, MEMORY_THRESHOLD, STALE_DAYS_THRESHOLD


class ResourceDetector:
    """Detects idle and oversized cloud resources using configurable heuristics."""

    def detect_idle(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            resource
            for resource in resources
            if (
                resource["cpu_avg_percent"] < CPU_THRESHOLD
                or resource["memory_avg_percent"] < MEMORY_THRESHOLD
                or resource["last_active_days"] > STALE_DAYS_THRESHOLD
            )
            and resource["cost_monthly_usd"] > COST_THRESHOLD
        ]

    def detect_oversized(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            resource
            for resource in resources
            if (
                0 <= resource["cpu_avg_percent"] < 25
                or resource["memory_avg_percent"] < MEMORY_THRESHOLD
            )
            and resource["cost_monthly_usd"] > 150
        ]

    def calculate_potential_saving(self, resource: Dict[str, Any]) -> float:
        cost = resource["cost_monthly_usd"]
        cpu = resource["cpu_avg_percent"]
        memory = resource["memory_avg_percent"]
        age = resource["last_active_days"]

        if age > STALE_DAYS_THRESHOLD:
            saving = cost * 0.9
        elif cpu < CPU_THRESHOLD or memory < MEMORY_THRESHOLD:
            saving = cost * 0.75
        elif cpu < 15 and cost > 150:
            saving = cost * 0.55
        else:
            saving = cost * 0.35

        return round(max(25.0, min(saving, cost)), 2)

    def assign_severity(self, resource: Dict[str, Any], saving: float) -> str:
        cpu = resource["cpu_avg_percent"]
        age = resource["last_active_days"]

        if saving > 250 or cpu < 3 or age > STALE_DAYS_THRESHOLD:
            return "P0"
        if saving >= 120 or cpu < 7:
            return "P1"
        return "P2"

    def generate_report_data(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        for resource in resources:
            idle = resource["cpu_avg_percent"] < CPU_THRESHOLD and resource["cost_monthly_usd"] > COST_THRESHOLD
            oversized = 0 <= resource["cpu_avg_percent"] < 20 and resource["cost_monthly_usd"] > 150
            if not (idle or oversized):
                continue

            saving = self.calculate_potential_saving(resource)
            severity = self.assign_severity(resource, saving)
            issue_type = "idle" if idle else "oversized"
            issue_summary = (
                "Resource is underutilized and can be rightsized or decommissioned"
                if idle
                else "Resource appears oversized for low sustained utilization"
            )

            findings.append(
                {
                    "resource": resource,
                    "issue_type": issue_type,
                    "potential_saving": saving,
                    "severity": severity,
                    "issue_summary": issue_summary,
                    "analysis": {},
                }
            )

        return findings
