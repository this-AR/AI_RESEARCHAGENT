from types import SimpleNamespace
from unittest import TestCase

from ai_research_agent.evaluation import check_campaign, score_outputs, summarize
from ai_research_agent.schemas import (
    CompanyProfile,
    EmailCampaign,
    EmailMessage,
    EvidenceClaim,
    QualityReport,
)

RETRIEVED = {"https://acme.com/news/"}


def _email(body: str) -> EmailMessage:
    return EmailMessage(subject="Hi", body=body)


def _campaign(*bodies: str) -> EmailCampaign:
    return EmailCampaign(emails=[_email(b) for b in bodies])


GOOD = _campaign(*["Congrats [Source](https://acme.com/news)"] * 4)
GOOD_BODIES = [e.body for e in GOOD.emails]


class ScoreOutputsTests(TestCase):
    def test_measures_citations_and_grounding_against_retrieved_urls(self) -> None:
        campaign = EmailCampaign(
            emails=[
                _email("Congrats [Source](https://acme.com/news)"),  # retrieved, despite slash
                _email("Saw this [Source](https://made-up.example)"),  # never retrieved
                EmailMessage(
                    subject="Hi",
                    body="No inline link",
                    personalization_evidence=[EvidenceClaim(claim="News", source_url="https://acme.com/news")],
                ),
                _email("Also none"),
            ]
        )
        outputs = {
            "company_profile": CompanyProfile(company_name="Acme"),
            "campaign": campaign,
            "quality": QualityReport(passed=False, unsupported_claims=["x"]),
            "raw_result": SimpleNamespace(token_usage=SimpleNamespace(total_tokens=1234)),
            "retrieved_urls": RETRIEVED,
        }

        metrics = score_outputs(outputs)

        self.assertTrue(metrics["schema_valid"])
        self.assertEqual(metrics["citation_coverage"], 0.5)
        self.assertEqual(metrics["evidence_coverage"], 0.25)
        self.assertAlmostEqual(metrics["grounded_link_rate"], 2 / 3)
        self.assertFalse(metrics["draft_qa_passed"])
        self.assertEqual(metrics["unsupported_claims"], 1)
        self.assertEqual(metrics["total_tokens"], 1234)

    def test_missing_outputs_are_not_schema_valid(self) -> None:
        metrics = score_outputs({"company_profile": None, "campaign": None, "quality": None})

        self.assertFalse(metrics["schema_valid"])
        self.assertEqual(metrics["citation_coverage"], 0.0)
        self.assertIsNone(metrics["grounded_link_rate"])


class CheckCampaignTests(TestCase):
    def test_accepts_grounded_campaign(self) -> None:
        self.assertIsNone(check_campaign(GOOD, RETRIEVED))

    def test_rejects_non_campaign(self) -> None:
        self.assertIn("EmailCampaign", check_campaign(None, RETRIEVED))

    def test_rejects_wrong_email_count(self) -> None:
        self.assertIn("exactly four", check_campaign(_campaign(*GOOD_BODIES[:3]), RETRIEVED))

    def test_rejects_email_without_inline_link(self) -> None:
        error = check_campaign(_campaign(*GOOD_BODIES[:3], "No link"), RETRIEVED)
        self.assertIn("Emails [4]", error)
        self.assertIn("https://acme.com/news", error)  # retries see only this feedback

    def test_rejects_ungrounded_url_and_names_it(self) -> None:
        error = check_campaign(_campaign(*GOOD_BODIES[:3], "[Source](https://made-up.example)"), RETRIEVED)
        self.assertIn("https://made-up.example", error)
        self.assertIn("https://acme.com/news", error)

    def test_rejects_everything_when_search_returned_nothing(self) -> None:
        self.assertIn("never returned", check_campaign(GOOD, set()))


class SummarizeTests(TestCase):
    def test_failed_runs_count_against_rates_not_means(self) -> None:
        rows = [
            {"ok": True, "schema_valid": True, "draft_qa_passed": True, "citation_coverage": 1.0, "latency_s": 10},
            {"ok": False, "error": "boom", "latency_s": 2},
        ]

        summary = summarize(rows)

        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["schema_valid_rate"], 0.5)
        self.assertEqual(summary["draft_qa_pass_rate"], 0.5)
        self.assertEqual(summary["mean_citation_coverage"], 1.0)
        self.assertEqual(summary["mean_latency_s"], 6.0)
