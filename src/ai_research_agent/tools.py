"""Factories for CrewAI tools.

Imports are intentionally lazy so configuration checks and CLI help work before
the optional AI runtime has been installed.
"""

from __future__ import annotations

import json
from typing import Any

from .config import Settings
from .errors import DependencyError


def build_tools(settings: Settings) -> dict[str, Any]:
    try:
        from crewai.tools import BaseTool
    except ImportError as exc:
        raise DependencyError(
            "CrewAI is not installed. Run: python -m pip install -e ."
        ) from exc

    # -----------------------------------------------------------------------
    # Shared LLM call for the tools below
    # -----------------------------------------------------------------------
    def _complete(system: str, user: str, temperature: float) -> str:
        import litellm

        response = litellm.completion(
            model=settings.litellm_model,
            api_key=settings.llm_api_key,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            timeout=10,
        )
        return response.choices[0].message.content

    # -----------------------------------------------------------------------
    # Sentiment tool
    # -----------------------------------------------------------------------
    class SentimentAnalysisTool(BaseTool):
        name: str = "Sentiment Analysis"
        description: str = "Scores the tone of proposed outreach copy using a language model."

        def _run(self, text: str) -> str:
            if not settings.llm_api_key:
                return "Tone: unknown. LLM API key missing."
            try:
                return _complete(
                    "You are a sentiment analysis tool. Classify the following outreach text's tone (Positive, Negative, or Neutral) and provide a 1-sentence reasoning. Keep your response very brief.",
                    text,
                    0.0,
                )
            except Exception as e:  # noqa: BLE001 - a tool failure must not abort the crew
                return f"Tone: unknown. API error: {e}"

    # -----------------------------------------------------------------------
    # Search tool — delegates to search_engine with caching, dedup, retries
    # -----------------------------------------------------------------------
    class SearchTool(BaseTool):
        name: str = "Web Search"
        description: str = (
            "Searches the public web and returns titles, URLs, and snippets. "
            "Results are deduplicated and cached automatically."
        )

        def _run(self, query: str) -> str:
            from .search_engine import search

            provider = "serper" if settings.serper_api_key else "duckduckgo"
            api_key = settings.serper_api_key
            results = search(query, provider=provider, api_key=api_key, max_results=5)
            if not results:
                return "No search results found."
            formatted = [
                f"Title: {r.title}\nURL: {r.url}\nSummary: {r.snippet}\nSource: {r.provider}"
                for r in results
            ]
            return "\n\n".join(formatted)

    # -----------------------------------------------------------------------
    # Lead profiling tool — returns a research checklist
    # -----------------------------------------------------------------------
    class LeadProfilingTool(BaseTool):
        name: str = "Lead Profile Outline"
        description: str = "Creates a tailored checklist for company qualification research."

        def _run(self, company_data: str) -> str:
            company = company_data.strip() or "Unknown company"
            if not settings.llm_api_key:
                return f"Profile target: {company}\nResearch standard dimensions."
            try:
                content = _complete(
                    "You are a sales research strategist. Create a 5-bullet-point research checklist tailored specifically for the provided company or industry. The checklist must guide a researcher on what to look for to qualify the lead. Be extremely concise. No intro/outro.",
                    company,
                    0.3,
                )
                return f"Tailored Research Outline for {company}:\n{content}"
            except Exception as e:  # noqa: BLE001 - a tool failure must not abort the crew
                return f"Profile target: {company}\nResearch standard dimensions. (Error: {e})"

    # -----------------------------------------------------------------------
    # File parser tool — CSV/JSON bulk import
    # -----------------------------------------------------------------------
    class FileParserTool(BaseTool):
        name: str = "Lead List Parser"
        description: str = (
            "Parses a CSV or JSON file containing lead data. "
            "Returns parsed targets or error messages."
        )

        def _run(self, file_path: str) -> str:
            from pathlib import Path

            from .file_parser import parse_file

            path = Path(file_path)
            targets, errors = parse_file(path)
            output: dict[str, Any] = {
                "valid_rows": [t.as_inputs() for t in targets],
                "error_count": len(errors),
                "errors": errors,
            }
            return json.dumps(output, indent=2)

    sentiment = SentimentAnalysisTool()
    profile = LeadProfilingTool()
    search = SearchTool()
    parser = FileParserTool()

    return {
        "search": search,
        "sentiment": sentiment,
        "profile": profile,
        "parser": parser,
    }
