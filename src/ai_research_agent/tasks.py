"""CrewAI task factory."""

from __future__ import annotations

from typing import Any

from .errors import DependencyError


def build_tasks(agents: dict[str, Any]) -> list[Any]:
    try:
        from crewai import Task
    except ImportError as exc:
        raise DependencyError(
            "CrewAI is not installed. Run: python -m pip install -e ."
        ) from exc
    
    from .schemas import CompanyProfile, EmailCampaign, QualityReport

    research = Task(
        description=(
            "Research {company_name} in {industry}. Focus on the stated milestone "
            "({recent_milestone}) and verify the role of {key_decision_maker} ({position}). "
            "Identify market position, recent developments, plausible challenges, and outreach "
            "triggers. Include a URL next to every factual claim. Label inferences explicitly."
        ),
        expected_output=(
            "A structured CompanyProfile with an executive summary, decision-maker evidence, "
            "recent developments, opportunities, risks, and a source list."
        ),
        agent=agents["lead"],
        output_pydantic=CompanyProfile,
    )
    emails = Task(
        description=(
            "Draft a 4-step email sequence based on the CompanyProfile. Keep it concise, personalized, and "
            "honest. Do not invent social proof, metrics, clients, or capabilities. "
            "CRITICAL REQUIREMENT: For every factual claim, metric, or recent milestone you mention, you MUST "
            "include an inline markdown link to the source URL provided in the CompanyProfile (e.g., "
            "'We saw you raised $10M [Source](https://example.com)')."
        ),
        expected_output=(
            "A structured EmailCampaign containing four email drafts, each with a subject, body, call to action, and suggested timing."
        ),
        agent=agents["email"],
        context=[research],
        output_pydantic=EmailCampaign,
    )
    review = Task(
        description=(
            "Review the research-to-email handoff. Identify missing evidence, unsupported claims, "
            "and weak personalization. Recommend precise corrections."
        ),
        expected_output="A short handoff review with pass/fail findings and corrections.",
        agent=agents["orchestrator"],
        context=[research, emails],
    )
    quality = Task(
        description=(
            "Perform final quality assurance. Check factual support, tone, readability, and calls "
            "to action. Return corrected deliverables and a clear go/no-go recommendation."
        ),
        expected_output="A structured QualityReport detailing pass/fail status, unsupported claims, missing evidence, tone issues, and recommendations.",
        agent=agents["quality"],
        context=[research, emails, review],
        output_pydantic=QualityReport,
    )
    return [research, emails, review, quality]
