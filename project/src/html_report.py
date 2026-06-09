from __future__ import annotations
import json
import os
import shutil
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    from project.config import GITHUB_REPO
except Exception:
    GITHUB_REPO = ""

GITHUB_ISSUES_URL = (
    f"https://github.com/{GITHUB_REPO}/issues?q=is%3Aissue+state%3Aopen"
    if GITHUB_REPO else "#"
)


class HTMLReportGenerator:
    """Generates a feature-rich HTML dashboard with embedded AI chatbot."""

    def generate_dashboard(
        self,
        resources: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
        total_saving: float,
        weekly_trends: List[Dict[str, Any]],
        github_urls: List[str],
        output_dir: str,
        open_browser: bool = True,
        browser_target: str | None = None,
    ) -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        filepath = Path(output_dir) / "dashboard.html"
        html = self._render_html(resources, findings, total_saving, weekly_trends, github_urls, output_dir)
        filepath.write_text(html, encoding="utf-8")
        if open_browser:
            if browser_target:
                self._open_in_chrome(browser_target, is_url=True)
            else:
                self._open_in_chrome(str(filepath), is_url=False)
        return str(filepath)

    def _open_in_chrome(self, target: str, is_url: bool = False) -> None:
        absolute_target = target if is_url else str(Path(target).absolute())
        chrome_exe = shutil.which("chrome") or shutil.which("chrome.exe")
        if not chrome_exe and os.name == "nt":
            for candidate in [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]:
                if Path(candidate).exists():
                    chrome_exe = candidate
                    break
        if chrome_exe:
            try:
                subprocess.Popen([chrome_exe, absolute_target])
                return
            except Exception:
                pass
        try:
            if os.name == "nt":
                subprocess.Popen(f'start "" "{absolute_target}"', shell=True)
                return
        except Exception:
            pass
        if is_url:
            webbrowser.open(absolute_target)
        else:
            webbrowser.open(Path(absolute_target).as_uri())

    def _render_html(
        self,
        resources: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
        total_saving: float,
        weekly_trends: List[Dict[str, Any]],
        github_urls: List[str],
        output_dir: str,
    ) -> str:
        scan_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
        issues_found = len(findings)
        resources_scanned = len(resources)
        github_count = len(github_urls)
        total_cost = sum(r.get("cost_monthly_usd", 0.0) for r in resources)

        severity_totals = {"P0": 0.0, "P1": 0.0, "P2": 0.0}
        for entry in findings:
            sev = entry.get("severity") or entry.get("analysis", {}).get("severity", "P2")
            severity_totals[sev] += float(
                entry.get("potential_saving", entry.get("analysis", {}).get("estimated_saving_value", 0.0))
            )

        donut_segments = []
        donut_total = sum(severity_totals.values()) or 1
        seg_start = 0
        donut_colors = {"P0": "#ff6b6b", "P1": "#ffd43b", "P2": "#00d4aa"}
        for sev in ["P0", "P1", "P2"]:
            val = severity_totals[sev]
            pct = val / donut_total
            size = pct * 314
            donut_segments.append({
                "severity": sev, "value": val, "percent": int(pct * 100),
                "dasharray": f"{size:.1f} 314", "offset": f"{seg_start:.1f}",
                "color": donut_colors[sev],
            })
            seg_start += size

        weekly_rows = ""
        max_waste = max((e["waste"] for e in weekly_trends), default=1) or 1
        for entry in weekly_trends:
            width = int((entry["waste"] / max_waste) * 100)
            weekly_rows += f"""
<div class="weekly-item">
  <div class="weekly-meta">
    <span class="weekly-label">{entry['week']}</span>
    <a class="gh-week-link" href="{GITHUB_ISSUES_URL}" target="_blank" rel="noopener">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
      {entry['issues']} issue{"s" if entry['issues'] != 1 else ""} &rarr;
    </a>
  </div>
  <div class="weekly-bar-wrap">
    <div class="bar-bg"><div class="bar-fill" style="width:{width}%;"></div></div>
    <span class="weekly-waste">${entry['waste']:,.2f}</span>
  </div>
</div>"""

        flagged_cards = ""
        for entry in findings:
            res = entry["resource"]
            analysis = entry.get("analysis", {})
            sev = analysis.get("severity", entry.get("severity", "P2"))
            sev_color = {"P0": "#ff6b6b", "P1": "#ffd43b", "P2": "#00d4aa"}.get(sev, "#00d4aa")
            saving_text = analysis.get("estimated_saving", f"${entry.get('potential_saving', 0):.2f}/month")
            rec = analysis.get("recommendation", "Review and adjust sizing.")
            cpu = res["cpu_avg_percent"]
            mem = res.get("memory_avg_percent", 0)
            flagged_cards += (
                f'<div class="flag-card" data-severity="{sev}" data-type="{res["type"]}">'
                f'<div class="flag-header">'
                f'<span>{res["resource_id"]}</span>'
                f'<strong style="color:{sev_color};border:1px solid {sev_color};padding:3px 11px;border-radius:999px;font-size:0.78rem;">{sev}</strong>'
                f'</div>'
                f'<div class="flag-body">'
                f'<p><strong>Type:</strong> {res["type"]} &bull; <strong>Region:</strong> {res["region"]}</p>'
                f'<div class="util-bars">'
                f'<div class="util-row"><span>CPU</span><div class="util-bg"><div class="util-fill cpu-fill" style="width:{min(cpu,100)}%;"></div></div><span>{cpu}%</span></div>'
                f'<div class="util-row"><span>Mem</span><div class="util-bg"><div class="util-fill mem-fill" style="width:{min(mem,100)}%;"></div></div><span>{mem}%</span></div>'
                f'</div>'
                f'<p><strong>Cost:</strong> ${res.get("cost_monthly_usd", 0):,.2f}/mo &bull; <strong style="color:#34d399">Save: {saving_text}</strong></p>'
                f'<p style="color:#94a3b8;font-size:0.84rem;">{rec}</p>'
                f'</div></div>'
            )

        github_links = "".join(
            f'<li><a href="{url}" target="_blank" rel="noopener">{url}</a></li>'
            for url in github_urls
        )
        if not github_links:
            github_links = f'<li><a href="{GITHUB_ISSUES_URL}" target="_blank" rel="noopener">View all open issues on GitHub &rarr;</a></li>'

        training_info = self._get_training_info(output_dir)
        training_count = training_info["count"]
        training_ts = training_info["timestamp"]

        resources_json = json.dumps(resources, ensure_ascii=False)
        findings_clean = []
        for entry in findings:
            res = entry["resource"]
            analysis = entry.get("analysis", {})
            findings_clean.append({
                "resource_id": res["resource_id"],
                "type": res["type"],
                "region": res["region"],
                "cpu": res["cpu_avg_percent"],
                "memory": res.get("memory_avg_percent", 0),
                "cost": res["cost_monthly_usd"],
                "last_active_days": res["last_active_days"],
                "issue_type": entry.get("issue_type", "idle"),
                "severity": analysis.get("severity", entry.get("severity", "P2")),
                "saving": entry.get("potential_saving", analysis.get("estimated_saving_value", 0.0)),
                "saving_text": analysis.get("estimated_saving", f"${entry.get('potential_saving', 0):.2f}/month"),
                "recommendation": analysis.get("recommendation", "Review and adjust sizing."),
                "reason": analysis.get("reason", "Resource appears underutilized."),
            })
        findings_json = json.dumps(findings_clean, ensure_ascii=False)
        total_saving_json = json.dumps(round(total_saving, 2))
        github_url_json = json.dumps(GITHUB_ISSUES_URL)
        scan_time_json = json.dumps(scan_time)

        p0_count = sum(1 for e in findings if e.get("severity") == "P0" or e.get("analysis", {}).get("severity") == "P0")
        p1_count = sum(1 for e in findings if e.get("severity") == "P1" or e.get("analysis", {}).get("severity") == "P1")

        return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<meta name="description" content="Cloud Cost Optimizer Dashboard - AI-powered cloud spend analysis"/>
<title>Cloud Cost Optimizer Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
/* ═══════════════════════════════════════════════════════════════
   DESIGN TOKENS & RESET
═══════════════════════════════════════════════════════════════ */
:root {{
  --bg:        #060a12;
  --bg2:       #0d1628;
  --bg3:       #111e35;
  --border:    rgba(148,163,184,.09);
  --border2:   rgba(56,189,248,.18);
  --text:      #e2e8f0;
  --muted:     #64748b;
  --accent:    #38bdf8;
  --accent2:   #818cf8;
  --green:     #34d399;
  --red:       #ff6b6b;
  --yellow:    #ffd43b;
  --teal:      #00d4aa;
  --radius:    22px;
}}
[data-theme="light"] {{
  --bg:#f1f5f9; --bg2:#ffffff; --bg3:#f8fafc;
  --border:rgba(15,23,42,.1); --text:#0f172a; --muted:#64748b;
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
body{{
  font-family:'Inter',system-ui,sans-serif;
  background:var(--bg);color:var(--text);
  min-height:100vh;transition:background .3s,color .3s;
}}
.page{{max-width:1340px;margin:0 auto;padding:24px 18px 80px;}}

/* ─── Scrollbar ───────────────────────────────────────────── */
::-webkit-scrollbar{{width:5px;height:5px;}}
::-webkit-scrollbar-track{{background:transparent;}}
::-webkit-scrollbar-thumb{{background:rgba(148,163,184,.2);border-radius:4px;}}

/* ─── Topbar ──────────────────────────────────────────────── */
.topbar{{
  display:flex;flex-wrap:wrap;justify-content:space-between;gap:16px;align-items:center;
  background:rgba(13,22,40,.97);border:1px solid var(--border);border-radius:var(--radius);
  padding:22px 30px;margin-bottom:24px;
  box-shadow:0 4px 30px rgba(0,0,0,.3);
}}
.brand h1{{
  font-size:clamp(1.5rem,2.3vw,2.2rem);font-weight:900;letter-spacing:-0.04em;
  background:linear-gradient(135deg,#38bdf8 25%,#818cf8 65%,#a78bfa);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.brand p{{color:var(--muted);font-size:0.88rem;margin-top:4px;}}
.topbar-right{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}}
.nav-links{{display:flex;flex-wrap:wrap;gap:8px;}}
.nav-links a{{
  color:var(--accent);text-decoration:none;font-weight:600;padding:8px 16px;
  background:rgba(56,189,248,.07);border-radius:999px;border:1px solid rgba(56,189,248,.14);
  transition:all .2s;font-size:0.85rem;
}}
.nav-links a:hover{{background:rgba(56,189,248,.16);border-color:rgba(56,189,248,.35);}}
.theme-btn{{
  width:38px;height:38px;border-radius:50%;border:1px solid var(--border2);
  background:rgba(56,189,248,.07);color:var(--accent);cursor:pointer;
  display:flex;align-items:center;justify-content:center;transition:all .2s;font-size:1rem;
}}
.theme-btn:hover{{background:rgba(56,189,248,.16);}}

/* ─── Grid / Cards ────────────────────────────────────────── */
.grid{{display:grid;gap:18px;}}
.stats-grid{{grid-template-columns:repeat(4,minmax(185px,1fr));}}
.charts-grid{{grid-template-columns:1.6fr 1fr;}}
.card{{
  background:var(--bg2);border:1px solid var(--border);
  border-radius:var(--radius);padding:24px 26px;
  box-shadow:0 12px 40px rgba(0,0,0,.18);
  transition:border-color .2s;
}}
.card:hover{{border-color:rgba(56,189,248,.12);}}
.card-title{{
  font-size:0.78rem;color:var(--muted);font-weight:700;
  text-transform:uppercase;letter-spacing:.09em;margin-bottom:16px;
}}

/* ─── Stat cards ──────────────────────────────────────────── */
.stat-card{{
  display:flex;flex-direction:column;justify-content:center;gap:8px;
  min-height:125px;position:relative;overflow:hidden;
  transition:transform .2s,border-color .2s;cursor:default;
}}
.stat-card::after{{
  content:'';position:absolute;inset:0;border-radius:var(--radius);
  background:linear-gradient(135deg,rgba(56,189,248,.06),transparent);
  opacity:0;transition:opacity .3s;
}}
.stat-card:hover{{transform:translateY(-3px);border-color:rgba(56,189,248,.22);}}
.stat-card:hover::after{{opacity:1;}}
.stat-label{{font-size:0.78rem;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.08em;}}
.stat-value{{font-size:2.2rem;font-weight:900;line-height:1;}}
.stat-sub{{font-size:0.75rem;color:var(--muted);margin-top:2px;}}

/* ─── Table ───────────────────────────────────────────────── */
.table-wrap{{overflow-x:auto;}}
.table{{width:100%;border-collapse:collapse;min-width:440px;}}
.table th,.table td{{
  text-align:left;padding:11px 12px;
  border-bottom:1px solid rgba(148,163,184,.06);
}}
.table th{{font-size:0.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;}}
.table tbody tr{{transition:background .15s;}}
.table tbody tr:hover{{background:rgba(56,189,248,.04);}}

/* Search/filter bar */
.filter-bar{{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap;}}
#resource-search{{
  flex:1;min-width:160px;background:var(--bg3);border:1px solid var(--border);
  border-radius:10px;padding:9px 14px;color:var(--text);font-size:0.85rem;
  font-family:inherit;outline:none;transition:border-color .2s;
}}
#resource-search:focus{{border-color:var(--border2);}}
#resource-search::placeholder{{color:var(--muted);}}
.filter-pills{{display:flex;gap:7px;flex-wrap:wrap;}}
.fpill{{
  padding:7px 13px;border-radius:999px;font-size:0.78rem;font-weight:600;cursor:pointer;
  border:1px solid var(--border);background:transparent;color:var(--muted);
  transition:all .2s;
}}
.fpill.active,.fpill:hover{{background:rgba(56,189,248,.1);border-color:rgba(56,189,248,.3);color:var(--accent);}}

/* ─── Utilisation mini-bars ───────────────────────────────── */
.util-bars{{display:grid;gap:6px;margin:8px 0;}}
.util-row{{display:flex;align-items:center;gap:8px;font-size:0.75rem;color:var(--muted);}}
.util-row span:first-child{{width:28px;flex-shrink:0;}}
.util-row span:last-child{{width:30px;text-align:right;flex-shrink:0;}}
.util-bg{{flex:1;height:6px;border-radius:999px;background:rgba(148,163,184,.1);overflow:hidden;}}
.util-fill{{height:100%;border-radius:999px;transition:width .8s ease;}}
.cpu-fill{{background:linear-gradient(90deg,#38bdf8,#818cf8);}}
.mem-fill{{background:linear-gradient(90deg,#34d399,#059669);}}

/* ─── Donut ───────────────────────────────────────────────── */
.donut-wrapper{{display:flex;flex-direction:column;align-items:center;gap:16px;}}
.donut-legend{{display:grid;gap:10px;width:100%;}}
.legend-item{{display:flex;align-items:center;gap:10px;font-size:0.88rem;color:var(--text);}}
.legend-color{{width:13px;height:13px;border-radius:4px;flex-shrink:0;}}

/* ─── Weekly trend ────────────────────────────────────────── */
.weekly-list{{display:grid;gap:11px;}}
.weekly-item{{
  background:rgba(13,22,40,.8);border:1px solid var(--border);
  border-radius:14px;padding:13px 17px;display:grid;gap:9px;
  transition:border-color .2s;
}}
.weekly-item:hover{{border-color:rgba(56,189,248,.2);}}
.weekly-meta{{display:flex;justify-content:space-between;align-items:center;}}
.weekly-label{{font-weight:700;font-size:0.88rem;color:#94a3b8;}}
.gh-week-link{{
  display:inline-flex;align-items:center;gap:5px;font-size:0.75rem;font-weight:600;
  color:var(--accent);text-decoration:none;padding:4px 11px;border-radius:999px;
  background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.18);
  transition:all .2s;
}}
.gh-week-link:hover{{background:rgba(56,189,248,.18);border-color:rgba(56,189,248,.4);}}
.weekly-bar-wrap{{display:flex;align-items:center;gap:12px;}}
.bar-bg{{flex:1;height:8px;border-radius:999px;background:rgba(148,163,184,.1);overflow:hidden;}}
.bar-fill{{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .9s cubic-bezier(.4,0,.2,1);}}
.weekly-waste{{font-size:0.8rem;color:#94a3b8;white-space:nowrap;min-width:65px;text-align:right;}}

/* ─── Flag cards ──────────────────────────────────────────── */
.flag-grid{{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));}}
.flag-card{{
  background:rgba(7,12,24,.85);border:1px solid var(--border);
  border-radius:18px;padding:18px;transition:border-color .2s,transform .2s;
}}
.flag-card:hover{{border-color:rgba(56,189,248,.2);transform:translateY(-2px);}}
.flag-card[data-severity="P0"]{{border-left:3px solid #ff6b6b;}}
.flag-card[data-severity="P1"]{{border-left:3px solid #ffd43b;}}
.flag-card[data-severity="P2"]{{border-left:3px solid #00d4aa;}}
.flag-header{{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap;}}
.flag-header span{{font-size:0.9rem;font-weight:700;}}
.flag-body p{{margin:6px 0;line-height:1.6;font-size:0.85rem;}}

/* ─── Savings Calculator ──────────────────────────────────── */
.calc-card{{margin-top:18px;}}
.calc-body{{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:center;}}
.calc-left label{{font-size:0.82rem;color:var(--muted);display:block;margin-bottom:8px;font-weight:600;}}
.calc-slider{{width:100%;-webkit-appearance:none;appearance:none;height:6px;border-radius:999px;
  background:linear-gradient(90deg,var(--accent) 0%,rgba(148,163,184,.2) 0%);outline:none;cursor:pointer;}}
.calc-slider::-webkit-slider-thumb{{-webkit-appearance:none;width:20px;height:20px;border-radius:50%;
  background:linear-gradient(135deg,var(--accent),var(--accent2));border:2px solid var(--bg);
  box-shadow:0 4px 12px rgba(56,189,248,.4);cursor:pointer;}}
.calc-right{{
  background:rgba(52,211,153,.06);border:1px solid rgba(52,211,153,.18);
  border-radius:16px;padding:20px;text-align:center;
}}
.calc-result-label{{font-size:0.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;}}
.calc-result-value{{font-size:2rem;font-weight:900;color:var(--green);line-height:1;}}
.calc-result-annual{{font-size:0.88rem;color:#6ee7b7;margin-top:6px;}}

/* ─── Live info ───────────────────────────────────────────── */
.live-info{{
  display:flex;flex-wrap:wrap;justify-content:space-between;gap:10px;margin-top:16px;
  padding:12px 20px;border-radius:13px;background:rgba(13,22,40,.8);
  border:1px solid rgba(56,189,248,.08);color:var(--muted);font-size:0.83rem;
}}
.refresh-button{{
  display:inline-flex;align-items:center;gap:6px;padding:6px 14px;
  border:1px solid rgba(56,189,248,.18);border-radius:999px;background:rgba(56,189,248,.06);
  color:var(--accent);cursor:pointer;transition:all .2s;font-size:0.83rem;
}}
.refresh-button:hover{{background:rgba(56,189,248,.14);}}

/* ─── Export bar ──────────────────────────────────────────── */
.export-bar{{
  display:flex;gap:10px;margin-top:18px;flex-wrap:wrap;
}}
.export-btn{{
  display:inline-flex;align-items:center;gap:7px;padding:9px 18px;border-radius:12px;
  font-size:0.83rem;font-weight:600;cursor:pointer;transition:all .2s;border:1px solid;
}}
.export-btn.csv{{color:#34d399;border-color:rgba(52,211,153,.25);background:rgba(52,211,153,.07);}}
.export-btn.csv:hover{{background:rgba(52,211,153,.15);}}
.export-btn.json-btn{{color:#818cf8;border-color:rgba(129,140,248,.25);background:rgba(129,140,248,.07);}}
.export-btn.json-btn:hover{{background:rgba(129,140,248,.15);}}
.export-btn.print-btn{{color:#ffd43b;border-color:rgba(255,212,59,.25);background:rgba(255,212,59,.07);}}
.export-btn.print-btn:hover{{background:rgba(255,212,59,.15);}}

/* ══════════════════════════════════════════════════════════════
   █████████   CHATBOT   █████████
══════════════════════════════════════════════════════════════ */
#chatbot-section{{
  margin-top:22px;
  background:linear-gradient(150deg,rgba(13,22,40,.99),rgba(18,28,50,.99));
  border:1px solid rgba(56,189,248,.22);
  border-radius:28px;overflow:hidden;
  box-shadow:0 30px 80px rgba(0,0,0,.4), inset 0 1px 0 rgba(56,189,248,.08);
}}

/* Chat header */
.chat-header{{
  display:flex;align-items:center;gap:14px;padding:20px 26px;
  background:linear-gradient(90deg,rgba(56,189,248,.1),rgba(129,140,248,.08));
  border-bottom:1px solid rgba(56,189,248,.12);
}}
.chat-avatar{{
  width:50px;height:50px;border-radius:16px;flex-shrink:0;
  background:linear-gradient(135deg,#38bdf8,#818cf8);
  display:flex;align-items:center;justify-content:center;font-size:1.4rem;
  box-shadow:0 6px 20px rgba(56,189,248,.35);
}}
.chat-header-info h2{{
  font-size:1.05rem;font-weight:800;color:var(--text);margin:0 0 3px;
  text-transform:none;letter-spacing:-0.01em;
}}
.chat-header-info p{{color:var(--muted);font-size:0.82rem;}}
.chat-status-badge{{
  margin-left:auto;display:flex;align-items:center;gap:7px;
  background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.25);
  padding:6px 14px;border-radius:999px;font-size:0.78rem;font-weight:700;color:#22c55e;
}}
.status-dot{{
  width:8px;height:8px;border-radius:50%;background:#22c55e;
  box-shadow:0 0 8px #22c55e;animation:pulse 2s infinite;
}}
@keyframes pulse{{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:.5;transform:scale(.8);}}}}

/* Chat body: 2-column layout */
.chat-body{{display:grid;grid-template-columns:1fr 270px;min-height:520px;}}

/* Messages pane */
.chat-messages-pane{{display:flex;flex-direction:column;border-right:1px solid rgba(148,163,184,.07);}}
.chat-messages{{
  flex:1;overflow-y:auto;padding:18px 20px;display:flex;flex-direction:column;gap:13px;
  scrollbar-width:thin;scrollbar-color:rgba(148,163,184,.12) transparent;
}}

/* Messages */
.msg{{display:flex;gap:9px;align-items:flex-end;animation:msgIn .35s cubic-bezier(.34,1.56,.64,1);}}
@keyframes msgIn{{from{{opacity:0;transform:translateY(12px) scale(.96);}}to{{opacity:1;transform:none;}}}}
.msg.user{{flex-direction:row-reverse;}}
.msg-avatar{{
  width:30px;height:30px;border-radius:50%;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:0.85rem;
}}
.msg.bot .msg-avatar{{background:linear-gradient(135deg,#38bdf8,#818cf8);}}
.msg.user .msg-avatar{{background:linear-gradient(135deg,#6366f1,#a855f7);}}
.msg-bubble{{
  max-width:80%;padding:11px 15px;border-radius:18px;font-size:0.875rem;line-height:1.65;
}}
.msg.bot .msg-bubble{{
  background:rgba(25,38,62,.95);border:1px solid rgba(148,163,184,.1);
  color:var(--text);border-bottom-left-radius:4px;
}}
.msg.user .msg-bubble{{
  background:linear-gradient(135deg,#38bdf8,#818cf8);
  color:#fff;border-bottom-right-radius:4px;
}}
.msg-bubble strong{{color:var(--accent);}}
.msg.user .msg-bubble strong{{color:#fff;}}
.msg-bubble a{{color:var(--accent);}}
.msg.user .msg-bubble a{{color:#dbeafe;}}
.msg-bubble code{{background:rgba(56,189,248,.12);padding:1px 6px;border-radius:5px;font-size:0.8em;color:#7dd3fc;}}
.msg-time{{font-size:0.7rem;color:var(--muted);margin-top:3px;padding:0 4px;}}

/* Typing indicator */
.typing-indicator{{display:flex;gap:5px;align-items:center;padding:3px 0;}}
.typing-dot{{width:7px;height:7px;border-radius:50%;background:#475569;animation:bounce 1.3s infinite;}}
.typing-dot:nth-child(2){{animation-delay:.18s;}}
.typing-dot:nth-child(3){{animation-delay:.36s;}}
@keyframes bounce{{0%,60%,100%{{transform:translateY(0);opacity:.5;}}30%{{transform:translateY(-7px);opacity:1;}}}}

/* Input bar */
.chat-input-bar{{
  display:flex;gap:9px;padding:13px 16px;
  border-top:1px solid rgba(148,163,184,.07);flex-shrink:0;
  background:rgba(8,13,26,.5);
}}
#chat-textarea{{
  flex:1;background:rgba(25,38,62,.7);border:1px solid rgba(148,163,184,.12);
  border-radius:13px;padding:11px 15px;color:var(--text);font-size:0.875rem;
  font-family:inherit;outline:none;resize:none;
  transition:border-color .2s,box-shadow .2s;min-height:44px;
}}
#chat-textarea:focus{{border-color:var(--border2);box-shadow:0 0 0 3px rgba(56,189,248,.08);}}
#chat-textarea::placeholder{{color:#475569;}}
#chat-send-btn{{
  width:44px;height:44px;border-radius:13px;border:none;flex-shrink:0;align-self:flex-end;
  background:linear-gradient(135deg,#38bdf8,#818cf8);cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:transform .2s,box-shadow .2s;box-shadow:0 4px 14px rgba(56,189,248,.3);
}}
#chat-send-btn:hover{{transform:scale(1.09);box-shadow:0 6px 20px rgba(56,189,248,.5);}}
#chat-send-btn:active{{transform:scale(.94);}}
#chat-send-btn:disabled{{opacity:.5;transform:none;}}

/* Chat sidebar */
.chat-sidebar{{display:flex;flex-direction:column;gap:0;padding:18px;background:rgba(7,11,22,.45);overflow-y:auto;}}
.sidebar-section-title{{
  font-size:0.72rem;font-weight:700;color:#475569;
  text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px;
}}
.chip-grid{{display:flex;flex-direction:column;gap:7px;margin-bottom:16px;}}
.q-chip{{
  text-align:left;padding:9px 13px;border-radius:11px;font-size:0.8rem;font-weight:500;
  background:rgba(56,189,248,.05);border:1px solid rgba(56,189,248,.12);color:#94a3b8;
  cursor:pointer;transition:all .2s;line-height:1.4;
}}
.q-chip:hover{{background:rgba(56,189,248,.14);border-color:rgba(56,189,248,.32);color:var(--text);}}
.sidebar-sep{{border:none;border-top:1px solid rgba(148,163,184,.07);margin:14px 0;}}
.mini-stats{{display:grid;gap:9px;}}
.mini-stat{{
  background:rgba(13,22,40,.8);border-radius:11px;padding:11px 13px;
  border:1px solid var(--border);
}}
.mini-stat-label{{font-size:0.7rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:.07em;margin-bottom:3px;}}
.mini-stat-value{{font-size:1.05rem;font-weight:800;}}

/* ─── Floating bubble ─────────────────────────────────────── */
#chat-fab{{
  position:fixed;bottom:26px;right:26px;width:54px;height:54px;border-radius:50%;
  background:linear-gradient(135deg,#38bdf8,#818cf8);border:none;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 8px 26px rgba(56,189,248,.5);z-index:999;
  transition:transform .3s cubic-bezier(.34,1.56,.64,1),box-shadow .3s;
  animation:fabPulse 3s ease-in-out infinite;
}}
#chat-fab:hover{{transform:scale(1.12);box-shadow:0 12px 36px rgba(56,189,248,.65);animation:none;}}
@keyframes fabPulse{{0%,100%{{box-shadow:0 8px 26px rgba(56,189,248,.5);}}50%{{box-shadow:0 8px 36px rgba(56,189,248,.8),0 0 0 8px rgba(56,189,248,.1);}}}}

/* ─── Notification toast ──────────────────────────────────── */
#toast{{
  position:fixed;top:24px;right:24px;z-index:9999;
  background:rgba(13,22,40,.97);border:1px solid rgba(56,189,248,.25);
  border-radius:14px;padding:14px 20px;font-size:0.88rem;color:var(--text);
  box-shadow:0 10px 40px rgba(0,0,0,.4);
  transform:translateX(120%);transition:transform .35s cubic-bezier(.34,1.56,.64,1);
  max-width:320px;display:flex;align-items:center;gap:10px;
}}
#toast.show{{transform:translateX(0);}}

/* ─── Misc ────────────────────────────────────────────────── */
a{{color:var(--accent);}}
.agent-card{{
  background:rgba(56,189,248,.03);border:1px solid rgba(56,189,248,.1);
  border-radius:18px;padding:20px 24px;margin-top:18px;
}}
@media(max-width:1080px){{.stats-grid,.charts-grid{{grid-template-columns:1fr;}}}}
@media(max-width:800px){{
  .chat-body{{grid-template-columns:1fr;}}
  .chat-sidebar{{border-top:1px solid rgba(148,163,184,.07);}}
  .calc-body{{grid-template-columns:1fr;}}
  .topbar{{flex-direction:column;align-items:stretch;}}
}}
@media print{{
  #chat-fab,#toast,.export-bar,.refresh-button,.chat-input-bar,.chat-sidebar,.live-info{{display:none!important;}}
  body{{background:#fff;color:#000;}}
  .card,.chatbot-section{{box-shadow:none;border:1px solid #ddd;}}
}}
</style>
</head>
<body>
<div class="page">

<!-- ── Topbar ─────────────────────────────────────────────── -->
<div class="topbar">
  <div class="brand">
    <h1>&#x2601;&#xFE0F; Cloud Cost Optimizer</h1>
    <p>AI-powered cloud spend analysis &bull; Real-time recommendations &bull; {scan_time}</p>
  </div>
  <div class="topbar-right">
    <nav class="nav-links">
      <a href="#summary">Summary</a>
      <a href="#charts">Charts</a>
      <a href="#trend">Trends</a>
      <a href="#findings">Findings</a>
      <a href="#chatbot-section">&#x1F916; AI Chat</a>
    </nav>
    <button class="theme-btn" id="theme-toggle" title="Toggle dark/light mode">&#x1F31E;</button>
  </div>
</div>

<!-- ── Export bar ─────────────────────────────────────────── -->
<div class="export-bar">
  <button class="export-btn csv" id="btn-export-csv">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
    Export CSV
  </button>
  <button class="export-btn json-btn" id="btn-export-json">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
    Export JSON
  </button>
  <button class="export-btn print-btn" onclick="window.print()">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
    Print / PDF
  </button>
</div>

<!-- ── Stats ──────────────────────────────────────────────── -->
<div class="grid stats-grid" id="summary" style="margin-top:18px;">
  <div class="card stat-card">
    <div class="stat-label">Resources Scanned</div>
    <div class="stat-value" id="cnt-resources">0</div>
    <div class="stat-sub">across all regions</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">Issues Found</div>
    <div class="stat-value" id="cnt-issues" style="color:#fb7185;">0</div>
    <div class="stat-sub">{p0_count} critical &bull; {p1_count} warnings</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">Estimated Savings</div>
    <div class="stat-value" id="cnt-savings" style="color:#34d399;">$0</div>
    <div class="stat-sub">per month</div>
  </div>
  <div class="card stat-card">
    <div class="stat-label">GitHub Issues</div>
    <div class="stat-value" id="cnt-github" style="color:#facc15;">0</div>
    <div class="stat-sub"><a href="{GITHUB_ISSUES_URL}" target="_blank">View on GitHub &rarr;</a></div>
  </div>
</div>

<!-- ── Live bar ───────────────────────────────────────────── -->
<div class="live-info">
  <div>&#x1F7E2; Live dashboard &bull; auto-refresh every 30 s</div>
  <div>Last scan: <strong id="last-updated">{scan_time}</strong></div>
  <button class="refresh-button" onclick="location.reload()">&#x21bb; Refresh</button>
  <div>Next in <strong id="refresh-countdown">30</strong>s</div>
</div>

<!-- ── Charts ─────────────────────────────────────────────── -->
<div class="grid charts-grid" id="charts" style="margin-top:20px;">
  <div class="card">
    <div class="card-title">Resource Inventory &amp; Health</div>
    <div class="filter-bar">
      <input type="text" id="resource-search" placeholder="&#x1F50D; Search resource ID or type...">
      <div class="filter-pills">
        <button class="fpill active" data-filter="all">All</button>
        <button class="fpill" data-filter="flagged">Flagged</button>
        <button class="fpill" data-filter="healthy">Healthy</button>
      </div>
    </div>
    <div class="table-wrap">
      <table class="table" id="resource-table">
        <thead><tr>
          <th style="width:26%">Resource</th><th style="width:13%">Type</th>
          <th style="width:12%">CPU</th><th style="width:16%">Cost/mo</th><th style="width:14%">Status</th>
          <th style="width:19%">Waste Score</th>
        </tr></thead>
        <tbody id="resource-tbody">
          {''.join(self._resource_table_row(r, findings) for r in resources)}
        </tbody>
      </table>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Savings by Severity</div>
    <div class="donut-wrapper">
      <svg width="200" height="200" viewBox="0 0 260 260">
        <circle cx="130" cy="130" r="88" fill="none" stroke="#0a1020" stroke-width="44"/>
        {''.join(self._donut_segment_svg(s) for s in donut_segments)}
        <text x="130" y="132" fill="#e2e8f0" font-size="20" font-weight="900" text-anchor="middle">${total_saving:,.0f}</text>
        <text x="130" y="150" fill="#64748b" font-size="10" text-anchor="middle">potential savings</text>
      </svg>
      <div class="donut-legend">{''.join(self._donut_legend_html(s) for s in donut_segments)}</div>
    </div>
  </div>
</div>

<!-- ── Weekly trend ───────────────────────────────────────── -->
<div class="card" id="trend" style="margin-top:20px;">
  <div class="card-title">Weekly Spend &amp; Issue Trend &nbsp;<a href="{GITHUB_ISSUES_URL}" target="_blank" style="font-size:0.8rem;text-transform:none;font-weight:600;">View All Issues &rarr;</a></div>
  <div class="weekly-list">{weekly_rows}</div>
</div>

<!-- ── Savings calculator ─────────────────────────────────── -->
<div class="card calc-card" id="calculator">
  <div class="card-title">&#x1F4B9; Interactive Savings Calculator</div>
  <div class="calc-body">
    <div class="calc-left">
      <label>Remediation coverage: <strong id="coverage-pct">50</strong>% of flagged issues</label>
      <input type="range" class="calc-slider" id="coverage-slider" min="0" max="100" value="50">
      <p style="margin-top:14px;color:var(--muted);font-size:0.82rem;">Drag the slider to estimate savings based on how many flagged resources you remediate.</p>
    </div>
    <div class="calc-right">
      <div class="calc-result-label">Projected Monthly Savings</div>
      <div class="calc-result-value" id="calc-result">$0</div>
      <div class="calc-result-annual" id="calc-annual">$0 / year</div>
    </div>
  </div>
</div>

<!-- ── Findings ───────────────────────────────────────────── -->
<div class="card" id="findings" style="margin-top:20px;">
  <div class="card-title">Flagged Resources &amp; Recommendations</div>
  <div class="flag-grid" style="margin-top:6px;">{flagged_cards}</div>
</div>

<!-- ── GitHub issues ──────────────────────────────────────── -->
<div class="card" id="issues" style="margin-top:20px;">
  <div class="card-title">GitHub Issue Links</div>
  <ul style="padding-left:20px;display:grid;gap:7px;margin-top:4px;">{github_links}</ul>
</div>

<!-- ── AI Agent ───────────────────────────────────────────── -->
<div class="agent-card">
  <div class="card-title">AI Agent Studio</div>
  <p style="color:#cbd5e1;line-height:1.7;font-size:0.9rem;">
    LLM-powered recommendation engine &bull; Training examples: <strong>{training_count}</strong> &bull; Last generated: <strong>{training_ts}</strong>
  </p>
  <p style="color:#475569;margin-top:8px;font-size:0.82rem;">
    Run <code>python main.py --train</code> to refresh &bull; <code>python main.py --serve --ai</code> for Ollama backend
  </p>
</div>

<!-- ═══════════════════════════════════════════════════════════
     ██████   CHATBOT SECTION   ██████
═══════════════════════════════════════════════════════════════ -->
<div id="chatbot-section">

  <!-- Header -->
  <div class="chat-header">
    <div class="chat-avatar">&#x1F916;</div>
    <div class="chat-header-info">
      <h2>Cloud Cost AI Assistant</h2>
      <p>Intelligent analysis &bull; Knows your infrastructure &bull; Instant answers, no server needed</p>
    </div>
    <div class="chat-status-badge">
      <div class="status-dot"></div>
      Online &amp; Ready
    </div>
  </div>

  <!-- Body -->
  <div class="chat-body">

    <!-- Left: messages + input -->
    <div class="chat-messages-pane">
      <div class="chat-messages" id="chat-messages"></div>
      <div class="chat-input-bar">
        <textarea id="chat-textarea" rows="1" placeholder="Ask about costs, savings, resources, or type 'help'..."></textarea>
        <button id="chat-send-btn" title="Send">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Right: quick chips + mini stats -->
    <div class="chat-sidebar">
      <div class="sidebar-section-title">&#x26A1; Quick Questions</div>
      <div class="chip-grid" id="chip-grid">
        <button class="q-chip" data-q="Give me a full summary">&#x1F4CB; Full Summary</button>
        <button class="q-chip" data-q="What are my total potential savings?">&#x1F4B0; Total Savings</button>
        <button class="q-chip" data-q="Show P0 critical issues">&#x1F6A8; P0 Critical</button>
        <button class="q-chip" data-q="Which resources should I fix first?">&#x1F3AF; Fix Priority</button>
        <button class="q-chip" data-q="Show idle or inactive resources">&#x1F634; Idle Resources</button>
        <button class="q-chip" data-q="Most expensive resources">&#x1F4C8; Most Expensive</button>
        <button class="q-chip" data-q="Spend breakdown by region">&#x1F30D; By Region</button>
        <button class="q-chip" data-q="How can I reduce costs?">&#x2702;&#xFE0F; Reduce Costs</button>
        <button class="q-chip" data-q="What are P1 warning issues?">&#x26A0;&#xFE0F; P1 Warnings</button>
        <button class="q-chip" data-q="Show me a cost forecast">&#x1F4C6; Cost Forecast</button>
      </div>
      <hr class="sidebar-sep">
      <div class="sidebar-section-title">&#x1F4CA; Live Stats</div>
      <div class="mini-stats">
        <div class="mini-stat">
          <div class="mini-stat-label">Total Spend</div>
          <div class="mini-stat-value" style="color:#94a3b8;">${total_cost:,.0f}<span style="font-size:0.65rem;color:#475569;font-weight:500;">/mo</span></div>
        </div>
        <div class="mini-stat">
          <div class="mini-stat-label">Savings Available</div>
          <div class="mini-stat-value" style="color:#34d399;">${total_saving:,.0f}<span style="font-size:0.65rem;color:#475569;font-weight:500;">/mo</span></div>
        </div>
        <div class="mini-stat">
          <div class="mini-stat-label">Issues Flagged</div>
          <div class="mini-stat-value" style="color:#fb7185;">{issues_found}</div>
        </div>
        <div class="mini-stat">
          <div class="mini-stat-label">GitHub</div>
          <div class="mini-stat-value"><a href="{GITHUB_ISSUES_URL}" target="_blank" style="color:#38bdf8;font-size:0.82rem;text-decoration:none;font-weight:700;">View {github_count} Issues &rarr;</a></div>
        </div>
      </div>
    </div>
  </div>
</div><!-- end chatbot-section -->

<div class="card" style="margin-top:20px;text-align:center;">
  <p style="color:#334155;font-size:0.82rem;">Report generated at {scan_time} &bull; Cloud Cost Optimizer &bull; <a href="{GITHUB_ISSUES_URL}" target="_blank">GitHub Issues</a></p>
</div>

</div><!-- end .page -->

<!-- Floating bubble → scrolls to chatbot -->
<button id="chat-fab" onclick="document.getElementById('chatbot-section').scrollIntoView({{behavior:'smooth'}});setTimeout(()=>document.getElementById('chat-textarea').focus(),600);" title="Open AI Chat">
  <svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
</button>

<!-- Toast notification -->
<div id="toast"></div>

<!-- ══════════════  JAVASCRIPT  ══════════════ -->
<script>
// ── Embedded data ───────────────────────────────────────────────────────────
const RESOURCES    = {resources_json};
const FINDINGS     = {findings_json};
const TOTAL_SAVING = {total_saving_json};
const TOTAL_COST   = {total_cost};
const GH_URL       = {github_url_json};
const SCAN_TIME    = {scan_time_json};

// ── Animated counters ───────────────────────────────────────────────────────
function animateCounter(el, target, prefix='', suffix='', decimals=0, duration=1200) {{
  const start = performance.now();
  function step(now) {{
    const p = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - p, 4);
    const val = target * ease;
    el.textContent = prefix + val.toLocaleString('en-US', {{
      minimumFractionDigits: decimals, maximumFractionDigits: decimals
    }}) + suffix;
    if (p < 1) requestAnimationFrame(step);
  }}
  requestAnimationFrame(step);
}}

window.addEventListener('DOMContentLoaded', () => {{
  animateCounter(document.getElementById('cnt-resources'), {resources_scanned}, '', '', 0);
  animateCounter(document.getElementById('cnt-issues'),    {issues_found},     '', '', 0);
  animateCounter(document.getElementById('cnt-savings'),   {total_saving},     '$', '', 2, 1600);
  animateCounter(document.getElementById('cnt-github'),    {github_count},     '', '', 0);
}});

// ── Search & filter table ───────────────────────────────────────────────────
const searchEl  = document.getElementById('resource-search');
const tbody     = document.getElementById('resource-tbody');
let activeFilter = 'all';

function applyFilter() {{
  const q = searchEl.value.toLowerCase();
  Array.from(tbody.rows).forEach(row => {{
    const text   = row.textContent.toLowerCase();
    const status = row.dataset.status || '';
    const matchQ = !q || text.includes(q);
    const matchF = activeFilter === 'all'
      || (activeFilter === 'flagged' && status === 'flagged')
      || (activeFilter === 'healthy' && status === 'healthy');
    row.style.display = matchQ && matchF ? '' : 'none';
  }});
}}
searchEl.addEventListener('input', applyFilter);
document.querySelectorAll('.fpill').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.fpill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter;
    applyFilter();
  }});
}});

// ── Theme toggle ────────────────────────────────────────────────────────────
const themeBtn = document.getElementById('theme-toggle');
themeBtn.addEventListener('click', () => {{
  const html = document.documentElement;
  const isLight = html.dataset.theme === 'light';
  html.dataset.theme = isLight ? 'dark' : 'light';
  themeBtn.textContent = isLight ? '🌙' : '☀️';
  showToast(isLight ? '🌙 Dark mode on' : '☀️ Light mode on');
}});

// ── Toast ───────────────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg) {{
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2800);
}}

// ── Export CSV ──────────────────────────────────────────────────────────────
document.getElementById('btn-export-csv').addEventListener('click', () => {{
  const headers = ['resource_id','type','region','cpu_avg_percent','memory_avg_percent','cost_monthly_usd','last_active_days','flagged','severity','potential_saving'];
  const flagMap = {{}};
  FINDINGS.forEach(f => {{ flagMap[f.resource_id] = {{severity:f.severity, saving:f.saving}}; }});
  const rows = RESOURCES.map(r => {{
    const f = flagMap[r.resource_id];
    return [r.resource_id,r.type,r.region,r.cpu_avg_percent,r.memory_avg_percent,
            r.cost_monthly_usd,r.last_active_days,
            f?'yes':'no', f?f.severity:'', f?f.saving:''].join(',');
  }});
  const csv = [headers.join(','), ...rows].join('\\n');
  const blob = new Blob([csv], {{type:'text/csv'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'cloud_cost_report.csv';
  a.click();
  showToast('✅ CSV exported!');
}});

// ── Export JSON ─────────────────────────────────────────────────────────────
document.getElementById('btn-export-json').addEventListener('click', () => {{
  const data = {{scan_time: SCAN_TIME, total_cost: TOTAL_COST, total_saving: TOTAL_SAVING, resources: RESOURCES, findings: FINDINGS}};
  const blob = new Blob([JSON.stringify(data, null, 2)], {{type:'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'cloud_cost_report.json';
  a.click();
  showToast('✅ JSON exported!');
}});

// ── Savings calculator ──────────────────────────────────────────────────────
const slider  = document.getElementById('coverage-slider');
const pctEl   = document.getElementById('coverage-pct');
const resultEl = document.getElementById('calc-result');
const annualEl = document.getElementById('calc-annual');
function updateCalc() {{
  const pct = parseInt(slider.value);
  pctEl.textContent = pct;
  const monthly = TOTAL_SAVING * (pct / 100);
  resultEl.textContent = '$' + monthly.toLocaleString('en-US', {{minimumFractionDigits:2, maximumFractionDigits:2}});
  annualEl.textContent = '$' + (monthly * 12).toLocaleString('en-US', {{minimumFractionDigits:2, maximumFractionDigits:2}}) + ' / year';
  // Update slider gradient
  slider.style.background = `linear-gradient(90deg, #38bdf8 ${{pct}}%, rgba(148,163,184,.2) ${{pct}}%)`;
}}
slider.addEventListener('input', updateCalc);
updateCalc();

// ══════════════════════════════════════════════════════════════
//  CHATBOT ENGINE
// ══════════════════════════════════════════════════════════════
const Bot = {{
  _fmt(v) {{ return '$' + (+v).toLocaleString('en-US', {{minimumFractionDigits:2,maximumFractionDigits:2}}); }},

  greet() {{
    const p0 = FINDINGS.filter(f=>f.severity==='P0').length;
    const p1 = FINDINGS.filter(f=>f.severity==='P1').length;
    const pct = TOTAL_COST>0?((TOTAL_SAVING/TOTAL_COST)*100).toFixed(1):0;
    return `👋 Hi! I'm your <strong>Cloud Cost AI</strong> — I've already analysed your infrastructure.<br><br>`
      + `📊 <strong>${{RESOURCES.length}}</strong> resources scanned &bull; <strong>${{FINDINGS.length}}</strong> issues detected<br>`
      + `🚨 <strong style="color:#ff6b6b">${{p0}}</strong> P0 Critical &bull; <strong style="color:#ffd43b">${{p1}}</strong> P1 Warnings<br>`
      + `💰 Potential: <strong style="color:#34d399">${{this._fmt(TOTAL_SAVING)}}/mo</strong> (${{pct}}% of total spend)<br><br>`
      + `👉 Click a <strong>Quick Question</strong> on the right, or type anything below!`;
  }},

  summary() {{
    const p0=FINDINGS.filter(f=>f.severity==='P0').length;
    const p1=FINDINGS.filter(f=>f.severity==='P1').length;
    const p2=FINDINGS.filter(f=>f.severity==='P2').length;
    const pct=TOTAL_COST>0?((TOTAL_SAVING/TOTAL_COST)*100).toFixed(1):0;
    return `📋 <strong>Dashboard Summary</strong><br><br>`
      +`• Total monthly spend: <strong>${{this._fmt(TOTAL_COST)}}</strong><br>`
      +`• Potential savings: <strong style="color:#34d399">${{this._fmt(TOTAL_SAVING)}}/mo</strong> (${{pct}}% waste)<br>`
      +`• Annual savings potential: <strong style="color:#34d399">${{this._fmt(TOTAL_SAVING*12)}}/yr</strong><br>`
      +`• Resources scanned: <strong>${{RESOURCES.length}}</strong><br>`
      +`• Issues flagged: P0 <strong style="color:#ff6b6b">${{p0}}</strong> &bull; P1 <strong style="color:#ffd43b">${{p1}}</strong> &bull; P2 <strong style="color:#00d4aa">${{p2}}</strong><br><br>`
      +`<a href="${{GH_URL}}" target="_blank">View GitHub Issues →</a>`;
  }},

  savings() {{
    const top = [...FINDINGS].sort((a,b)=>b.saving-a.saving).slice(0,5);
    let out = `💰 <strong>Top Savings Opportunities:</strong><br><br>`;
    top.forEach((f,i)=>{{
      const c=f.severity==='P0'?'#ff6b6b':f.severity==='P1'?'#ffd43b':'#00d4aa';
      out+=`${{i+1}}. <strong>${{f.resource_id}}</strong> — <strong style="color:#34d399">${{f.saving_text}}</strong> <span style="color:${{c}};font-size:0.8em">(${{f.severity}})</span><br>`;
    }});
    out+=`<br>Total recoverable: <strong style="color:#34d399">${{this._fmt(TOTAL_SAVING)}}/month &bull; ${{this._fmt(TOTAL_SAVING*12)}}/year</strong>`;
    return out;
  }},

  p0Issues() {{
    const crit=FINDINGS.filter(f=>f.severity==='P0');
    if(!crit.length) return '✅ No P0 critical issues found — great news!';
    let out=`🚨 <strong>${{crit.length}} P0 Critical Issue${{crit.length>1?'s':''}}:</strong><br><br>`;
    crit.forEach(f=>{{
      out+=`• <strong>${{f.resource_id}}</strong> (${{f.type}}, ${{f.region}})<br>`;
      out+=`&nbsp;&nbsp;CPU <strong>${{f.cpu}}%</strong> &bull; ${{this._fmt(f.cost)}}/mo &bull; Save: <strong style="color:#34d399">${{f.saving_text}}</strong><br>`;
      out+=`&nbsp;&nbsp;💡 ${{f.recommendation}}<br><br>`;
    }});
    out+=`<a href="${{GH_URL}}" target="_blank">Track on GitHub →</a>`;
    return out.trim();
  }},

  p1Issues() {{
    const warn=FINDINGS.filter(f=>f.severity==='P1');
    if(!warn.length) return '✅ No P1 warnings in this scan.';
    let out=`⚠️ <strong>${{warn.length}} P1 Warning${{warn.length>1?'s':''}}:</strong><br><br>`;
    warn.forEach(f=>{{
      out+=`• <strong>${{f.resource_id}}</strong> (${{f.type}}) — <strong style="color:#34d399">${{f.saving_text}}</strong><br>`;
      out+=`&nbsp;&nbsp;💡 ${{f.recommendation}}<br>`;
    }});
    return out;
  }},

  fixFirst() {{
    const order={{P0:0,P1:1,P2:2}};
    const sorted=[...FINDINGS].sort((a,b)=>(order[a.severity]||2)-(order[b.severity]||2)||b.saving-a.saving);
    if(!sorted.length) return '✅ No flagged resources — infrastructure is clean!';
    const f=sorted[0];
    const sc=f.severity==='P0'?'#ff6b6b':f.severity==='P1'?'#ffd43b':'#00d4aa';
    let out=`🎯 <strong>Fix This First:</strong><br><br>`;
    out+=`<strong>${{f.resource_id}}</strong> (${{f.type}}, ${{f.region}})<br>`;
    out+=`Severity: <strong style="color:${{sc}}">${{f.severity}}</strong> &bull; Saving: <strong style="color:#34d399">${{f.saving_text}}</strong><br>`;
    out+=`CPU: ${{f.cpu}}% &bull; Cost: ${{this._fmt(f.cost)}}/mo &bull; Idle: ${{f.last_active_days}} days<br><br>`;
    out+=`💡 ${{f.recommendation}}<br><br>`;
    if(sorted.length>1){{
      out+=`Next to fix:<br>`;
      sorted.slice(1,4).forEach(r=>{{
        out+=`• <strong>${{r.resource_id}}</strong> — ${{r.severity}} — ${{r.saving_text}}<br>`;
      }});
    }}
    return out;
  }},

  idle() {{
    const idle=FINDINGS.filter(f=>f.issue_type==='idle'||f.cpu<10);
    if(!idle.length) return '✅ No idle resources detected.';
    let out=`😴 <strong>${{idle.length}} Idle Resource${{idle.length>1?'s':''}}:</strong><br><br>`;
    idle.forEach(f=>{{
      out+=`• <strong>${{f.resource_id}}</strong> — CPU ${{f.cpu}}%, inactive ${{f.last_active_days}} days<br>`;
      out+=`&nbsp;&nbsp;${{this._fmt(f.cost)}}/mo &bull; Save: <strong style="color:#34d399">${{f.saving_text}}</strong><br>`;
    }});
    return out;
  }},

  expensive() {{
    const top=[...RESOURCES].sort((a,b)=>b.cost_monthly_usd-a.cost_monthly_usd).slice(0,5);
    let out=`📈 <strong>Most Expensive Resources:</strong><br><br>`;
    top.forEach((r,i)=>{{
      const fl=FINDINGS.find(f=>f.resource_id===r.resource_id);
      out+=`${{i+1}}. <strong>${{r.resource_id}}</strong> (${{r.type}}) — <strong>${{this._fmt(r.cost_monthly_usd)}}/mo</strong>`;
      if(fl) out+=` <span style="color:#ff6b6b;font-size:0.8em">⚠ ${{fl.severity}}</span>`;
      out+=`<br>`;
    }});
    return out;
  }},

  regions() {{
    const map={{}};
    RESOURCES.forEach(r=>{{map[r.region]=(map[r.region]||0)+r.cost_monthly_usd;}});
    let out=`🌍 <strong>Spend by Region:</strong><br><br>`;
    Object.entries(map).sort((a,b)=>b[1]-a[1]).forEach(([region,cost])=>{{
      out+=`• <strong>${{region}}</strong>: ${{this._fmt(cost)}}/mo<br>`;
    }});
    return out;
  }},

  reduce() {{
    const p0=FINDINGS.filter(f=>f.severity==='P0').length;
    let out=`✂️ <strong>Cost Reduction Roadmap:</strong><br><br>`;
    out+=`1. 🚨 Immediately fix <strong>${{p0}} P0 critical</strong> issues<br>`;
    out+=`2. 📉 Right-size resources with CPU &lt; 10%<br>`;
    out+=`3. 🗑️ Decommission resources idle &gt; 30 days<br>`;
    out+=`4. 📊 Review oversized instances (CPU &lt; 20%, cost &gt; $150)<br>`;
    out+=`5. 🔁 Enable auto-scaling to avoid over-provisioning<br><br>`;
    out+=`Potential: <strong style="color:#34d399">${{this._fmt(TOTAL_SAVING)}}/mo &bull; ${{this._fmt(TOTAL_SAVING*12)}}/yr</strong><br>`;
    out+=`<a href="${{GH_URL}}" target="_blank">Track on GitHub →</a>`;
    return out;
  }},

  forecast() {{
    const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const now=new Date();
    let out=`📅 <strong>6-Month Cost Forecast (without action):</strong><br><br>`;
    let running=TOTAL_COST;
    for(let i=0;i<6;i++){{
      const m=months[(now.getMonth()+i)%12];
      const drift=running*(1+0.02*i);
      out+=`• ${{m}}: <strong>${{this._fmt(drift)}}/mo</strong><br>`;
    }}
    out+=`<br>With full remediation: <strong style="color:#34d399">${{this._fmt(TOTAL_COST-TOTAL_SAVING)}}/mo</strong><br>`;
    out+=`Annual saving vs doing nothing: <strong style="color:#34d399">${{this._fmt(TOTAL_SAVING*12)}}</strong>`;
    return out;
  }},

  resourceInfo(id) {{
    const r=RESOURCES.find(x=>x.resource_id.toLowerCase()===id.toLowerCase());
    const f=FINDINGS.find(x=>x.resource_id.toLowerCase()===id.toLowerCase());
    if(!r) return `❓ Resource <strong>${{id}}</strong> not found. Check the ID.`;
    let out=`🔍 <strong>${{r.resource_id}}</strong><br><br>`;
    out+=`• Type: ${{r.type}} &bull; Region: ${{r.region}}<br>`;
    out+=`• CPU: ${{r.cpu_avg_percent}}% &bull; Memory: ${{r.memory_avg_percent}}%<br>`;
    out+=`• Monthly cost: ${{this._fmt(r.cost_monthly_usd)}} &bull; Last active: ${{r.last_active_days}} days ago<br>`;
    out+=`• Waste score: ${{r.waste_score || 'N/A'}}<br>`;
    if(f){{
      const sc=f.severity==='P0'?'#ff6b6b':f.severity==='P1'?'#ffd43b':'#00d4aa';
      out+=`<br>⚠️ <strong style="color:${{sc}}">Flagged ${{f.severity}}</strong><br>`;
      out+=`Saving: <strong style="color:#34d399">${{f.saving_text}}</strong><br>`;
      out+=`💡 ${{f.recommendation}}`;
    }} else {{
      out+=`<br>✅ Healthy — no issues flagged.`;
    }}
    return out;
  }},

  help() {{
    return `🤖 <strong>Things I can help with:</strong><br><br>`
      +`• <em>summary</em> — full dashboard overview<br>`
      +`• <em>savings</em> — top saving opportunities<br>`
      +`• <em>P0 / P1</em> — issues by severity<br>`
      +`• <em>fix first</em> — priority action list<br>`
      +`• <em>idle</em> — unused resources<br>`
      +`• <em>expensive</em> — cost leaders<br>`
      +`• <em>region</em> — spend by region<br>`
      +`• <em>reduce costs</em> — remediation roadmap<br>`
      +`• <em>forecast</em> — 6-month cost projection<br>`
      +`• Any resource ID (e.g. <code>ec2-web-04</code>)`;
  }},

  unknown() {{
    return `🤔 Not sure about that. Try:<br>`
      +`<em>savings</em>, <em>P0 issues</em>, <em>fix first</em>, <em>forecast</em>, <em>summary</em><br>`
      +`or type a resource ID. Type <strong>help</strong> for all commands.`;
  }},

  process(msg) {{
    const q=msg.toLowerCase().trim();
    for(const r of RESOURCES) {{
      if(q.includes(r.resource_id.toLowerCase())) return this.resourceInfo(r.resource_id);
    }}
    if(/^(hi|hello|hey|yo)\b/.test(q))                               return this.greet();
    if(/help|what can|commands/.test(q))                              return this.help();
    if(/summar|overview|full report/.test(q))                         return this.summary();
    if(/saving|save|how much|recoverable|opportunit/.test(q))         return this.savings();
    if(/p0|critical|urgent|emergency/.test(q))                        return this.p0Issues();
    if(/p1|warning|medium/.test(q))                                   return this.p1Issues();
    if(/fix|first|priorit|start|action|roadmap/.test(q))             return this.fixFirst();
    if(/idle|unused|inactive|stale/.test(q))                          return this.idle();
    if(/expens|highest cost|most cost|priciest/.test(q))              return this.expensive();
    if(/region|location/.test(q))                                     return this.regions();
    if(/reduc|cut cost|lower|optimiz/.test(q))                        return this.reduce();
    if(/forecast|predict|project|future/.test(q))                     return this.forecast();
    return this.unknown();
  }}
}};

// ── Chat UI helpers ─────────────────────────────────────────────────────────
const msgsEl  = document.getElementById('chat-messages');
const inputEl = document.getElementById('chat-textarea');
const sendBtn = document.getElementById('chat-send-btn');

function now12() {{
  return new Date().toLocaleTimeString('en-US',{{hour:'numeric',minute:'2-digit'}});
}}

function appendMsg(html, role) {{
  const wrap   = document.createElement('div');
  wrap.className = 'msg ' + role;
  const av = document.createElement('div');
  av.className = 'msg-avatar';
  av.textContent = role === 'bot' ? '🤖' : '👤';
  const right = document.createElement('div');
  right.style.display='flex';right.style.flexDirection='column';right.style.gap='3px';
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = html;
  const time = document.createElement('div');
  time.className='msg-time';
  time.textContent = now12();
  right.appendChild(bubble);
  right.appendChild(time);
  if(role==='user') {{ wrap.appendChild(right); wrap.appendChild(av); }}
  else              {{ wrap.appendChild(av);   wrap.appendChild(right); }}
  msgsEl.appendChild(wrap);
  msgsEl.scrollTop = msgsEl.scrollHeight;
  return wrap;
}}

function showTyping() {{
  const wrap = document.createElement('div');
  wrap.className='msg bot'; wrap.id='typing-row';
  const av=document.createElement('div'); av.className='msg-avatar'; av.textContent='🤖';
  const bub=document.createElement('div'); bub.className='msg-bubble';
  bub.innerHTML='<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
  wrap.appendChild(av); wrap.appendChild(bub);
  msgsEl.appendChild(wrap);
  msgsEl.scrollTop=msgsEl.scrollHeight;
}}

function removeTyping() {{
  const el=document.getElementById('typing-row');
  if(el) el.remove();
}}

async function sendMessage() {{
  const text=inputEl.value.trim();
  if(!text) return;
  inputEl.value=''; inputEl.style.height='auto';
  appendMsg(text,'user');
  showTyping(); sendBtn.disabled=true;

  try {{
    const r=await fetch('/chat',{{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{question:text}}),
      signal:AbortSignal.timeout(4000),
    }});
    if(r.ok){{
      const d=await r.json();
      removeTyping(); appendMsg(d.answer||Bot.process(text),'bot');
      sendBtn.disabled=false; return;
    }}
  }} catch(_) {{}}

  setTimeout(()=>{{
    removeTyping(); appendMsg(Bot.process(text),'bot');
    sendBtn.disabled=false;
  }}, 500+Math.random()*400);
}}

sendBtn.addEventListener('click', sendMessage);
inputEl.addEventListener('keydown', e=>{{
  if(e.key==='Enter'&&!e.shiftKey){{ e.preventDefault(); sendMessage(); }}
}});
inputEl.addEventListener('input', ()=>{{
  inputEl.style.height='auto';
  inputEl.style.height=Math.min(inputEl.scrollHeight,110)+'px';
}});
document.getElementById('chip-grid').addEventListener('click', e=>{{
  const chip=e.target.closest('.q-chip');
  if(!chip) return;
  inputEl.value=chip.dataset.q;
  sendMessage();
}});

// Pre-load greeting immediately
appendMsg(Bot.greet(),'bot');

// ── Auto-refresh ─────────────────────────────────────────────────────────────
const cntEl=document.getElementById('refresh-countdown');
const luEl=document.getElementById('last-updated');
let secs=30;
function tick(){{
  cntEl.textContent=secs; luEl.textContent=new Date().toLocaleTimeString();
  if(secs<=0) location.reload(); else secs--;
}}
tick(); setInterval(tick,1000);
</script>
</body>
</html>"""

    def _resource_table_row(self, resource: Dict[str, Any], findings: List[Dict[str, Any]]) -> str:
        flagged = any(e["resource"]["resource_id"] == resource["resource_id"] for e in findings)
        finding = next((e for e in findings if e["resource"]["resource_id"] == resource["resource_id"]), None)
        color = "#fb7185" if flagged else "#34d399"
        status = "⚠ Flagged" if flagged else "✓ Healthy"
        waste = resource.get("waste_score", 0)
        waste_color = "#ff6b6b" if waste > 70 else "#ffd43b" if waste > 40 else "#34d399"
        sev = ""
        if finding:
            sev_raw = finding.get("analysis", {}).get("severity", finding.get("severity", ""))
            sev_color_map = {"P0": "#ff6b6b", "P1": "#ffd43b", "P2": "#00d4aa"}
            sev_col = sev_color_map.get(sev_raw, "#94a3b8")
            sev = f' <span style="color:{sev_col};font-size:0.75rem;font-weight:700;">{sev_raw}</span>'
        return (
            f'<tr data-status="{"flagged" if flagged else "healthy"}">'
            f"<td style='font-weight:600;'>{resource['resource_id']}{sev}</td>"
            f"<td>{resource['type']}</td>"
            f"<td>{resource['cpu_avg_percent']}%</td>"
            f"<td>${resource.get('cost_monthly_usd', 0.0):,.2f}</td>"
            f"<td style='color:{color};font-weight:700;'>{status}</td>"
            f"<td><div style='display:flex;align-items:center;gap:8px;'>"
            f"<div style='flex:1;height:6px;background:rgba(148,163,184,.1);border-radius:999px;overflow:hidden;'>"
            f"<div style='height:100%;width:{waste}%;background:{waste_color};border-radius:999px;'></div>"
            f"</div><span style='font-size:0.78rem;color:{waste_color};font-weight:700;'>{waste}</span></div></td>"
            f"</tr>"
        )

    def _get_training_info(self, output_dir: str) -> Dict[str, Any]:
        training_path = Path(output_dir) / "ai_training_dataset.jsonl"
        if not training_path.exists():
            return {"count": 0, "timestamp": "Never generated", "note": ""}
        count = sum(1 for _ in training_path.open("r", encoding="utf-8"))
        ts = datetime.fromtimestamp(training_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return {"count": count, "timestamp": ts, "note": "Available for fine-tuning."}

    def _donut_segment_svg(self, segment: Dict[str, Any]) -> str:
        return (
            f"<circle cx='130' cy='130' r='88' fill='none' stroke='{segment['color']}' stroke-width='44' "
            f"stroke-dasharray='{segment['dasharray']}' stroke-dashoffset='-{segment['offset']}' transform='rotate(-90 130 130)'/>"
        )

    def _donut_legend_html(self, segment: Dict[str, Any]) -> str:
        return (
            f"<div class='legend-item'><span class='legend-color' style='background:{segment['color']};'></span>"
            f"<span>{segment['severity']}: <strong>${segment['value']:,.0f}</strong> ({segment['percent']}%)</span></div>"
        )
