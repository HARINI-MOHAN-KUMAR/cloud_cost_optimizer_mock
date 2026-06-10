"""Cloud Cost Optimizer — configuration (all paths absolute, Render-safe)."""
from __future__ import annotations
from pathlib import Path
from dotenv import load_dotenv
import os

# ── Resolved project root ────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent  # Cloud_IQ/project/

# Load environment variables from either the project folder or root folder
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")
load_dotenv(dotenv_path=_PROJECT_ROOT.parent / ".env")

# ── External API credentials ─────────────────────────────────────────────────
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY", "")
GITHUB_TOKEN        = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO         = os.getenv("GITHUB_REPO", "HARINI-MOHAN-KUMAR/cloud_cost_optimizer_mock")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ── Email (Gmail SMTP) ───────────────────────────────────────────────────────
EMAIL_SENDER    = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD", "")     # Gmail App Password
EMAIL_RECEIVER  = os.getenv("EMAIL_RECEIVER", "")
SMTP_SERVER     = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587") or "587")

# ── Budget alert threshold ────────────────────────────────────────────────────
BUDGET_THRESHOLD = float(os.getenv("BUDGET_THRESHOLD", "1500"))

# ── Feature flags ─────────────────────────────────────────────────────────────
ENABLE_AI_AGENT       = os.getenv("ENABLE_AI_AGENT",       "true").lower() in ("1", "true", "yes")
ENABLE_GITHUB_ISSUES  = os.getenv("ENABLE_GITHUB_ISSUES",  "false").lower() in ("1", "true", "yes")
ENABLE_DISCORD_ALERTS = os.getenv("ENABLE_DISCORD_ALERTS", "true").lower()  in ("1", "true", "yes")
ENABLE_EMAIL_REPORT   = os.getenv("ENABLE_EMAIL_REPORT",   "true").lower()  in ("1", "true", "yes")

# ── Detection thresholds ──────────────────────────────────────────────────────
CPU_THRESHOLD         = int(os.getenv("CPU_THRESHOLD",          "10"))
MEMORY_THRESHOLD      = int(os.getenv("MEMORY_THRESHOLD",       "20"))
STALE_DAYS_THRESHOLD  = int(os.getenv("STALE_DAYS_THRESHOLD",   "30"))
COST_THRESHOLD        = int(os.getenv("COST_THRESHOLD",         "50"))

# ── Absolute data/output paths (works on Render AND locally) ─────────────────
DATA_DIR    = str(_PROJECT_ROOT / "data")
OUTPUT_DIR  = str(_PROJECT_ROOT / "output")

CURRENT_WEEK_CSV = os.getenv("CURRENT_WEEK_CSV", "cloud_billing_week4.csv")
ALL_WEEKS_CSV = [
    "cloud_billing_week1.csv",
    "cloud_billing_week2.csv",
    "cloud_billing_week3.csv",
    "cloud_billing_week4.csv",
]

# ── Server ────────────────────────────────────────────────────────────────────
PORT = int(os.getenv("PORT", "5000"))
