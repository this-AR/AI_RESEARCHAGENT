"""Export helpers for research results.

Supports JSON, Markdown, and CSV serialisation of a ResearchRun so it can be
consumed by downstream tools, reviewed by humans, or imported into a CRM.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .schemas import EmailCampaign, LeadScore, ResearchRun


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def export_json(run: ResearchRun, path: Path | str) -> Path:
    """Write a ResearchRun as indented JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = run.model_dump(mode="json")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _md_heading(text: str, level: int = 1) -> str:
    return f"{'#' * level} {text}\n"


def _md_bullet(text: str) -> str:
    return f"- {text}\n"


def _claim_row(claim: Any) -> str:
    status = getattr(claim, "status", "inferred")
    conf = getattr(claim, "confidence", 0.5)
    url = getattr(claim, "source_url", None)
    url_md = f" [{url}]({url})" if url else ""
    return f"- **{status}** (confidence {conf}): {claim.claim}{url_md}\n"


def export_markdown(run: ResearchRun, path: Path | str) -> Path:
    """Write a human-readable Markdown report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(_md_heading("AI Research Agent Report", 1))
    lines.append(f"**Run ID:** {run.run_id}  \n")
    lines.append(f"**Created:** {run.created_at.isoformat()}  \n\n")

    # Target
    if run.target:
        lines.append(_md_heading("Target", 2))
        for k, v in run.target.items():
            lines.append(_md_bullet(f"{k.replace('_', ' ').title()}: {v}"))
        lines.append("\n")

    # Company Profile
    if run.company_profile:
        cp = run.company_profile
        lines.append(_md_heading("Company Profile", 2))
        lines.append(_md_bullet(f"Name: {cp.company_name}"))
        if cp.industry:
            lines.append(_md_bullet(f"Industry: {cp.industry}"))
        if cp.market_position:
            lines.append(_md_bullet(f"Market Position: {cp.market_position}"))

        if cp.recent_developments:
            lines.append(_md_heading("Recent Developments", 3))
            for dev in cp.recent_developments:
                lines.append(_claim_row(dev))

        if cp.pain_points:
            lines.append(_md_heading("Pain Points", 3))
            for pt in cp.pain_points:
                lines.append(_claim_row(pt))

        if cp.opportunities:
            lines.append(_md_heading("Opportunities", 3))
            for opp in cp.opportunities:
                lines.append(_claim_row(opp))

        if cp.sources:
            lines.append(_md_heading("Sources", 3))
            for src in cp.sources:
                lines.append(f"- [{src.title}]({src.url}) — {src.provider}\n")
        lines.append("\n")

    # Decision Maker
    if run.decision_maker:
        dm = run.decision_maker
        lines.append(_md_heading("Decision Maker", 2))
        lines.append(_md_bullet(f"Name: {dm.name}"))
        if dm.position:
            lines.append(_md_bullet(f"Position: {dm.position}"))
        lines.append(_md_bullet(f"Confidence: {dm.confidence}"))
        if dm.evidence:
            lines.append(_md_heading("Evidence", 3))
            for ev in dm.evidence:
                lines.append(_claim_row(ev))
        lines.append("\n")

    # Lead Score
    if run.lead_score:
        ls = run.lead_score
        lines.append(_md_heading("Lead Score", 2))
        lines.append(f"**Total:** {ls.total} / 100  \n")
        lines.append(f"*{ls.summary}*  \n\n")
        for factor in ls.factors:
            flag = " ⚠️ missing evidence" if factor.evidence_missing else ""
            lines.append(_md_bullet(f"{factor.name}: {factor.score}/{factor.max_score} — {factor.explanation}{flag}"))
        lines.append("\n")

    # Email Campaign
    if run.campaign:
        lines.append(_md_heading("Email Campaign", 2))
        for idx, email in enumerate(run.campaign.emails, start=1):
            lines.append(_md_heading(f"Message {idx}", 3))
            lines.append(f"**Subject:** {email.subject}  \n")
            lines.append(f"**Timing:** {email.suggested_timing}  \n")
            lines.append(f"**CTA:** {email.call_to_action}  \n\n")
            lines.append(email.body)
            lines.append("\n\n")

    # Quality Report
    if run.quality:
        qr = run.quality
        lines.append(_md_heading("Quality Report", 2))
        lines.append(_md_bullet(f"Passed: {'Yes' if qr.passed else 'No'}"))
        if qr.unsupported_claims:
            lines.append(_md_heading("Unsupported Claims", 3))
            for c in qr.unsupported_claims:
                lines.append(_md_bullet(c))
        if qr.missing_evidence:
            lines.append(_md_heading("Missing Evidence", 3))
            for m in qr.missing_evidence:
                lines.append(_md_bullet(m))
        if qr.recommendations:
            lines.append(_md_heading("Recommendations", 3))
            for r in qr.recommendations:
                lines.append(_md_bullet(r))
        lines.append("\n")

    path.write_text("".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def _lead_score_rows(run: ResearchRun) -> list[dict[str, Any]]:
    """Flatten a ResearchRun into CRM-friendly rows."""
    rows: list[dict[str, Any]] = []
    if not run.campaign:
        return rows

    base = {
        "run_id": run.run_id,
        "company_name": run.target.get("company_name", ""),
        "industry": run.target.get("industry", ""),
        "decision_maker": run.target.get("key_decision_maker", ""),
        "position": run.target.get("position", ""),
        "lead_score_total": run.lead_score.total if run.lead_score else "",
    }

    for idx, email in enumerate(run.campaign.emails, start=1):
        row = {
            **base,
            "message_number": idx,
            "subject": email.subject,
            "body": email.body,
            "call_to_action": email.call_to_action,
            "suggested_timing": email.suggested_timing,
        }
        rows.append(row)
    return rows


def export_csv(runs: list[ResearchRun], path: Path | str) -> Path:
    """Write a list of ResearchRuns as a single CSV file.

    Each email message becomes its own row so the file is easy to import into
    a spreadsheet or CRM.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "run_id",
        "company_name",
        "industry",
        "decision_maker",
        "position",
        "lead_score_total",
        "message_number",
        "subject",
        "body",
        "call_to_action",
        "suggested_timing",
    ]

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for run in runs:
            for row in _lead_score_rows(run):
                writer.writerow(row)

    return path
