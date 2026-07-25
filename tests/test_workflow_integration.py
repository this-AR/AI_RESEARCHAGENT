import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from ai_research_agent.config import Settings
from ai_research_agent.models import ResearchTarget
from ai_research_agent.schemas import CompanyProfile, EmailCampaign, QualityReport
from ai_research_agent.workflow import run_research


class WorkflowIntegrationTests(TestCase):
    def setUp(self):
        self.target = ResearchTarget(
            company_name="Acme Corp",
            industry="Tech",
            key_decision_maker="Alice",
            position="CEO",
            recent_milestone="New funding"
        )
        self.settings = Settings(
            groq_api_key="test_key",
            groq_model="llama3-8b-8192",
            serper_api_key=None,
            output_dir=Path("outputs"),
            max_rpm=5,
            verbose=False
        )

    @patch("ai_research_agent.workflow.build_crew")
    def test_run_research_success(self, mock_build_crew):
        # Setup mock crew and kickoff
        mock_crew_instance = MagicMock()
        mock_build_crew.return_value = mock_crew_instance

        # Mock task outputs
        mock_task_0 = MagicMock()
        mock_task_0.output.pydantic = CompanyProfile(company_name="Acme Corp")

        mock_task_1 = MagicMock()
        mock_task_1.output.pydantic = EmailCampaign(target_company="Acme Corp", emails=[])

        mock_task_3 = MagicMock()
        mock_task_3.output.pydantic = QualityReport(passed=True)

        mock_crew_instance.tasks = [mock_task_0, mock_task_1, MagicMock(), mock_task_3]

        # Mock final output
        mock_result = MagicMock()
        mock_result.raw = "This is a raw mock result."
        mock_result.pydantic = mock_task_3.output.pydantic
        mock_crew_instance.kickoff.return_value = mock_result

        # Ensure directory exists for test
        os.makedirs("outputs", exist_ok=True)
        test_path = Path("outputs/test_workflow.md")

        # Run test
        structured_outputs, output_path = run_research(
            self.target,
            self.settings,
            output_path=test_path
        )

        # Verify
        mock_crew_instance.kickoff.assert_called_once()
        self.assertTrue(output_path.exists())
        self.assertEqual(structured_outputs["company_profile"].company_name, "Acme Corp")
        self.assertTrue(structured_outputs["quality"].passed)

        # Clean up
        if output_path.exists():
            os.remove(output_path)
