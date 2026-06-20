import os
from unittest import TestCase
from unittest.mock import patch

from ai_research_agent.config import Settings
from ai_research_agent.errors import ConfigurationError


class SettingsTests(TestCase):
    def test_loads_valid_environment(self) -> None:
        environment = {
            "GROQ_API_KEY": "secret",
            "GROQ_MODEL": "example-model",
            "RESEARCH_MAX_RPM": "7",
            "RESEARCH_VERBOSE": "true",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.groq_model, "example-model")
        self.assertEqual(settings.max_rpm, 7)
        self.assertTrue(settings.verbose)
        self.assertEqual(settings.search_provider, "DuckDuckGo")

    def test_rejects_missing_live_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "GROQ_API_KEY, GROQ_MODEL"):
                Settings.from_env()

    def test_rejects_invalid_rate_limit(self) -> None:
        environment = {
            "GROQ_API_KEY": "secret",
            "GROQ_MODEL": "example-model",
            "RESEARCH_MAX_RPM": "zero",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "positive integer"):
                Settings.from_env()
