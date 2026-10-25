from types import SimpleNamespace
from unittest import TestCase

from ai_research_agent.evaluation import score_outputs, summarize
from ai_research_agent.schemas import (
    CompanyProfile,
    EmailCampaign,
    EmailMessage,
    QualityReport,
    ResearchSource,
)


def _email(body: str) -> EmailMessage:
    return EmailMessage(subject="Hi", body=body)


class ScoreOutputsTests(TestCase):
    def test_measures_citations_and_grounding(self) -> None:
        profile = CompanyProfile(
            company_name="Acme",
            sources=[ResearchSource(url="https://acme.com/news/", title="News", provider="test")],
        )
        campaign = EmailCampaign(
            emails=[
                _email("Congrats [Source](https://acme.com/news)"),  # grounded despite slash
                _email("Saw this [Source](https://made-up.example)"),  # not a researched URL
                _email("No link here"),
                _email("Also none"),
            ]
        )
        outputs = {
            "company_profile": profile,
            "campaign": campaign,
            "quality": QualityReport(passed=False, unsupported_claims=["x"]),
            "raw_result": SimpleNamespace(token_usage=SimpleNamespace(total_tokens=1234)),
        }

        metrics = score_outputs(outputs)

        self.assertTrue(metrics["schema_valid"])
        self.assertEqual(metrics["citation_coverage"], 0.5)
        self.assertEqual(metrics["grounded_link_rate"], 0.5)
        self.assertFalse(metrics["qa_passed"])
        self.assertEqual(metrics["unsupported_claims"], 1)
        self.assertEqual(metrics["total_tokens"], 1234)

    def test_missing_outputs_are_not_schema_valid(self) -> None:
        metrics = score_outputs({"company_profile": None, "campaign": None, "quality": None})

        self.assertFalse(metrics["schema_valid"])
        self.assertEqual(metrics["citation_coverage"], 0.0)
        self.assertIsNone(metrics["grounded_link_rate"])


class SummarizeTests(TestCase):
    def test_failed_runs_count_against_rates_not_means(self) -> None:
        rows = [
            {"ok": True, "schema_valid": True, "qa_passed": True, "citation_coverage": 1.0, "latency_s": 10},
            {"ok": False, "error": "boom", "latency_s": 2},
        ]

        summary = summarize(rows)

        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["schema_valid_rate"], 0.5)
        self.assertEqual(summary["mean_citation_coverage"], 1.0)
        self.assertEqual(summary["mean_latency_s"], 6.0)
