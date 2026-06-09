from __future__ import annotations
from typing import Any, Dict, List, Optional

import requests

from project.config import GITHUB_REPO, GITHUB_TOKEN

LABELS = {
    "P0": {"name": "P0-critical", "color": "d73a4a"},
    "P1": {"name": "P1-warning", "color": "e4e669"},
    "P2": {"name": "P2-low", "color": "0075ca"},
}


class GitHubIssueManager:
    """Files prioritized GitHub issues for flagged cloud cost findings."""

    def __init__(self, token: str = GITHUB_TOKEN, repo: str = GITHUB_REPO) -> None:
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
        )

    def _is_enabled(self) -> bool:
        return bool(self.repo and self.session.headers.get("Authorization"))

    def create_labels_if_missing(self) -> None:
        if not self._is_enabled():
            return

        endpoint = f"https://api.github.com/repos/{self.repo}/labels"
        response = self.session.get(endpoint, timeout=15)
        response.raise_for_status()
        existing = {label["name"] for label in response.json()}
        for entry in LABELS.values():
            if entry["name"] not in existing:
                self.session.post(
                    endpoint,
                    json={"name": entry["name"], "color": entry["color"], "description": "Cloud cost optimization severity label."},
                    timeout=15,
                )

    def check_duplicate(self, resource_id: str) -> Optional[str]:
        if not self._is_enabled():
            return None

        endpoint = f"https://api.github.com/repos/{self.repo}/issues"
        params = {"state": "open", "labels": "cost-optimization", "per_page": 100}
        response = self.session.get(endpoint, params=params, timeout=15)
        response.raise_for_status()
        for issue in response.json():
            if resource_id in issue.get("title", ""):
                return issue.get("html_url")
        return None

    def create_issue(self, resource: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[str]:
        if not self._is_enabled():
            return None

        try:
            existing = self.check_duplicate(resource["resource_id"])
            if existing:
                return existing

            label = LABELS.get(analysis.get("severity", "P2"), LABELS["P2"])["name"]
            title = f"[{analysis.get('severity', 'P2')}] {resource['resource_id']} is underutilized — save {analysis.get('estimated_saving', '$0/month')}"
            body = self._build_issue_body(resource, analysis)
            endpoint = f"https://api.github.com/repos/{self.repo}/issues"
            response = self.session.post(
                endpoint,
                json={
                    "title": title,
                    "body": body,
                    "labels": ["cost-optimization", label],
                },
                timeout=15,
            )
            response.raise_for_status()
            return response.json().get("html_url")
        except requests.HTTPError as error:
            print(f"⚠️  GitHub issue creation failed: {error}")
            return None
        except Exception as error:
            print(f"⚠️  GitHub issue error: {error}")
            return None

    def file_all_issues(self, findings: List[Dict[str, Any]]) -> List[str]:
        urls: List[str] = []
        if self._is_enabled():
            try:
                self.create_labels_if_missing()
            except Exception as error:
                print(f"⚠️  Warning: failed to ensure GitHub labels: {error}")

        for entry in findings:
            resource = entry["resource"]
            analysis = entry.get("analysis", {})
            url = self.create_issue(resource, analysis)
            if url:
                urls.append(url)
        return urls

    def _build_issue_body(self, resource: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        return (
            f"## ☁️ Cloud Cost Optimization Finding\n\n"
            f"### Resource: `{resource['resource_id']}`\n\n"
            f"**Type:** {resource['type']}  \n"
            f"**Region:** {resource['region']}  \n"
            f"**CPU Avg:** {resource['cpu_avg_percent']}%  \n"
            f"**Memory Avg:** {resource['memory_avg_percent']}%  \n"
            f"**Monthly Cost:** ${resource['cost_monthly_usd']:.2f}  \n"
            f"**Last Active:** {resource['last_active_days']} days ago  \n"
            f"**Estimated Savings:** {analysis.get('estimated_saving', '$0/month')}  \n"
            f"**Severity:** {analysis.get('severity', 'P2')}  \n\n"
            f"### AI Analysis\n"
            f"{analysis.get('reason', 'No analysis available.')}\n\n"
            f"### Recommended Action\n"
            f"{analysis.get('recommendation', 'Review the resource and take corrective action.')}\n\n"
            f"---\n"
            f"*Filed automatically by Cloud Cost Optimizer AI Agent*"
        )
