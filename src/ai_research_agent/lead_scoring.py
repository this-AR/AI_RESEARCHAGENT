"""Explainable lead scoring engine.

Scoring is deterministic and testable: it depends only on the evidence present
in a CompanyProfile and DecisionMaker.  Missing evidence is treated differently
from negative evidence so callers can distinguish "don't know" from "no fit".
"""

from __future__ import annotations

from datetime import datetime, timezone

from .schemas import (
    CompanyProfile,
    DecisionMaker,
    EvidenceClaim,
    EvidenceStatus,
    LeadScore,
    LeadScoreFactor,
)


def _has_verified_claim(evidence: list[EvidenceClaim]) -> bool:
    return any(c.status == EvidenceStatus.verified for c in evidence)


def _count_recent_evidence(evidence: list[EvidenceClaim], days: int = 90) -> int:
    now = datetime.now(timezone.utc)
    count = 0
    for claim in evidence:
        if claim.retrieved_at is None:
            continue
        try:
            delta = now - claim.retrieved_at
            if delta.days <= days:
                count += 1
        except Exception:
            pass
    return count


def _freshness_score(sources_count: int, recent_evidence_count: int) -> tuple[int, bool]:
    """Return (score, evidence_missing)."""
    if sources_count == 0:
        return 0, True
    if recent_evidence_count >= 3:
        return 20, False
    if recent_evidence_count >= 1:
        return 12, False
    return 5, False


def _company_fit_score(profile: CompanyProfile) -> tuple[int, bool, str]:
    """Score based on market position clarity and industry specificity."""
    missing = not (profile.market_position.strip() or profile.industry.strip())
    if missing:
        return 0, True, "No market position or industry information available."
    score = 10
    explanation = f"Industry '{profile.industry}' and market position described."
    if len(profile.recent_developments) >= 2:
        score += 5
        explanation += " Multiple recent developments noted."
    if len(profile.opportunities) >= 1:
        score += 5
        explanation += " Opportunities identified."
    return min(score, 20), False, explanation


def _recent_activity_score(profile: CompanyProfile) -> tuple[int, bool, str]:
    """Score based on volume and recency of recent developments."""
    if not profile.recent_developments:
        return 0, True, "No recent developments recorded."
    recent = _count_recent_evidence(profile.recent_developments)
    verified = _has_verified_claim(profile.recent_developments)
    if verified and recent >= 2:
        return 20, False, f"{recent} recent verified development(s)."
    if verified:
        return 15, False, "At least one verified recent development."
    return 10, False, f"{len(profile.recent_developments)} development(s) but limited verification."


def _decision_maker_score(decision_maker: DecisionMaker | None) -> tuple[int, bool, str]:
    if decision_maker is None or not decision_maker.name.strip():
        return 0, True, "No decision-maker information provided."
    score = 8
    explanation = f"Named contact: {decision_maker.name}"
    if decision_maker.position.strip():
        score += 4
        explanation += f" ({decision_maker.position})"
    if decision_maker.evidence:
        verified = _has_verified_claim(decision_maker.evidence)
        if verified:
            score += 8
            explanation += " with verified role evidence."
        else:
            score += 4
            explanation += " with some role evidence."
    return min(score, 20), False, explanation


def _pain_point_score(profile: CompanyProfile) -> tuple[int, bool, str]:
    if not profile.pain_points:
        return 0, True, "No pain-point evidence collected."
    verified = _has_verified_claim(profile.pain_points)
    count = len(profile.pain_points)
    if verified and count >= 2:
        return 20, False, f"{count} pain points with verified sources."
    if verified:
        return 15, False, "At least one verified pain point."
    return 10, False, f"{count} pain point(s) but not verified."


def score_lead(profile: CompanyProfile, decision_maker: DecisionMaker | None = None) -> LeadScore:
    """Produce an explainable 0-100 lead score from structured evidence.

    Parameters
    ----------
    profile:
        The researched company profile.
    decision_maker:
        Optional decision-maker profile.

    Returns
    -------
    LeadScore
        Total score and a per-factor breakdown.
    """
    factors: list[LeadScoreFactor] = []

    company_score, company_missing, company_explanation = _company_fit_score(profile)
    factors.append(
        LeadScoreFactor(
            name="Company Fit",
            score=company_score,
            max_score=20,
            explanation=company_explanation,
            evidence_missing=company_missing,
        )
    )

    activity_score, activity_missing, activity_explanation = _recent_activity_score(profile)
    factors.append(
        LeadScoreFactor(
            name="Recent Activity",
            score=activity_score,
            max_score=20,
            explanation=activity_explanation,
            evidence_missing=activity_missing,
        )
    )

    dm_score, dm_missing, dm_explanation = _decision_maker_score(decision_maker)
    factors.append(
        LeadScoreFactor(
            name="Decision-Maker Confidence",
            score=dm_score,
            max_score=20,
            explanation=dm_explanation,
            evidence_missing=dm_missing,
        )
    )

    pain_score, pain_missing, pain_explanation = _pain_point_score(profile)
    factors.append(
        LeadScoreFactor(
            name="Pain-Point Evidence",
            score=pain_score,
            max_score=20,
            explanation=pain_explanation,
            evidence_missing=pain_missing,
        )
    )

    freshness_score, freshness_missing = _freshness_score(
        len(profile.sources),
        _count_recent_evidence(profile.recent_developments),
    )
    factors.append(
        LeadScoreFactor(
            name="Data Freshness",
            score=freshness_score,
            max_score=20,
            explanation="Based on source count and recency of evidence." if not freshness_missing else "No sources available.",
            evidence_missing=freshness_missing,
        )
    )

    missing_factors = sum(1 for f in factors if f.evidence_missing)
    summary = f"Lead score: {sum(f.score for f in factors)}/100. {missing_factors} factor(s) lack evidence."

    return LeadScore.from_factors(factors, summary=summary)
