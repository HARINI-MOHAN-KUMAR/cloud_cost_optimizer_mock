from __future__ import annotations
from typing import Any, Dict, List

from project.config import ENABLE_AI_AGENT
from project.src.llm_analyzer import LLMAnalyzer


class AIAnalyzerAgent:
    """Runs the LLM-based analyzer conditionally, with rule-based fallback when disabled."""

    def __init__(self, enabled: bool, analyzer: LLMAnalyzer) -> None:
        self.enabled = enabled
        self.analyzer = analyzer

    def analyze(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.enabled:
            print("ℹ️ AI agent is disabled; using fallback analysis for findings.")
            return self._apply_fallback(findings)

        print("ℹ️ AI agent is enabled; analyzing findings with the LLM.")
        return self.analyzer.batch_analyze(findings)

    def train(self, findings: List[Dict[str, Any]]) -> str:
        if not findings:
            raise ValueError("No findings available to generate AI training data.")

        dataset_path = self.analyzer.generate_training_dataset(findings)
        print(f"📚 AI training dataset generated: {dataset_path}")
        return dataset_path

    def _apply_fallback(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for entry in findings:
            analysis = self.analyzer._fallback(entry["resource"])
            analysis["estimated_saving_value"] = self.analyzer._parse_saving(
                analysis.get("estimated_saving", "")
            )
            entry["analysis"] = analysis
            results.append(entry)
        return results
