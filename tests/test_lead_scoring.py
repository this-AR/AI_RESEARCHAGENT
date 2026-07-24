from datetime import datetime, timezone
from unittest import TestCase

from ai_research_agent.lead_scoring import score_lead
from ai_research_agent.schemas import (
    CompanyProfile,
    DecisionMaker,
    EvidenceClaim,
    EvidenceStatus,
    ResearchSource,
)


class LeadScoringTests(TestCase):
    def test_empty_profile_scores_zero(self) -> None:
        profile = CompanyProfile(company_name="Acme")
        score = score_lead(profile)
        self.assertEqual(score.total, 0)
        self.assertTrue(any(f.evidence_missing for f in score.factors))

    def test_full_evidence_scores_high(self) -> None:
        now = datetime.now(timezone.utc)
        profile = CompanyProfile(
            company_name="Acme",
            industry="Technology",
            market_position="Market leader",
            recent_developments=[
                EvidenceClaim(
                    claim="Launched new product",
                    status=EvidenceStatus.verified,
                    retrieved_at=now,
                    confidence=0.9,
                ),
                EvidenceClaim(
                    claim="Opened new office",
                    status=EvidenceStatus.verified,
                    retrieved_at=now,
                    confidence=0.8,
                ),
            ],
            pain_points=[
                EvidenceClaim(
                    claim="High churn rate",
                    status=EvidenceStatus.verified,
                    retrieved_at=now,
                    confidence=0.85,
                ),
            ],
            opportunities=[
                EvidenceClaim(
                    claim="Expansion into Asia",
                    status=EvidenceStatus.inferred,
                    retrieved_at=now,
                ),
            ],
            sources=[
                ResearchSource(url="https://example.com", title="News", provider="DDG"),
                ResearchSource(url="https://other.com", title="Blog", provider="DDG"),
            ],
        )
        dm = DecisionMaker(
            name="Alice Smith",
            position="CEO",
            evidence=[
                EvidenceClaim(
                    claim="Listed as CEO on company website",
                    status=EvidenceStatus.verified,
                    retrieved_at=now,
                    confidence=0.95,
                ),
            ],
            confidence=0.95,
        )
        score = score_lead(profile, dm)
        self.assertGreater(score.total, 60)
        self.assertFalse(any(f.evidence_missing for f in score.factors))

    def test_missing_dm_flagged(self) -> None:
        profile = CompanyProfile(
            company_name="Acme",
            industry="Tech",
            market_position="Leader",
            sources=[ResearchSource(url="https://example.com", title="X", provider="DDG")],
        )
        score = score_lead(profile, None)
        dm_factor = next(f for f in score.factors if f.name == "Decision-Maker Confidence")
        self.assertTrue(dm_factor.evidence_missing)

    def test_score_summary_includes_missing_count(self) -> None:
        profile = CompanyProfile(company_name="Acme")
        score = score_lead(profile)
        self.assertIn("factor(s) lack evidence", score.summary)
