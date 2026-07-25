"""Environment-backed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
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
    groq_api_key: str
    groq_model: str
    serper_api_key: str | None
    output_dir: Path
    max_rpm: int
    verbose: bool

    @classmethod
    def from_env(cls, *, require_live_credentials: bool = True) -> Settings:
        _load_dotenv()

        api_key = os.getenv("GROQ_API_KEY", "").strip()
        model = os.getenv("GROQ_MODEL", "").strip()
        missing = []
        if require_live_credentials and not api_key:
            missing.append("GROQ_API_KEY")
        if require_live_credentials and not model:
            missing.append("GROQ_MODEL")
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
            groq_api_key=api_key,
            groq_model=model,
            serper_api_key=os.getenv("SERPER_API_KEY", "").strip() or None,
            output_dir=output_dir,
            max_rpm=max_rpm,
            verbose=verbose,
        )

    @property
    def search_provider(self) -> str:
        return "Serper" if self.serper_api_key else "DuckDuckGo"
