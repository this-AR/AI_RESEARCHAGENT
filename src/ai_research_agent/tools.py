"""Factories for CrewAI tools.

Imports are intentionally lazy so configuration checks and CLI help work before
the optional AI runtime has been installed.
"""

from __future__ import annotations

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

    class SentimentAnalysisTool(BaseTool):
        name: str = "Sentiment Analysis"
        description: str = "Scores the tone of proposed outreach copy."

        def _run(self, text: str) -> str:
            positive = {"growth", "successful", "opportunity", "value", "partnership"}
            negative = {"decline", "failure", "loss", "problem", "setback"}
            tokens = {token.strip(".,!?;:").lower() for token in text.split()}
            score = len(tokens & positive) - len(tokens & negative)
            label = "positive" if score > 0 else "negative" if score < 0 else "neutral"
            return f"Tone: {label}; lexical score: {score}."

    class LeadProfilingTool(BaseTool):
        name: str = "Lead Profile Outline"
        description: str = "Creates a consistent checklist for company qualification research."

        def _run(self, company_data: str) -> str:
            company = company_data.strip() or "Unknown company"
            return (
                f"Profile target: {company}\n"
                "Research: market position, recent activity, decision-maker evidence, "
                "pain points, fit, timing, and source freshness.\n"
                "Do not assign a score unless supporting evidence is present."
            )

    class DuckDuckGoSearchTool(BaseTool):
        name: str = "DuckDuckGo Search"
        description: str = "Searches the public web and returns titles, URLs, and snippets."

        def _run(self, query: str) -> str:
            try:
                from ddgs import DDGS
            except ImportError as exc:
                raise DependencyError("DuckDuckGo search requires the 'ddgs' package.") from exc

            results = DDGS().text(query, max_results=5)
            formatted = [
                f"Title: {item.get('title', 'N/A')}\n"
                f"URL: {item.get('href', 'N/A')}\n"
                f"Summary: {item.get('body', 'N/A')}"
                for item in results
            ]
            return "\n\n".join(formatted) or "No search results found."

    sentiment = SentimentAnalysisTool()
    profile = LeadProfilingTool()

    if settings.serper_api_key:
        try:
            from crewai_tools import SerperDevTool
        except ImportError as exc:
            raise DependencyError("Serper search requires the CrewAI tools package.") from exc
        os.environ["SERPER_API_KEY"] = settings.serper_api_key
        search: Any = SerperDevTool()
    else:
        search = DuckDuckGoSearchTool()

    return {"search": search, "sentiment": sentiment, "profile": profile}
