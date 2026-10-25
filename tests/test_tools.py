from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from ai_research_agent.config import Settings
from ai_research_agent.schemas import ResearchSource
from ai_research_agent.tools import build_tools


def _settings(api_key: str = "secret") -> Settings:
    return Settings(
        llm_api_key=api_key,
        llm_model="example-model",
        serper_api_key=None,
        output_dir=Path("outputs"),
        max_rpm=5,
        verbose=False,
    )


class LlmToolTests(TestCase):
    @patch("litellm.completion")
    def test_routes_through_litellm_with_prefixed_model(self, completion) -> None:
        completion.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Positive."))]
        )
        result = build_tools(_settings(), set())["sentiment"]._run("Great to meet you")

        self.assertEqual(result, "Positive.")
        self.assertEqual(completion.call_args.kwargs["model"], "groq/example-model")

    @patch("litellm.completion", side_effect=RuntimeError("boom"))
    def test_provider_error_falls_back(self, _) -> None:
        tools = build_tools(_settings(), set())

        self.assertIn("API error: boom", tools["sentiment"]._run("hi"))
        self.assertIn("(Error: boom)", tools["profile"]._run("Acme"))

    @patch("litellm.completion")
    def test_missing_key_skips_call(self, completion) -> None:
        tools = build_tools(_settings(api_key=""), set())

        self.assertIn("LLM API key missing", tools["sentiment"]._run("hi"))
        self.assertEqual(tools["profile"]._run("Acme"), "Profile target: Acme\nResearch standard dimensions.")
        completion.assert_not_called()


class SearchToolTests(TestCase):
    @patch("ai_research_agent.search_engine.search")
    def test_records_every_returned_url(self, search) -> None:
        search.return_value = [
            ResearchSource(url="https://acme.com/news/", title="News", provider="test"),
            ResearchSource(url="https://acme.com/about/", title="About", provider="test"),
        ]
        retrieved: set[str] = set()

        build_tools(_settings(), retrieved)["search"]._run("acme")

        self.assertEqual(retrieved, {"https://acme.com/news/", "https://acme.com/about/"})
