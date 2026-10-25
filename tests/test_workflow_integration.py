import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

import litellm
from google.genai.errors import ServerError

from ai_research_agent.config import Settings
from ai_research_agent.errors import WorkflowError
from ai_research_agent.models import ResearchTarget
from ai_research_agent.schemas import (
    CompanyProfile,
    EmailCampaign,
    QualityReport,
    ResearchRun,
    ResearchSource,
)
from ai_research_agent.workflow import _is_transient, run_research

SOURCE = ResearchSource(url="https://acme.com/news/", title="Acme news", provider="test")


def _overloaded() -> ServerError:
    return ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})


def _mock_crew() -> MagicMock:
    crew = MagicMock()
    profile, campaign, quality = MagicMock(), MagicMock(), MagicMock()
    profile.output.pydantic = CompanyProfile(company_name="Acme Corp")
    campaign.output.pydantic = EmailCampaign(target_company="Acme Corp", emails=[])
    quality.output.pydantic = QualityReport(passed=True)
    crew.tasks = [profile, campaign, MagicMock(), quality]
    result = MagicMock()
    result.raw = "This is a raw mock result."
    result.pydantic = quality.output.pydantic
    result.token_usage.model_dump.return_value = {"total_tokens": 42, "prompt_tokens": 40}
    crew.kickoff.return_value = result
    return crew


@patch("ai_research_agent.workflow.time.sleep")
@patch("ai_research_agent.search_engine.search", return_value=[SOURCE])
class WorkflowIntegrationTests(TestCase):
    def setUp(self):
        self.target = ResearchTarget(
            company_name="Acme Corp",
            industry="Tech",
            key_decision_maker="Alice",
            position="CEO",
            recent_milestone="New funding",
        )
        self.settings = Settings(
            llm_api_key="test_key",
            llm_model="gemini/primary",
            serper_api_key=None,
            output_dir=Path("outputs"),
            max_rpm=5,
            verbose=False,
        )
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output_path = Path(self.tmp.name) / "acme.md"

    @patch("ai_research_agent.workflow.build_crew")
    def test_no_search_results_fails_before_any_llm_call(self, mock_build_crew, search, _):
        search.return_value = []
        with self.assertRaisesRegex(WorkflowError, "cannot be grounded"):
            run_research(self.target, self.settings)
        mock_build_crew.assert_not_called()

    @patch("ai_research_agent.workflow.build_crew")
    def test_run_research_success_writes_markdown_and_json_artifact(self, mock_build_crew, *_):
        crew = _mock_crew()
        mock_build_crew.return_value = crew

        outputs, path = run_research(self.target, self.settings, output_path=self.output_path)

        crew.kickoff.assert_called_once()
        self.assertTrue(path.exists())
        self.assertEqual(outputs["company_profile"].company_name, "Acme Corp")
        self.assertEqual(outputs["model"], "gemini/primary")
        # Pre-searched URLs seed the registry the crew's tool and guardrail share, and reach the prompt.
        self.assertIs(outputs["retrieved_urls"], mock_build_crew.call_args.args[1])
        self.assertEqual(outputs["retrieved_urls"], {"https://acme.com/news/"})
        self.assertIn("https://acme.com/news/", crew.kickoff.call_args.kwargs["inputs"]["search_results"])

        run = ResearchRun.model_validate_json(outputs["artifact"].read_text(encoding="utf-8"))
        self.assertEqual(outputs["artifact"], self.output_path.with_suffix(".json"))
        self.assertEqual(run.retrieved_urls, ["https://acme.com/news/"])
        self.assertEqual(run.sources[0].title, "Acme news")
        self.assertEqual(run.token_usage["total_tokens"], 42)
        self.assertEqual(run.model, "gemini/primary")

    @patch("ai_research_agent.workflow.build_crew")
    def test_switches_to_fallback_when_primary_stays_overloaded(self, mock_build_crew, *_):
        primary, fallback = _mock_crew(), _mock_crew()
        primary.kickoff.side_effect = _overloaded()
        mock_build_crew.side_effect = [primary, fallback]

        outputs, _ = run_research(self.target, _with_fallback(self.settings), output_path=self.output_path)

        self.assertEqual(primary.kickoff.call_count, 3)
        fallback.kickoff.assert_called_once()
        self.assertEqual(mock_build_crew.call_args_list[1].args[0].litellm_model, "groq/llama-3.3-70b-versatile")
        self.assertEqual(outputs["model"], "groq/llama-3.3-70b-versatile")
        # The fallback reuses the first search: same registry object, no second search round.
        self.assertIs(mock_build_crew.call_args_list[1].args[1], outputs["retrieved_urls"])

    @patch("ai_research_agent.workflow.build_crew")
    def test_without_fallback_a_persistent_overload_fails(self, mock_build_crew, _, sleep):
        crew = _mock_crew()
        crew.kickoff.side_effect = _overloaded()
        mock_build_crew.return_value = crew

        with self.assertRaisesRegex(WorkflowError, "503"):
            run_research(self.target, self.settings, output_path=self.output_path)
        self.assertEqual(crew.kickoff.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("ai_research_agent.workflow.build_crew")
    def test_non_transient_error_is_not_retried_or_failed_over(self, mock_build_crew, *_):
        crew = _mock_crew()
        crew.kickoff.side_effect = ValueError("Task failed guardrail validation after 2 retries.")
        mock_build_crew.return_value = crew

        with self.assertRaises(WorkflowError):
            run_research(self.target, _with_fallback(self.settings), output_path=self.output_path)
        crew.kickoff.assert_called_once()
        mock_build_crew.assert_called_once()


def _with_fallback(settings: Settings) -> Settings:
    return replace(settings, fallback_model="llama-3.3-70b-versatile", fallback_api_key="groq_key")


class TransientErrorTests(TestCase):
    def test_classifies_provider_errors(self) -> None:
        self.assertTrue(_is_transient(_overloaded()))
        self.assertTrue(_is_transient(litellm.RateLimitError("slow down", "groq", "llama")))
        self.assertTrue(_is_transient(TimeoutError()))
        self.assertFalse(_is_transient(ValueError("bad output")))
        self.assertFalse(_is_transient(ServerError(501, {"error": {"code": 501, "message": "nope", "status": "X"}})))

    def test_follows_wrapped_causes(self) -> None:
        try:
            try:
                raise _overloaded()
            except ServerError as inner:
                raise RuntimeError("crew failed") from inner
        except RuntimeError as outer:
            self.assertTrue(_is_transient(outer))
