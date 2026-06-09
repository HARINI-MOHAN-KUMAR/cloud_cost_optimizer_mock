"""Cloud Cost Optimizer configuration placeholders."""

from dotenv import load_dotenv
import os

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "HARINI-MOHAN-KUMAR/cloud_cost_optimizer")  # Example: "my-org/cloud-cost-optimizer"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

# Feature flags: set default to enabled so the project can run with integrations
ENABLE_AI_AGENT = os.getenv("ENABLE_AI_AGENT", "true").lower() in ("1", "true", "yes")
ENABLE_GITHUB_ISSUES = os.getenv("ENABLE_GITHUB_ISSUES", "true").lower() in ("1", "true", "yes")
ENABLE_DISCORD_ALERTS = os.getenv("ENABLE_DISCORD_ALERTS", "true").lower() in ("1", "true", "yes")
ENABLE_EMAIL_REPORT = os.getenv("ENABLE_EMAIL_REPORT", "true").lower() in ("1", "true", "yes")

CPU_THRESHOLD = 10
MEMORY_THRESHOLD = 20
STALE_DAYS_THRESHOLD = 30
COST_THRESHOLD = 50
DATA_DIR = "data"
OUTPUT_DIR = "output"
CURRENT_WEEK_CSV = "cloud_billing_week4.csv"
ALL_WEEKS_CSV = [
    "cloud_billing_week1.csv",
    "cloud_billing_week2.csv",
    "cloud_billing_week3.csv",
    "cloud_billing_week4.csv",
]
