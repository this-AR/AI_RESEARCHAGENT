"""CrewAI task factory."""

from __future__ import annotations

from typing import Any

from .errors import DependencyError


def build_tasks(agents: dict[str, Any], retrieved_urls: set[str]) -> list[Any]:
    try:
        from crewai import Task
    except ImportError as exc:
        raise DependencyError(
            "CrewAI is not installed. Run: python -m pip install -e ."
        ) from exc

    from .evaluation import check_campaign
    from .schemas import CompanyProfile, EmailCampaign, QualityReport

    # No return annotation: crewai rejects the string form produced by `from __future__ import annotations`.
    def campaign_guardrail(output):
        error = check_campaign(output.pydantic, retrieved_urls)
        return (False, error) if error else (True, output)

    research = Task(
        description=(
            "Research {company_name} in {industry}. Focus on the stated milestone "
            "({recent_milestone}) and verify the role of {key_decision_maker} ({position}). "
            "Identify market position, recent developments, plausible challenges, and outreach "
            "triggers. Include a URL next to every factual claim. Label inferences explicitly.\n\n"
            "Web search results gathered for this research (title | URL | snippet):\n"
            "{search_results}\n\n"
            "Base every factual claim on these results or on your own Web Search tool calls, and "
            "copy their URLs exactly. Never cite a URL from memory; later steps reject any URL "
            "that search did not return."
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
            "A structured EmailCampaign containing four email drafts, each with a subject, body, call to action, and suggested timing. "
            "Each body cites its claims with inline [Source](url) links taken from the CompanyProfile."
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
    rewrite = Task(
        description=(
            "Review the QualityReport and the drafted EmailCampaign. "
            "If the QualityReport indicates that the sequence failed (passed is false), you MUST completely rewrite "
            "the emails to resolve all unsupported claims, tone issues, and incorporate all recommendations. "
            "If the QualityReport indicates passed is true, return the original emails unchanged. "
            "In both cases, every factual claim in an email body MUST keep or gain an inline markdown "
            "link like [Source](https://...), and personalization_evidence source_url values must be "
            "copied exactly. Use only URLs that appear in the CompanyProfile; never invent or alter a "
            "URL. Remove any claim you cannot link to such a URL, but always return exactly four emails."
        ),
        expected_output=(
            "A structured EmailCampaign containing the final, corrected outreach messages, where each "
            "email body cites its claims with inline [Source](url) links taken from the CompanyProfile."
        ),
        agent=agents["email"],
        context=[research, emails, quality],
        output_pydantic=EmailCampaign,
        guardrail=campaign_guardrail,
        guardrail_max_retries=2,
    )
    return [research, emails, review, quality, rewrite]
