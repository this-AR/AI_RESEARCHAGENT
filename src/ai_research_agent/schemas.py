"""Structured, evidence-grounded output schemas.

All models use Pydantic so CrewAI agents can be asked to return typed output
instead of free-text "JSON-like" strings.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EvidenceStatus(str, Enum):
    verified = "verified"
    inferred = "inferred"
    unsupported = "unsupported"


class ResearchSource(BaseModel):
    """A single web source used during research."""

    url: str
    title: str = Field(..., min_length=1)
    snippet: str = ""
    provider: str = Field(default="", min_length=1, description="Search provider name, e.g. DuckDuckGo")
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        return value.strip()


class EvidenceClaim(BaseModel):
    """A factual claim with provenance and confidence."""

    claim: str = Field(..., min_length=1)
    source_url: str | None = None
    retrieved_at: datetime | None = None
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    status: EvidenceStatus = EvidenceStatus.inferred

    @field_validator("claim")
    @classmethod
    def _strip_claim(cls, value: str) -> str:
        return value.strip()


class DecisionMaker(BaseModel):
    """Profile of a target contact."""

    name: str = Field(..., min_length=1)
    position: str = ""
    evidence: list[EvidenceClaim] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class CompanyProfile(BaseModel):
    """Aggregated company intelligence."""

    company_name: str = Field(..., min_length=1)
    industry: str = ""
    market_position: str = ""
    recent_developments: list[EvidenceClaim] = Field(default_factory=list)
    pain_points: list[EvidenceClaim] = Field(default_factory=list)
    opportunities: list[EvidenceClaim] = Field(default_factory=list)
    risks: list[EvidenceClaim] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)


class LeadScoreFactor(BaseModel):
    """One dimension of the lead score with explanation."""

    name: str = Field(..., min_length=1)
    score: int = Field(..., ge=0, le=20)
    max_score: int = Field(20, ge=1, le=20)
    explanation: str = ""
    evidence_missing: bool = False


class LeadScore(BaseModel):
    """Explainable lead qualification score."""

    total: int = Field(..., ge=0, le=100)
    factors: list[LeadScoreFactor] = Field(default_factory=list)
    summary: str = ""

    @field_validator("factors")
    @classmethod
    def _total_matches_factors(cls, factors: list[LeadScoreFactor], info: Any) -> list[LeadScoreFactor]:
        # Pydantic v2 validator signature: second arg is ValidationInfo.
        calculated = sum(f.score for f in factors)
        if factors and hasattr(info, "data") and "total" in info.data and calculated != info.data["total"]:
            raise ValueError(f"Sum of factor scores ({calculated}) does not match total score ({info.data['total']})")
        return factors

    @classmethod
    def from_factors(cls, factors: list[LeadScoreFactor], summary: str = "") -> LeadScore:
        total = sum(f.score for f in factors)
        if total > 100:
            scale = 100 / total
            for f in factors:
                f.score = int(f.score * scale)
            # distribute any remaining points to the largest factor to ensure sum is exactly 100
            new_total = sum(f.score for f in factors)
            if new_total < 100 and factors:
                largest = max(factors, key=lambda f: f.score)
                largest.score += (100 - new_total)
            total = 100
        return cls(total=total, factors=factors, summary=summary)


class EmailMessage(BaseModel):
    """A single outreach message."""

    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    call_to_action: str = ""
    suggested_timing: str = ""
    personalization_evidence: list[EvidenceClaim] = Field(default_factory=list)


class EmailCampaign(BaseModel):
    """A sequence of outreach messages."""

    target_company: str = ""
    target_contact: str = ""
    emails: list[EmailMessage] = Field(default_factory=list)


class QualityReport(BaseModel):
    """QA findings for a research run."""

    passed: bool = False
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    tone_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ResearchRun(BaseModel):
    """Top-level container for a completed research workflow."""

    target: dict[str, str] = Field(default_factory=dict)
    company_profile: CompanyProfile | None = None
    decision_maker: DecisionMaker | None = None
    lead_score: LeadScore | None = None
    campaign: EmailCampaign | None = None
    quality: QualityReport | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
