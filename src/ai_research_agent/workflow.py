"""Construction and execution of the CrewAI workflow."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agents import build_agents
from .config import Settings
from .errors import DependencyError, WorkflowError
from .models import ResearchTarget
from .schemas import ResearchSource
from .tasks import build_tasks
from .tools import build_tools

LOGGER = logging.getLogger(__name__)


def build_crew(settings: Settings, retrieved_urls: set[str]) -> Any:
    try:
        from crewai import Crew, Process
    except ImportError as exc:
        raise DependencyError(
            "CrewAI is not installed. Run: python -m pip install -e ."
        ) from exc

    tools = build_tools(settings, retrieved_urls)
    agents = build_agents(settings, tools)
    tasks = build_tasks(agents, retrieved_urls)
    return Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        memory=False,
        max_rpm=settings.max_rpm,
        verbose=settings.verbose,
    )


def _gather_sources(target: ResearchTarget, settings: Settings) -> list[ResearchSource]:
    """Search before the crew runs: the research agent cannot be relied on to call the tool."""
    from .search_engine import search

    queries = [
        f"{target.company_name} {target.recent_milestone}",
        f"{target.company_name} {target.industry} news",
        f"{target.key_decision_maker} {target.position} {target.company_name}",
    ]
    by_url: dict[str, ResearchSource] = {}
    for query in queries:
        try:
            results = search(
                query,
                provider=settings.search_provider.lower(),
                api_key=settings.serper_api_key,
                max_results=5,
            )
        except WorkflowError as exc:
            LOGGER.warning("Search failed for %r: %s", query, exc)
            continue
        by_url.update((s.url, s) for s in results)
    if not by_url:
        raise WorkflowError("Web search returned no results, so the research cannot be grounded.")
    return list(by_url.values())


def _format_sources(sources: list[ResearchSource]) -> str:
    return "\n".join(f"- {s.title} | {s.url} | {s.snippet}" for s in sources)


def _result_text(result: Any) -> str:
    raw = getattr(result, "raw", None)
    return str(raw if raw is not None else result)


def _write_result(
    result: Any,
    target: ResearchTarget,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()
    content = (
        "# AI Research Agent Result\n\n"
        f"- Company: {target.company_name}\n"
        f"- Decision maker: {target.key_decision_maker} ({target.position})\n"
        f"- Created: {created_at}\n\n"
        f"{_result_text(result)}\n"
    )
    if hasattr(result, "pydantic") and result.pydantic:
        content += "\n## Structured Output\n```json\n"
        content += result.pydantic.model_dump_json(indent=2)
        content += "\n```\n"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def run_research(
    target: ResearchTarget,
    settings: Settings,
    *,
    output_path: Path | None = None,
    max_attempts: int = 3,
) -> tuple[Any, Path]:
    """Run the workflow and persist the final result as Markdown."""
    sources = _gather_sources(target, settings)
    # The final-email guardrail only accepts URLs in this set; the search tool adds any extra results.
    retrieved_urls = {s.url for s in sources}
    inputs = {**target.as_inputs(), "search_results": _format_sources(sources)}
    crew = build_crew(settings, retrieved_urls)
    delay_seconds = 10

    for attempt in range(1, max_attempts + 1):
        try:
            LOGGER.info("Starting research for %s (attempt %s/%s)", target.company_name, attempt, max_attempts)
            result = crew.kickoff(inputs=inputs)
            
            # Validation/Rejection check
            if not getattr(result, "pydantic", None):
                raise WorkflowError("Validation rejected: Agent failed to return expected structured Pydantic output.")
                
            break
        except Exception as exc:
            message = str(exc).lower()
            retryable = any(token in message for token in ("rate limit", "rate_limit", "timeout", "temporarily", "validation rejected"))
            if not retryable or attempt == max_attempts:
                raise WorkflowError(f"Research workflow failed: {exc}") from exc
            LOGGER.warning("Transient provider error; retrying in %s seconds", delay_seconds)
            time.sleep(delay_seconds)
            delay_seconds *= 2
    else:  # Defensive; the loop always returns or raises.
        raise WorkflowError("Research workflow stopped without producing a result.")

    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = settings.output_dir / f"research_{timestamp}.md"

    structured_outputs = {
        "company_profile": crew.tasks[0].output.pydantic if len(crew.tasks) > 0 else None,
        "campaign": crew.tasks[4].output.pydantic if len(crew.tasks) > 4 else (crew.tasks[1].output.pydantic if len(crew.tasks) > 1 else None),
        "quality": crew.tasks[3].output.pydantic if len(crew.tasks) > 3 else None,
        "raw_result": result,
        "retrieved_urls": retrieved_urls,
    }

    return structured_outputs, _write_result(result, target, output_path)
