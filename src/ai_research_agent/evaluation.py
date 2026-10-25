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
from .schemas import EmailCampaign, ResearchRun

LOGGER = logging.getLogger(__name__)
_LINK = re.compile(r"\]\((https?://[^)\s]+)\)")


def _canonical(url: str) -> str:
    return url.strip().rstrip("/")


def cited_urls(campaign: EmailCampaign) -> list[str]:
    """Every URL an email cites, inline or in personalization_evidence, canonicalized."""
    inline = [url for e in campaign.emails for url in _LINK.findall(e.body)]
    evidence = [c.source_url for e in campaign.emails for c in e.personalization_evidence if c.source_url]
    return [_canonical(url) for url in inline + evidence]


def check_campaign(campaign: Any, retrieved_urls: set[str]) -> str | None:
    """Return feedback for the agent if the final campaign breaks a hard rule, else None."""
    if not isinstance(campaign, EmailCampaign):
        return "Return a structured EmailCampaign."
    if len(campaign.emails) != 4:
        return f"Return exactly four emails; you returned {len(campaign.emails)}."
    allowed = {_canonical(url) for url in retrieved_urls}
    # crewai retries a guardrail with only this feedback as context, so it must carry the URLs.
    sources = (
        f" Cite only these retrieved URLs, exactly as written: {sorted(allowed)[:20]}."
        " Remove any claim you cannot support with one of them."
    )
    unlinked = [i for i, e in enumerate(campaign.emails, 1) if not _LINK.search(e.body)]
    if unlinked:
        return f"Emails {unlinked} have no inline [Source](url) link in the body. Add one per factual claim." + sources
    ungrounded = sorted({url for url in cited_urls(campaign) if url not in allowed})
    if ungrounded:
        return f"These cited URLs were never returned by web search: {ungrounded}." + sources
    return None


def score_outputs(outputs: dict[str, Any]) -> dict[str, Any]:
    """Compute metrics from the structured outputs returned by run_research."""
    profile = outputs.get("company_profile")
    campaign = outputs.get("campaign")
    quality = outputs.get("quality")
    emails = campaign.emails if campaign else []

    retrieved = {_canonical(url) for url in outputs.get("retrieved_urls", set())}
    cited = cited_urls(campaign) if campaign else []
    usage = getattr(outputs.get("raw_result"), "token_usage", None)

    return {
        "schema_valid": bool(profile and campaign and quality) and len(emails) == 4,
        "emails": len(emails),
        "sources": len(profile.sources) if profile else 0,
        # Share of emails with an inline source link in the body, as the email task requires.
        "citation_coverage": sum(bool(_LINK.search(e.body)) for e in emails) / len(emails) if emails else 0.0,
        # Share of emails citing a source in the structured personalization_evidence field.
        "evidence_coverage": (
            sum(any(c.source_url for c in e.personalization_evidence) for e in emails) / len(emails)
            if emails else 0.0
        ),
        # Share of all cited URLs (inline or evidence) that web search actually returned this run.
        "grounded_link_rate": sum(u in retrieved for u in cited) / len(cited) if cited else None,
        # The QA agent reviews the draft before the final rewrite, not the delivered emails.
        "draft_qa_passed": bool(quality and quality.passed),
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
        "draft_qa_pass_rate": rate("draft_qa_passed"),
        "mean_citation_coverage": mean("citation_coverage", done),
        "mean_evidence_coverage": mean("evidence_coverage", done),
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
            row.update(ok=True, result=str(path), model=outputs["model"], **score_outputs(outputs))
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


def rescore(report_dir: Path) -> dict[str, Any]:
    """Re-score the saved ResearchRun artifacts in an eval directory, with no API calls.

    Failed runs leave no artifact, so rates here cover completed runs only.
    """
    rows: list[dict[str, Any]] = []
    for path in sorted(report_dir.glob("*.json")):
        if path.name == "eval_report.json":
            continue
        run = ResearchRun.model_validate_json(path.read_text(encoding="utf-8"))
        outputs = {
            "company_profile": run.company_profile,
            "campaign": run.campaign,
            "quality": run.quality,
            "retrieved_urls": set(run.retrieved_urls),
        }
        row = {"company": run.target.get("company_name", path.stem), "ok": True, "model": run.model}
        row.update(score_outputs(outputs), total_tokens=run.token_usage.get("total_tokens"))
        rows.append(row)
    return summarize(rows)
