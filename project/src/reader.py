# REAL-WORLD EXTENSION:
# Replace load_resources() with boto3 calls to AWS Cost Explorer
# and return the same resource dict shape. Everything else stays identical.

from __future__ import annotations
import csv
from pathlib import Path
from typing import Any, Dict, List, Union

from project.config import DATA_DIR

REQUIRED_COLUMNS = {
    "resource_id", "type", "region",
    "cpu_avg_percent", "memory_avg_percent",
    "cost_monthly_usd", "last_active_days",
}


class CSVReader:
    """Reads and validates billing CSV resources for Cloud IQ."""

    def load_resources(self, filepath: Union[str, Path]) -> List[Dict[str, Any]]:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Billing CSV not found: {path}")
        if not self.validate_csv(path):
            raise ValueError(f"CSV validation failed: {path}")

        resources: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                norm = self._normalize_row(row)
                norm["waste_score"] = self._compute_waste_score(norm)
                resources.append(norm)
        return resources

    def load_all_weeks(self, filepaths: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        all_weeks: Dict[str, List[Dict[str, Any]]] = {}
        for filepath in filepaths:
            week_key = Path(filepath).stem
            try:
                all_weeks[week_key] = self.load_resources(Path(DATA_DIR) / filepath)
            except Exception:
                all_weeks[week_key] = []
        return all_weeks

    def validate_csv(self, filepath: Union[str, Path]) -> bool:
        path = Path(filepath)
        if not path.exists():
            return False
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            if not header:
                return False
            cols = {c.strip() for c in header}
            return REQUIRED_COLUMNS.issubset(cols)

    def print_summary(self, resources: List[Dict[str, Any]]) -> None:
        count = len(resources)
        total = sum(r.get("cost_monthly_usd", 0.0) for r in resources)
        avg = total / count if count else 0.0
        print(f"  • Resources loaded: {count}")
        print(f"  • Total monthly cost: ${total:,.2f}")
        print(f"  • Average cost per resource: ${avg:,.2f}")

    def _normalize_row(self, row: Dict[str, str]) -> Dict[str, Any]:
        return {
            "resource_id":        row.get("resource_id", "").strip(),
            "type":               row.get("type", "unknown").strip(),
            "region":             row.get("region", "unknown").strip(),
            "cpu_avg_percent":    float(row.get("cpu_avg_percent", "0") or 0),
            "memory_avg_percent": float(row.get("memory_avg_percent", "0") or 0),
            "cost_monthly_usd":   float(row.get("cost_monthly_usd", "0") or 0),
            "last_active_days":   int(float(row.get("last_active_days", "0") or 0)),
        }

    def _compute_waste_score(self, r: Dict[str, Any]) -> int:
        cpu  = r["cpu_avg_percent"]
        cost = r["cost_monthly_usd"]
        score = int(min(100, max(0, (100 - cpu) * (cost / 5))))
        return max(0, min(100, score))
