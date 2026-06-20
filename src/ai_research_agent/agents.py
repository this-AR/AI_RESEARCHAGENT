"""CrewAI agent factory."""

from __future__ import annotations

from typing import Any

from .config import Settings
from .errors import DependencyError


def build_agents(settings: Settings, tools: dict[str, Any]) -> dict[str, Any]:
    try:
        from crewai import Agent, LLM
    except ImportError as exc:
        raise DependencyError(
            "CrewAI is not installed. Run: python -m pip install -e ."
        ) from exc

    model = settings.groq_model
    if "/" not in model:
        model = f"groq/{model}"
    llm = LLM(model=model, api_key=settings.groq_api_key)
    common = {
        "llm": llm,
        "allow_delegation": False,
        "verbose": settings.verbose,
    }

    lead = Agent(
        role="Lead Discovery Specialist",
        goal="Research a target company and identify evidence-backed outreach opportunities.",
        backstory=(
            "You are a careful business researcher. You distinguish sourced facts from "
            "inference and retain URLs for every material claim."
        ),
        tools=[tools["search"], tools["profile"]],
        max_iter=4,
        **common,
    )
    email = Agent(
        role="Personalized Email Specialist",
        goal="Turn verified research into concise and honest outreach messages.",
        backstory=(
            "You write relevant business outreach without inventing metrics, clients, "
            "testimonials, or company details."
        ),
        tools=[tools["sentiment"]],
        max_iter=3,
        **common,
    )
    orchestrator = Agent(
        role="Workflow Reviewer",
        goal="Review handoffs for completeness, consistency, and unsupported claims.",
        backstory="You are a process reviewer focused on evidence preservation and useful output.",
        tools=[],
        max_iter=2,
        **common,
    )
    quality = Agent(
        role="Quality Assurance Specialist",
        goal="Validate research and outreach before delivery.",
        backstory=(
            "You are a skeptical editor who flags uncertain facts and never converts "
            "assumptions into claims."
        ),
        tools=[tools["sentiment"]],
        max_iter=2,
        **common,
    )
    return {"lead": lead, "email": email, "orchestrator": orchestrator, "quality": quality}
