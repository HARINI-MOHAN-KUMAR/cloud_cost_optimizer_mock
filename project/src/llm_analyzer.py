from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

from project.config import OLLAMA_MODEL, OLLAMA_URL

PROMPT_TEMPLATE = """
You are a cloud cost optimization expert working for a DevOps team. Analyze this cloud resource and provide a cost-saving recommendation.

Resource Details:
- ID: {resource_id}
- Type: {type}
- Region: {region}
- CPU Usage: {cpu_avg}%
- Memory Usage: {memory_avg}%
- Monthly Cost: ${cost_monthly}
- Days Since Last Active: {last_active_days}

Your job:
1. Determine if this resource is idle or oversized
2. Explain WHY in 1-2 sentences
3. Give ONE specific recommended action
4. Estimate monthly savings
5. Rate severity: P0 (critical), P1 (warning), P2 (low)

Respond ONLY in this exact JSON format, nothing else:
{{
  "severity": "P0",
  "reason": "explanation here",
  "recommendation": "specific action here",
  "estimated_saving": "$XXX/month",
  "confidence": "high"
}}
"""


class LLMAnalyzer:
    """Analyzes flagged resources using Ollama or a rule-based fallback."""

    def __init__(self) -> None:
        self.url = OLLAMA_URL
        self.model = OLLAMA_MODEL

    def analyze_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        prompt = PROMPT_TEMPLATE.format(
            resource_id=resource["resource_id"],
            type=resource["type"],
            region=resource["region"],
            cpu_avg=int(resource["cpu_avg_percent"]),
            memory_avg=int(resource["memory_avg_percent"]),
            cost_monthly=f"{resource['cost_monthly_usd']:.2f}",
            last_active_days=resource["last_active_days"],
        )

        for attempt in range(1, 4):
            try:
                response = requests.post(
                    self.url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "max_output_tokens": 300,
                        "temperature": 0.2,
                    },
                    timeout=15,
                )
                response.raise_for_status()

                if isinstance(response.json(), dict):
                    analysis = response.json()
                else:
                    analysis = self._parse_text_response(response.text)

                analysis["estimated_saving_value"] = self._parse_saving(analysis.get("estimated_saving", ""))
                return analysis
            except (requests.RequestException, json.JSONDecodeError, KeyError, ValueError):
                if attempt == 3:
                    return self._fallback(resource)
                time.sleep(1)

        return self._fallback(resource)

    def batch_analyze(self, flagged_resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for entry in flagged_resources:
            resource = entry["resource"]
            try:
                analysis = self.analyze_resource(resource)
            except Exception:
                analysis = self._fallback(resource)
            analysis["estimated_saving_value"] = self._parse_saving(analysis.get("estimated_saving", ""))
            entry["analysis"] = analysis
            results.append(entry)
        return results

    def answer_question(self, question: str) -> str:
        prompt = (
            "You are a cloud cost optimization expert. Answer the following question directly and briefly. "
            "Do not include extra commentary."
            f"\n\nQuestion: {question}\n\nAnswer:"
        )

        for attempt in range(1, 4):
            try:
                response = requests.post(
                    self.url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "max_output_tokens": 180,
                        "temperature": 0.2,
                    },
                    timeout=15,
                )
                response.raise_for_status()
                return self._extract_answer(response)
            except (requests.RequestException, json.JSONDecodeError, KeyError, ValueError):
                if attempt == 3:
                    return "Sorry, I couldn't answer that question right now."
                time.sleep(1)

        return "Sorry, I couldn't answer that question right now."

    def _extract_answer(self, response: requests.Response) -> str:
        try:
            data = response.json()
        except json.JSONDecodeError:
            return response.text.strip()

        if isinstance(data, dict):
            if "output" in data and isinstance(data["output"], str):
                return data["output"].strip()
            if "text" in data and isinstance(data["text"], str):
                return data["text"].strip()
            if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                first_choice = data["choices"][0]
                if isinstance(first_choice, dict):
                    for key in ("text", "content", "message", "output"):
                        if key in first_choice and isinstance(first_choice[key], str):
                            return first_choice[key].strip()
                elif isinstance(first_choice, str):
                    return first_choice.strip()

        return response.text.strip()

    def _parse_text_response(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        sanitized = text
        if "```json" in text:
            sanitized = text.split("```json", 1)[1].rsplit("```", 1)[0]
        return json.loads(sanitized)

    def _fallback(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        cpu = resource["cpu_avg_percent"]
        cost = resource["cost_monthly_usd"]
        saving_value = round(min(cost, max(50.0, cost * 0.5)), 2)
        severity = "P0" if cpu < 3 or saving_value > 200 else "P1" if cpu < 7 or saving_value > 100 else "P2"
        return {
            "severity": severity,
            "reason": (
                "The resource has very low utilization and a high monthly cost, indicating it is idle or oversized."
                if cpu < 20
                else "This resource is currently underutilized relative to its cost."
            ),
            "recommendation": (
                "Decommission the resource or right-size it to a smaller instance class."
                if cpu < 10
                else "Review the instance type and adjust compute sizing to reduce waste."
            ),
            "estimated_saving": f"${saving_value:.2f}/month",
            "confidence": "medium",
            "estimated_saving_value": saving_value,
        }

    def generate_training_dataset(self, findings: List[Dict[str, Any]]) -> str:
        training_path = Path("output") / "ai_training_dataset.jsonl"
        training_path.parent.mkdir(parents=True, exist_ok=True)

        lines: List[str] = []
        for index, entry in enumerate(findings, start=1):
            resource = entry["resource"]
            analysis = entry.get("analysis") or self._fallback(resource)
            prompt_text = PROMPT_TEMPLATE.format(
                resource_id=resource["resource_id"],
                type=resource["type"],
                region=resource["region"],
                cpu_avg=int(resource["cpu_avg_percent"]),
                memory_avg=int(resource["memory_avg_percent"]),
                cost_monthly=f"{resource['cost_monthly_usd']:.2f}",
                last_active_days=resource["last_active_days"],
            ).strip()
            completion = json.dumps(
                {
                    "severity": analysis["severity"],
                    "reason": analysis["reason"],
                    "recommendation": analysis["recommendation"],
                    "estimated_saving": analysis["estimated_saving"],
                    "confidence": analysis.get("confidence", "medium"),
                },
                ensure_ascii=False,
            )
            lines.append(json.dumps({"prompt": prompt_text, "completion": completion}, ensure_ascii=False))

        training_path.write_text("\n".join(lines), encoding="utf-8")
        return str(training_path)

    def _parse_saving(self, saving_text: Any) -> float:
        if not isinstance(saving_text, str):
            return 0.0
        cleaned = saving_text.replace("$", "").replace("/month", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
