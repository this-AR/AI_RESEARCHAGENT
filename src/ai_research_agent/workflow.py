"""Construction and execution of the CrewAI workflow."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Any

from .agents import build_agents
from .config import Settings
from .errors import DependencyError, WorkflowError
from .models import ResearchTarget
from .tasks import build_tasks
from .tools import build_tools

LOGGER = logging.getLogger(__name__)


def build_crew(settings: Settings) -> Any:
    try:
        from crewai import Crew, Process
    except ImportError as exc:
        raise DependencyError(
            "CrewAI is not installed. Run: python -m pip install -e ."
        ) from exc

    tools = build_tools(settings)
    agents = build_agents(settings, tools)
    tasks = build_tasks(agents)
    return Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        memory=False,
        max_rpm=settings.max_rpm,
        verbose=settings.verbose,
    )


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
        import json
        content += "\n## Structured Output\n```json\n"
        content += json.dumps(result.pydantic.model_dump(), indent=2)
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
    crew = build_crew(settings)
    delay_seconds = 10

    for attempt in range(1, max_attempts + 1):
        try:
            LOGGER.info("Starting research for %s (attempt %s/%s)", target.company_name, attempt, max_attempts)
            result = crew.kickoff(inputs=target.as_inputs())
            break
        except Exception as exc:
            message = str(exc).lower()
            retryable = any(token in message for token in ("rate limit", "rate_limit", "timeout", "temporarily"))
            if not retryable or attempt == max_attempts:
                raise WorkflowError(f"Research workflow failed: {exc}") from exc
            LOGGER.warning("Transient provider error; retrying in %s seconds", delay_seconds)
            time.sleep(delay_seconds)
            delay_seconds *= 2
    else:  # Defensive; the loop always returns or raises.
        raise WorkflowError("Research workflow stopped without producing a result.")

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = settings.output_dir / f"research_{timestamp}.md"

    structured_outputs = {
        "company_profile": crew.tasks[0].output.pydantic if len(crew.tasks) > 0 else None,
        "campaign": crew.tasks[1].output.pydantic if len(crew.tasks) > 1 else None,
        "quality": crew.tasks[3].output.pydantic if len(crew.tasks) > 3 else None,
        "raw_result": result,
    }

    return structured_outputs, _write_result(result, target, output_path)
