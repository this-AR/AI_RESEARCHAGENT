from datetime import datetime
from unittest import TestCase

from ai_research_agent.schemas import (
    CompanyProfile,
    EmailCampaign,
    EmailMessage,
    EvidenceClaim,
    EvidenceStatus,
    LeadScore,
    LeadScoreFactor,
    QualityReport,
    ResearchRun,
    ResearchSource,
)


class ResearchSourceTests(TestCase):
    def test_valid_source(self) -> None:
        source = ResearchSource(url="https://example.com", title="Example")
        self.assertEqual(source.provider, "")
        self.assertIsInstance(source.retrieved_at, datetime)


class EvidenceClaimTests(TestCase):
    def test_defaults_to_inferred(self) -> None:
        claim = EvidenceClaim(claim="AI adoption is rising.")
        self.assertEqual(claim.status, EvidenceStatus.inferred)
        self.assertEqual(claim.confidence, 0.5)

    def test_strips_claim(self) -> None:
        claim = EvidenceClaim(claim="  spaced  ")
        self.assertEqual(claim.claim, "spaced")


class CompanyProfileTests(TestCase):
    def test_empty_profile_valid(self) -> None:
        profile = CompanyProfile(company_name="Acme")
        self.assertEqual(profile.recent_developments, [])


class LeadScoreTests(TestCase):
    def test_from_factors_calculates_total(self) -> None:
        factors = [
            LeadScoreFactor(name="A", score=15, max_score=20),
            LeadScoreFactor(name="B", score=10, max_score=20),
        ]
        score = LeadScore.from_factors(factors)
        self.assertEqual(score.total, 25)
        self.assertEqual(len(score.factors), 2)

    def test_from_factors_caps_at_100(self) -> None:
        factors = [LeadScoreFactor(name=f"F{i}", score=20, max_score=20) for i in range(6)]
        score = LeadScore.from_factors(factors)
        self.assertEqual(score.total, 100)


class EmailCampaignTests(TestCase):
    def test_campaign_serializes(self) -> None:
        campaign = EmailCampaign(
            target_company="Acme",
            emails=[EmailMessage(subject="Hi", body="Hello")],
        )
        data = campaign.model_dump()
        self.assertEqual(data["target_company"], "Acme")
        self.assertEqual(len(data["emails"]), 1)


class QualityReportTests(TestCase):
    def test_default_not_passed(self) -> None:
        report = QualityReport()
        self.assertFalse(report.passed)


class ResearchRunTests(TestCase):
    def test_generates_run_id(self) -> None:
        run = ResearchRun()
        self.assertTrue(run.run_id)
        self.assertIsInstance(run.created_at, datetime)
