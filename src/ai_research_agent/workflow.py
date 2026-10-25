"""Construction and execution of the CrewAI workflow."""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agents import build_agents
from .config import Settings
from .errors import DependencyError, WorkflowError
from .exports import export_json
from .lead_scoring import score_lead
from .models import ResearchTarget
from .schemas import ResearchRun, ResearchSource
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


_TRANSIENT_STATUS = {429, 500, 502, 503, 504}
# Fallback for provider errors that arrive without a typed exception.
_TRANSIENT_TOKENS = (
    "rate limit", "rate_limit", "timeout", "temporar", "unavailable", "overloaded", "high demand", " 503", " 429",
)


def _transient_types() -> tuple[type[BaseException], ...]:
    types: list[type[BaseException]] = [TimeoutError, ConnectionError]
    try:
        import litellm

        types += [
            litellm.RateLimitError,
            litellm.ServiceUnavailableError,
            litellm.Timeout,
            litellm.APIConnectionError,
            litellm.InternalServerError,
        ]
    except ImportError:
        pass
    return tuple(types)


def _is_transient(exc: BaseException) -> bool:
    """True for provider errors worth retrying: rate limits, overload, timeouts and 5xx."""
    try:
        from google.genai.errors import APIError as GeminiAPIError
    except ImportError:
        GeminiAPIError = ()  # isinstance(x, ()) is always False
    types = _transient_types()
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, types):
            return True
        if isinstance(current, GeminiAPIError) and current.code in _TRANSIENT_STATUS:
            return True
        if any(token in f" {current}".lower() for token in _TRANSIENT_TOKENS):
            return True
        current = current.__cause__ or current.__context__
    return False


def _kickoff_with_retries(crew: Any, inputs: dict[str, str], max_attempts: int) -> Any:
    """Kick off the crew, retrying transient provider errors with jittered backoff; re-raises the last error."""
    delay_seconds = 10.0
    for attempt in range(1, max_attempts + 1):
        try:
            result = crew.kickoff(inputs=inputs)
            if not getattr(result, "pydantic", None):
                raise WorkflowError("Validation rejected: Agent failed to return expected structured Pydantic output.")
            return result
        except Exception as exc:
            retryable = _is_transient(exc) or "validation rejected" in str(exc).lower()
            if not retryable or attempt == max_attempts:
                raise
            # Equal jitter: never retry instantly, but spread concurrent retries apart.
            wait = delay_seconds / 2 + random.uniform(0, delay_seconds / 2)
            LOGGER.warning("Attempt %s/%s failed (%s); retrying in %.0f s", attempt, max_attempts, exc, wait)
            time.sleep(wait)
            delay_seconds *= 2
    raise WorkflowError("Research workflow stopped without producing a result.")  # unreachable


def _token_usage(result: Any) -> dict[str, int]:
    usage = getattr(result, "token_usage", None)
    dump = usage.model_dump() if hasattr(usage, "model_dump") else {}
    return {k: v for k, v in dump.items() if isinstance(v, int)} if isinstance(dump, dict) else {}


def run_research(
    target: ResearchTarget,
    settings: Settings,
    *,
    output_path: Path | None = None,
    max_attempts: int = 3,
) -> tuple[Any, Path]:
    """Run the workflow and persist the result as Markdown plus a JSON ResearchRun artifact."""
    sources = _gather_sources(target, settings)
    # The final-email guardrail only accepts URLs in this set; the search tool adds any extra results.
    retrieved_urls = {s.url for s in sources}
    inputs = {**target.as_inputs(), "search_results": _format_sources(sources)}

    LOGGER.info("Starting research for %s with %s", target.company_name, settings.litellm_model)
    crew = build_crew(settings, retrieved_urls)
    try:
        result = _kickoff_with_retries(crew, inputs, max_attempts)
    except Exception as exc:
        fallback = settings.fallback()
        if fallback is None or not _is_transient(exc):
            raise WorkflowError(f"Research workflow failed: {exc}") from exc
        LOGGER.warning(
            "%s unavailable (%s); switching to fallback %s", settings.litellm_model, exc, fallback.litellm_model
        )
        settings = fallback
        crew = build_crew(settings, retrieved_urls)
        try:
            result = _kickoff_with_retries(crew, inputs, max_attempts)
        except Exception as fallback_exc:
            raise WorkflowError(f"Research workflow failed on fallback model: {fallback_exc}") from fallback_exc

    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = settings.output_dir / f"research_{timestamp}.md"

    profile = crew.tasks[0].output.pydantic if len(crew.tasks) > 0 else None
    campaign = crew.tasks[4].output.pydantic if len(crew.tasks) > 4 else (crew.tasks[1].output.pydantic if len(crew.tasks) > 1 else None)
    quality = crew.tasks[3].output.pydantic if len(crew.tasks) > 3 else None

    markdown_path = _write_result(result, target, output_path)
    run = ResearchRun(
        target=target.as_inputs(),
        company_profile=profile,
        lead_score=score_lead(profile) if profile else None,
        campaign=campaign,
        quality=quality,
        model=settings.litellm_model,
        sources=sources,
        retrieved_urls=sorted(retrieved_urls),
        token_usage=_token_usage(result),
    )
    artifact = export_json(run, output_path.with_suffix(".json"))

    structured_outputs = {
        "company_profile": profile,
        "campaign": campaign,
        "quality": quality,
        "raw_result": result,
        "retrieved_urls": retrieved_urls,
        "model": settings.litellm_model,
        "artifact": artifact,
    }
    return structured_outputs, markdown_path
