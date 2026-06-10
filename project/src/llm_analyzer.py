from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from project.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
You are a cloud cost optimization expert. Analyze this cloud resource and return cost-saving recommendations.

Resource Details:
- ID: {resource_id}
- Type: {type}
- Region: {region}
- CPU Usage: {cpu_avg}%
- Memory Usage: {memory_avg}%
- Monthly Cost: ${cost_monthly}
- Days Since Last Active: {last_active_days}

Tasks:
1. Determine if idle or oversized
2. Explain WHY in 1-2 sentences
3. Give ONE specific action
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


def _try_import_gemini():
    """Try to import Gemini SDK; return None if unavailable."""
    try:
        import google.generativeai as genai
        return genai
    except ImportError:
        logger.warning("google-generativeai not installed. Using fallback analysis.")
        return None


class LLMAnalyzer:
    """Analyzes flagged resources using Gemini API with rule-based fallback."""

    def __init__(self) -> None:
        self._genai = _try_import_gemini()
        self._model = None
        if self._genai and GEMINI_API_KEY:
            try:
                self._genai.configure(api_key=GEMINI_API_KEY)
                self._model = self._genai.GenerativeModel("gemini-2.0-flash")
                logger.info("Gemini 2.0 Flash initialized successfully.")
            except Exception as e:
                logger.warning("Gemini init failed: %s — using fallback.", e)
                self._model = None
        else:
            logger.info("No GEMINI_API_KEY set — using rule-based fallback.")

    def _is_gemini_available(self) -> bool:
        return self._model is not None

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

        if not self._is_gemini_available():
            return self._fallback(resource)

        for attempt in range(1, 4):
            try:
                response = self._model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.2,
                        "max_output_tokens": 300,
                    },
                )
                text = response.text.strip()
                # Strip markdown code fences if present
                if "```json" in text:
                    text = text.split("```json", 1)[1].rsplit("```", 1)[0].strip()
                elif "```" in text:
                    text = text.split("```", 1)[1].rsplit("```", 1)[0].strip()

                analysis = json.loads(text)
                analysis["estimated_saving_value"] = self._parse_saving(
                    analysis.get("estimated_saving", "")
                )
                return analysis
            except Exception as e:
                logger.warning("Gemini attempt %d/3 failed: %s", attempt, e)
                if attempt < 3:
                    time.sleep(1 * attempt)

        return self._fallback(resource)

    def batch_analyze(self, flagged: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for entry in flagged:
            resource = entry["resource"]
            try:
                analysis = self.analyze_resource(resource)
            except Exception:
                analysis = self._fallback(resource)
            analysis["estimated_saving_value"] = self._parse_saving(
                analysis.get("estimated_saving", "")
            )
            entry["analysis"] = analysis
            results.append(entry)
        return results

    def answer_question(self, question: str) -> str:
        prompt = (
            "You are a cloud cost optimization expert. Answer the following question "
            "clearly and concisely in 2-4 sentences.\n\n"
            f"Question: {question}\n\nAnswer:"
        )

        if not self._is_gemini_available():
            return (
                "AI assistant unavailable (no GEMINI_API_KEY configured). "
                "Please set your Gemini API key in the .env file."
            )

        for attempt in range(1, 4):
            try:
                response = self._model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.3, "max_output_tokens": 200},
                )
                return response.text.strip()
            except Exception as e:
                logger.warning("Gemini Q&A attempt %d/3 failed: %s", attempt, e)
                if attempt < 3:
                    time.sleep(1)

        return "Sorry, I couldn't answer that question right now."

    def _fallback(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        cpu  = resource["cpu_avg_percent"]
        cost = resource["cost_monthly_usd"]
        age  = resource["last_active_days"]
        saving_value = round(min(cost, max(50.0, cost * 0.5)), 2)
        severity = (
            "P0" if (cpu < 3 or age > 30 or saving_value > 200)
            else "P1" if (cpu < 7 or saving_value > 100)
            else "P2"
        )
        return {
            "severity": severity,
            "reason": (
                "Resource has very low utilization and high monthly cost — idle or oversized."
                if cpu < 20
                else "Resource is underutilized relative to its cost."
            ),
            "recommendation": (
                "Decommission or right-size to a smaller instance class."
                if cpu < 10
                else "Review instance type and reduce compute sizing."
            ),
            "estimated_saving": f"${saving_value:.2f}/month",
            "confidence": "medium",
            "estimated_saving_value": saving_value,
        }

    def generate_training_dataset(self, findings: List[Dict[str, Any]]) -> str:
        training_path = Path("output") / "ai_training_dataset.jsonl"
        training_path.parent.mkdir(parents=True, exist_ok=True)
        lines: List[str] = []
        for entry in findings:
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
            completion = json.dumps({
                "severity":          analysis["severity"],
                "reason":            analysis["reason"],
                "recommendation":    analysis["recommendation"],
                "estimated_saving":  analysis["estimated_saving"],
                "confidence":        analysis.get("confidence", "medium"),
            }, ensure_ascii=False)
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
