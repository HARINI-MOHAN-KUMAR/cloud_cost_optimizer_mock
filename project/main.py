from __future__ import annotations
import argparse
import functools
import http.server
import json
import socketserver
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

from project.config import (
    ALL_WEEKS_CSV,
    CURRENT_WEEK_CSV,
    DATA_DIR,
    ENABLE_AI_AGENT,
    ENABLE_DISCORD_ALERTS,
    ENABLE_EMAIL_REPORT,
    ENABLE_GITHUB_ISSUES,
    OUTPUT_DIR,
)
from project.src.ai_agent import AIAnalyzerAgent
from project.src.detector import ResourceDetector
from project.src.discord_alert import DiscordAlerter
from project.src.email_report import EmailReporter
from project.src.github_issues import GitHubIssueManager
from project.src.html_report import HTMLReportGenerator
from project.src.llm_analyzer import LLMAnalyzer
from project.src.reader import CSVReader


class ChatHandler(http.server.SimpleHTTPRequestHandler):
    """Serves dashboard files and handles local chat POST requests."""

    def __init__(self, *args: Any, analyzer: LLMAnalyzer | None = None, directory: str | Path | None = None, **kwargs: Any) -> None:
        self.analyzer = analyzer
        super().__init__(*args, directory=str(directory) if directory else None, **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/chat":
            return super().do_POST()

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
            question = str(payload.get("question", "")).strip()
            answer = self.analyzer.answer_question(question) if (question and self.analyzer) else "Please ask a cloud cost question."
            response = {"question": question, "answer": answer}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        except Exception as error:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(error)}).encode("utf-8"))


def start_dashboard_server(directory: str, analyzer: LLMAnalyzer, port: int = 8000) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(ChatHandler, analyzer=analyzer, directory=directory)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def print_banner() -> None:
    print("╔═══════════════════════════════════════════╗")
    print("║     ☁️  CLOUD COST OPTIMIZER AGENT        ║")
    print("║     Powered by Ollama + GitHub API        ║")
    print("╚═══════════════════════════════════════════╝")


def summary_box(resources: int, issues: int, savings: float, issues_filed: int, elapsed: float) -> None:
    print("\n╔═══════════════════════════════════════════╗")
    print(f"║ Resources scanned: {resources:<26}║")
    print(f"║ Issues found:      {issues:<26}║")
    print(f"║ Total savings:     ${savings:<24.2f}║")
    print(f"║ GitHub issues:     {issues_filed:<26}║")
    print(f"║ Time taken:        {elapsed:.2f}s{'':<17}║")
    print("╚═══════════════════════════════════════════╝\n")


def safe_action(action_name: str, func, *args: Any, **kwargs: Any) -> Any:
    try:
        return func(*args, **kwargs)
    except Exception as error:
        print(f"⚠️  Warning: {action_name} failed with: {error}")
        return None


def compute_weekly_trends(reader: CSVReader, detector: ResourceDetector) -> List[Dict[str, Any]]:
    trends: List[Dict[str, Any]] = []
    for filepath in ALL_WEEKS_CSV:
        resources = safe_action(f"load {filepath}", reader.load_resources, Path(DATA_DIR) / filepath) or []
        findings = detector.generate_report_data(resources)
        trends.append({
            "week": Path(filepath).stem,
            "waste": sum(item["potential_saving"] for item in findings),
            "issues": len(findings),
        })
    return trends


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cloud Cost Optimizer")
    parser.add_argument("--ask", dest="ask", type=str, help="Ask a cloud cost question and get a direct answer.")
    parser.add_argument(
        "--watch",
        dest="watch",
        type=int,
        nargs="?",
        const=10,
        help="Watch the current CSV and regenerate the dashboard every N seconds (default 10).",
    )
    parser.add_argument(
        "--train",
        dest="train",
        action="store_true",
        help="Generate AI training data from the latest findings.",
    )
    parser.add_argument(
        "--github",
        dest="github",
        action="store_true",
        help="Enable filing GitHub issues for flagged findings.",
    )
    parser.add_argument(
        "--discord",
        dest="discord",
        action="store_true",
        help="Enable Discord alerts for critical findings.",
    )
    parser.add_argument(
        "--email",
        dest="email",
        action="store_true",
        help="Enable sending an email report after each scan.",
    )
    parser.add_argument(
        "--ai",
        dest="ai",
        action="store_true",
        help="Enable AI analysis for findings.",
    )
    parser.add_argument(
        "--serve",
        dest="serve",
        action="store_true",
        help="Serve the dashboard locally and enable the built-in chat interface.",
    )
    parser.add_argument(
        "--no-browser",
        dest="no_browser",
        action="store_true",
        help="Do not open the generated dashboard in the browser.",
    )
    return parser.parse_args()


def run_pipeline(
    reader: CSVReader,
    detector: ResourceDetector,
    issue_manager: GitHubIssueManager,
    alerter: DiscordAlerter,
    reporter: EmailReporter,
    html_generator: HTMLReportGenerator,
    analyzer: LLMAnalyzer,
    current_resources: List[Dict[str, Any]],
    open_browser: bool = True,
    enable_ai: bool = ENABLE_AI_AGENT,
    enable_github: bool = ENABLE_GITHUB_ISSUES,
    enable_discord: bool = ENABLE_DISCORD_ALERTS,
    enable_email: bool = ENABLE_EMAIL_REPORT,
) -> tuple[str, List[str]]:
    findings = detector.generate_report_data(current_resources)
    analyzed_findings = safe_action(
        "AI agent analysis",
        AIAnalyzerAgent(enable_ai, analyzer).analyze,
        findings,
    ) or []
    total_saving = sum(
        entry.get("analysis", {}).get("estimated_saving_value", entry.get("potential_saving", 0.0))
        for entry in analyzed_findings
    )

    github_urls: List[str] = []
    if enable_github:
        github_urls = safe_action("file GitHub issues", issue_manager.file_all_issues, analyzed_findings) or []

    if enable_discord:
        for entry in analyzed_findings:
            analysis = entry.get("analysis", {})
            if analysis.get("severity") == "P0":
                sent = safe_action("Discord alert", alerter.send_critical_alert, entry["resource"], analysis)
                print(f"    • Discord alert for {entry['resource']['resource_id']}: {'sent' if sent else 'skipped'}")
        safe_action("Discord summary", alerter.send_summary, analyzed_findings, total_saving)

    if enable_email:
        safe_action("email report", reporter.send_report, analyzed_findings, total_saving, github_urls)

    weekly_trends = safe_action("weekly trend analysis", compute_weekly_trends, reader, detector) or []
    dashboard_path = safe_action(
        "dashboard generation",
        html_generator.generate_dashboard,
        current_resources,
        analyzed_findings,
        total_saving,
        weekly_trends,
        github_urls,
        OUTPUT_DIR,
        open_browser,
    ) or ""
    return dashboard_path, github_urls


def main() -> None:
    args = parse_args()
    analyzer = LLMAnalyzer()

    if args.ask:
        answer = analyzer.answer_question(args.ask)
        print("🤖 Answer:")
        print(answer)
        return

    enable_ai = ENABLE_AI_AGENT or args.ai
    enable_github = ENABLE_GITHUB_ISSUES or args.github
    enable_discord = ENABLE_DISCORD_ALERTS or args.discord
    enable_email = ENABLE_EMAIL_REPORT or args.email
    open_browser = not args.no_browser
    server_port = 8000 if args.serve else None
    server_url = f"http://127.0.0.1:{server_port}/dashboard.html" if args.serve else None

    print(
        f"⚙️  AI={'on' if enable_ai else 'off'} | GitHub={'on' if enable_github else 'off'} | "
        f"Discord={'on' if enable_discord else 'off'} | Email={'on' if enable_email else 'off'}"
    )

    reader = CSVReader()
    detector = ResourceDetector()
    issue_manager = GitHubIssueManager()
    alerter = DiscordAlerter()
    reporter = EmailReporter()
    html_generator = HTMLReportGenerator()

    if args.train:
        current_resources = safe_action("read current week CSV", reader.load_resources, Path(DATA_DIR) / CURRENT_WEEK_CSV) or []
        if not current_resources:
            print("⚠️ No resources found for AI training. Ensure the billing CSV exists.")
            return

        findings = detector.generate_report_data(current_resources)
        if not findings:
            print("⚠️ No flagged findings available to generate training data.")
            return

        training_path = safe_action(
            "AI training generation",
            AIAnalyzerAgent(enable_ai, analyzer).train,
            findings,
        )
        if training_path:
            print(f"  • Training dataset written to: {training_path}")
        return

    start = time.perf_counter()
    print_banner()

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    csv_path = Path(DATA_DIR) / CURRENT_WEEK_CSV

    if args.watch:
        if args.serve:
            server = start_dashboard_server(OUTPUT_DIR, analyzer, port=server_port)
            print(f"🌐 Local dashboard server started at {server_url}")
        print(f"🔁 Watch mode enabled. Regenerating dashboard every {args.watch} seconds.")
        current_resources = safe_action("read current week CSV", reader.load_resources, csv_path) or []
        if current_resources:
            reader.print_summary(current_resources)
        dashboard_path, github_urls = run_pipeline(
            reader,
            detector,
            issue_manager,
            alerter,
            reporter,
            html_generator,
            analyzer,
            current_resources,
            open_browser=not args.serve and open_browser,
            enable_ai=enable_ai,
            enable_github=enable_github,
            enable_discord=enable_discord,
            enable_email=enable_email,
        )
        if args.serve and open_browser:
            html_generator._open_in_chrome(server_url, is_url=True)
        print(f"  • Dashboard generated at: {dashboard_path}")

        last_mtime = csv_path.stat().st_mtime if csv_path.exists() else None
        print("⏳ Watching for updates. Edit the CSV file to refresh the dashboard.")
        while True:
            time.sleep(args.watch)
            try:
                current_mtime = csv_path.stat().st_mtime
            except FileNotFoundError:
                continue
            if current_mtime != last_mtime:
                last_mtime = current_mtime
                print("🟢 Change detected in CSV. Regenerating dashboard...")
                current_resources = safe_action("read current week CSV", reader.load_resources, csv_path) or []
                if current_resources:
                    reader.print_summary(current_resources)
                dashboard_path, github_urls = run_pipeline(
                    reader,
                    detector,
                    issue_manager,
                    alerter,
                    reporter,
                    html_generator,
                    analyzer,
                    current_resources,
                    open_browser=False,
                    enable_ai=enable_ai,
                    enable_github=enable_github,
                    enable_discord=enable_discord,
                    enable_email=enable_email,
                )
                print(f"  • Dashboard regenerated at: {dashboard_path}")
        return

    print("📂 Step 1/7 - Loading billing CSV data")
    current_resources = safe_action("read current week CSV", reader.load_resources, csv_path) or []
    if current_resources:
        reader.print_summary(current_resources)
    else:
        print("  • No resources were loaded.")

    if args.serve:
        server = start_dashboard_server(OUTPUT_DIR, analyzer, port=server_port)
        print(f"🌐 Local dashboard server started at {server_url}")

    dashboard_path, github_urls = run_pipeline(
        reader,
        detector,
        issue_manager,
        alerter,
        reporter,
        html_generator,
        analyzer,
        current_resources,
        open_browser=not args.serve and open_browser,
        enable_ai=enable_ai,
        enable_github=enable_github,
        enable_discord=enable_discord,
        enable_email=enable_email,
    )
    if dashboard_path:
        print(f"  • Dashboard generated at: {dashboard_path}")
    if args.serve and open_browser:
        html_generator._open_in_chrome(server_url, is_url=True)

    elapsed = time.perf_counter() - start
    summary_box(
        len(current_resources),
        len(detector.generate_report_data(current_resources)),
        sum(entry.get("analysis", {}).get("estimated_saving_value", entry.get("potential_saving", 0.0)) for entry in detector.generate_report_data(current_resources)),
        len(github_urls),
        elapsed,
    )


if __name__ == "__main__":
    main()
