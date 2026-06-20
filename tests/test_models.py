from unittest import TestCase

from ai_research_agent.errors import ConfigurationError
from ai_research_agent.models import ResearchTarget


class ResearchTargetTests(TestCase):
    def test_converts_to_crew_inputs(self) -> None:
        target = ResearchTarget("Acme", "Technology", "Alex", "CEO", "Product launch")
        self.assertEqual(target.as_inputs()["company_name"], "Acme")

    def test_rejects_blank_fields(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "industry cannot be empty"):
            ResearchTarget("Acme", " ", "Alex", "CEO", "Product launch")
