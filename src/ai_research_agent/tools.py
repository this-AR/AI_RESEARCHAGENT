"""Factories for CrewAI tools.

Imports are intentionally lazy so configuration checks and CLI help work before
the optional AI runtime has been installed.
"""

from __future__ import annotations

import json
import os
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
    # Sentiment tool
    # -----------------------------------------------------------------------
    class SentimentAnalysisTool(BaseTool):
        name: str = "Sentiment Analysis"
        description: str = "Scores the tone of proposed outreach copy."

        def _run(self, text: str) -> str:
            positive = {"growth", "successful", "opportunity", "value", "partnership", "innovation", "launch", "milestone"}
            negative = {"decline", "failure", "loss", "problem", "setback", "crisis", "layoff", "cut"}
            tokens = {token.strip(".,!?;:'\"").lower() for token in text.split()}
            score = len(tokens & positive) - len(tokens & negative)
            label = "positive" if score > 0 else "negative" if score < 0 else "neutral"
            return f"Tone: {label}; lexical score: {score}."

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
        description: str = "Creates a consistent checklist for company qualification research."

        def _run(self, company_data: str) -> str:
            company = company_data.strip() or "Unknown company"
            return (
                f"Profile target: {company}\n"
                "Research dimensions:\n"
                "- Market position and industry fit\n"
                "- Recent developments and milestones (with sources)\n"
                "- Decision-maker evidence (role, contact info, confidence)\n"
                "- Pain points and challenges (with evidence)\n"
                "- Outreach timing and relevance\n"
                "- Source freshness and verification status\n"
                "Do not assign a score unless supporting evidence is present."
            )

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
