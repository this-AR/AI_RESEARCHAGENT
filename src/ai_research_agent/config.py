"""Environment-backed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from .errors import ConfigurationError


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _as_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(
        "RESEARCH_VERBOSE must be one of: true, false, 1, 0, yes, no, on, off."
    )


@dataclass(frozen=True, slots=True)
class Settings:
    llm_api_key: str
    llm_model: str
    serper_api_key: str | None
    output_dir: Path
    max_rpm: int
    verbose: bool
    fallback_model: str | None = None
    fallback_api_key: str | None = None

    @classmethod
    def from_env(cls, *, require_live_credentials: bool = True) -> Settings:
        _load_dotenv()

        api_key = (os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY", "")).strip()
        model = (os.getenv("LLM_MODEL") or os.getenv("GROQ_MODEL", "")).strip()
        missing = []
        if require_live_credentials and not api_key:
            missing.append("LLM_API_KEY")
        if require_live_credentials and not model:
            missing.append("LLM_MODEL")
        if missing:
            names = ", ".join(missing)
            raise ConfigurationError(
                f"Missing required configuration: {names}. Copy .env.example to .env and set it."
            )

        raw_max_rpm = os.getenv("RESEARCH_MAX_RPM", "5").strip()
        try:
            max_rpm = int(raw_max_rpm)
        except ValueError as exc:
            raise ConfigurationError("RESEARCH_MAX_RPM must be a positive integer.") from exc
        if max_rpm < 1:
            raise ConfigurationError("RESEARCH_MAX_RPM must be a positive integer.")

        output_dir = Path(os.getenv("RESEARCH_OUTPUT_DIR", "outputs")).expanduser()
        verbose = _as_bool(os.getenv("RESEARCH_VERBOSE", "false"))

        return cls(
            llm_api_key=api_key,
            llm_model=model,
            serper_api_key=os.getenv("SERPER_API_KEY", "").strip() or None,
            output_dir=output_dir,
            max_rpm=max_rpm,
            verbose=verbose,
            fallback_model=os.getenv("LLM_FALLBACK_MODEL", "").strip() or None,
            fallback_api_key=os.getenv("LLM_FALLBACK_API_KEY", "").strip() or None,
        )

    def fallback(self) -> Settings | None:
        """Settings for the fallback model, or None if none is configured."""
        if not self.fallback_model:
            return None
        return replace(
            self,
            llm_model=self.fallback_model,
            llm_api_key=self.fallback_api_key or self.llm_api_key,
            fallback_model=None,  # a fallback never chains to another
            fallback_api_key=None,
        )

    @property
    def litellm_model(self) -> str:
        """Model id with a provider prefix; bare names default to Groq."""
        return self.llm_model if "/" in self.llm_model else f"groq/{self.llm_model}"

    @property
    def search_provider(self) -> str:
        return "Serper" if self.serper_api_key else "DuckDuckGo"
