# REAL-WORLD EXTENSION
# This reader is intentionally decoupled from cloud provider APIs.
# To use this agent with real AWS billing data, replace the CSVReader implementation with
# boto3 calls to AWS Cost Explorer and return the same resource dictionaries.
# The rest of the agent pipeline stays identical.

from __future__ import annotations
import csv
from pathlib import Path
from typing import Any, Dict, List, Union

from project.config import DATA_DIR

REQUIRED_COLUMNS = {
    "resource_id",
    "type",
    "region",
    "cpu_avg_percent",
    "memory_avg_percent",
    "cost_monthly_usd",
    "last_active_days",
}


class CSVReader:
    """Reads and validates billing CSV resources for the Cloud Cost Optimizer."""

    def load_resources(self, filepath: Union[str, Path]) -> List[Dict[str, Any]]:
        """Load a single CSV file and return normalized resource dictionaries."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Billing CSV not found: {path}")

        if not self.validate_csv(path):
            raise ValueError(f"CSV validation failed for: {path}")

        resources: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                normalized = self._normalize_row(row)
                normalized["waste_score"] = self._compute_waste_score(normalized)
                resources.append(normalized)

        return resources

    def load_all_weeks(self, filepaths: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Load multiple weekly CSV snapshots into a dictionary keyed by week name."""
        all_weeks: Dict[str, List[Dict[str, Any]]] = {}
        for filepath in filepaths:
            week_key = Path(filepath).stem
            try:
                all_weeks[week_key] = self.load_resources(DATA_DIR / filepath)
            except Exception:
                all_weeks[week_key] = []
        return all_weeks

    def validate_csv(self, filepath: Union[str, Path]) -> bool:
        """Validate that the CSV contains the required billing columns."""
        path = Path(filepath)
        if not path.exists():
            return False

        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            if not header:
                return False
            columns = {column.strip() for column in header}
            return REQUIRED_COLUMNS.issubset(columns)

    def print_summary(self, resources: List[Dict[str, Any]]) -> None:
        """Print a short summary of loaded resources."""
        count = len(resources)
        total_cost = sum(resource.get("cost_monthly_usd", 0.0) for resource in resources)
        average_cost = total_cost / count if count else 0.0
        print(f"  • Resources loaded: {count}")
        print(f"  • Total monthly cost: ${total_cost:,.2f}")
        print(f"  • Average cost per resource: ${average_cost:,.2f}")

    def _normalize_row(self, row: Dict[str, str]) -> Dict[str, Any]:
        return {
            "resource_id": row.get("resource_id", "").strip(),
            "type": row.get("type", "unknown").strip(),
            "region": row.get("region", "unknown").strip(),
            "cpu_avg_percent": float(row.get("cpu_avg_percent", "0") or 0),
            "memory_avg_percent": float(row.get("memory_avg_percent", "0") or 0),
            "cost_monthly_usd": float(row.get("cost_monthly_usd", "0") or 0),
            "last_active_days": int(float(row.get("last_active_days", "0") or 0)),
        }

    def _compute_waste_score(self, resource: Dict[str, Any]) -> int:
        cpu = resource["cpu_avg_percent"]
        cost = resource["cost_monthly_usd"]
        score = int(min(100, max(0, (100 - cpu) * (cost / 5))))
        return max(0, min(100, score))
