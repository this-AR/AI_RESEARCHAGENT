"""Live evaluation over a target dataset, scored with automatic metrics.

Metrics are computed from the structured outputs only; there is no manually
reviewed ground truth, and QA fields are the quality agent's own judgement.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import WorkflowError
from .lead_scoring import score_lead
from .models import ResearchTarget

LOGGER = logging.getLogger(__name__)
_LINK = re.compile(r"\]\((https?://[^)\s]+)\)")


def score_outputs(outputs: dict[str, Any]) -> dict[str, Any]:
    """Compute metrics from the structured outputs returned by run_research."""
    profile = outputs.get("company_profile")
    campaign = outputs.get("campaign")
    quality = outputs.get("quality")
    emails = campaign.emails if campaign else []

    known_urls: set[str] = set()
    if profile:
        known_urls = {s.url.rstrip("/") for s in profile.sources}
        for claims in (profile.recent_developments, profile.pain_points, profile.opportunities, profile.risks):
            known_urls.update(c.source_url.rstrip("/") for c in claims if c.source_url)
    links = [url.rstrip("/") for e in emails for url in _LINK.findall(e.body)]
    usage = getattr(outputs.get("raw_result"), "token_usage", None)

    return {
        "schema_valid": bool(profile and campaign and quality) and len(emails) == 4,
        "emails": len(emails),
        "sources": len(profile.sources) if profile else 0,
        # Share of emails that cite at least one source link.
        "citation_coverage": sum(bool(_LINK.search(e.body)) for e in emails) / len(emails) if emails else 0.0,
        # Share of cited links that point at a URL the research step actually found.
        "grounded_link_rate": sum(u in known_urls for u in links) / len(links) if links else None,
        "qa_passed": bool(quality and quality.passed),
        "unsupported_claims": len(quality.unsupported_claims) if quality else None,
        "lead_score": score_lead(profile).total if profile else None,
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Rates count failed runs as failures; averages use completed runs only."""
    done = [r for r in rows if r["ok"]]

    def rate(key: str) -> float | None:
        return round(sum(bool(r.get(key)) for r in rows) / len(rows), 3) if rows else None

    def mean(key: str, source: list[dict[str, Any]]) -> float | None:
        values = [r[key] for r in source if r.get(key) is not None]
        return round(sum(values) / len(values), 3) if values else None

    return {
        "runs": len(rows),
        "completed": len(done),
        "schema_valid_rate": rate("schema_valid"),
        "qa_pass_rate": rate("qa_passed"),
        "mean_citation_coverage": mean("citation_coverage", done),
        "mean_grounded_link_rate": mean("grounded_link_rate", done),
        "mean_unsupported_claims": mean("unsupported_claims", done),
        "mean_lead_score": mean("lead_score", done),
        "mean_latency_s": mean("latency_s", rows),
        "total_tokens": sum(r.get("total_tokens") or 0 for r in done),
    }


def run_eval(
    targets: list[ResearchTarget], settings: Settings, output_dir: Path
) -> tuple[dict[str, Any], Path]:
    """Run each target live, keep going past failed runs, and write eval_report.json."""
    from .workflow import run_research

    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for index, target in enumerate(targets, 1):
        LOGGER.info("Evaluating %s (%s/%s)", target.company_name, index, len(targets))
        slug = re.sub(r"[^a-z0-9]+", "-", target.company_name.lower()).strip("-")
        row: dict[str, Any] = {"company": target.company_name}
        started = time.monotonic()
        try:
            outputs, path = run_research(target, settings, output_path=output_dir / f"{slug}.md")
            row.update(ok=True, result=str(path), **score_outputs(outputs))
        except WorkflowError as exc:
            row.update(ok=False, error=str(exc))
        row["latency_s"] = round(time.monotonic() - started, 1)
        rows.append(row)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.litellm_model,
        "summary": summarize(rows),
        "runs": rows,
    }
    report_path = output_dir / "eval_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report, report_path
