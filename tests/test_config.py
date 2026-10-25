import os
from unittest import TestCase
from unittest.mock import patch

from ai_research_agent.config import Settings
from ai_research_agent.errors import ConfigurationError


# Keep a developer's local .env out of these tests.
@patch("ai_research_agent.config._load_dotenv")
class SettingsTests(TestCase):
    def test_loads_valid_environment(self, _) -> None:
        environment = {
            "GROQ_API_KEY": "secret",
            "GROQ_MODEL": "example-model",
            "RESEARCH_MAX_RPM": "7",
            "RESEARCH_VERBOSE": "true",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.llm_model, "example-model")
        self.assertEqual(settings.max_rpm, 7)
        self.assertTrue(settings.verbose)
        self.assertEqual(settings.search_provider, "DuckDuckGo")
        self.assertEqual(settings.litellm_model, "groq/example-model")

    def test_keeps_explicit_provider_prefix(self, _) -> None:
        environment = {"LLM_API_KEY": "secret", "LLM_MODEL": "openai/gpt-4o-mini"}
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(Settings.from_env().litellm_model, "openai/gpt-4o-mini")

    def test_rejects_missing_live_credentials(self, _) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(
            ConfigurationError, "LLM_API_KEY, LLM_MODEL"
        ):
            Settings.from_env()

    def test_rejects_invalid_rate_limit(self, _) -> None:
        environment = {
            "GROQ_API_KEY": "secret",
            "GROQ_MODEL": "example-model",
            "RESEARCH_MAX_RPM": "zero",
        }
        with patch.dict(os.environ, environment, clear=True), self.assertRaisesRegex(
            ConfigurationError, "positive integer"
        ):
            Settings.from_env()
