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
    # Sentiment tool
    # -----------------------------------------------------------------------
    class SentimentAnalysisTool(BaseTool):
        name: str = "Sentiment Analysis"
        description: str = "Scores the tone of proposed outreach copy using a language model."

        def _run(self, text: str) -> str:
            import requests

            if not settings.groq_api_key:
                return "Tone: unknown. Groq API key missing."
            
            headers = {
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": settings.groq_model,
                "messages": [
                    {"role": "system", "content": "You are a sentiment analysis tool. Classify the following outreach text's tone (Positive, Negative, or Neutral) and provide a 1-sentence reasoning. Keep your response very brief."},
                    {"role": "user", "content": text}
                ],
                "temperature": 0.0
            }
            try:
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
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
            import requests

            company = company_data.strip() or "Unknown company"
            if not settings.groq_api_key:
                return f"Profile target: {company}\nResearch standard dimensions."

            headers = {
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": settings.groq_model,
                "messages": [
                    {"role": "system", "content": "You are a sales research strategist. Create a 5-bullet-point research checklist tailored specifically for the provided company or industry. The checklist must guide a researcher on what to look for to qualify the lead. Be extremely concise. No intro/outro."},
                    {"role": "user", "content": company}
                ],
                "temperature": 0.3
            }
            try:
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                return f"Tailored Research Outline for {company}:\n{content}"
            except Exception as e:
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
