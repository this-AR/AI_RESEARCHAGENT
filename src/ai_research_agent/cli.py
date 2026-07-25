"""Command-line interface for the AI Research Agent."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .config import Settings
from .errors import ConfigurationError, ResearchAgentError
from .logging_config import configure_logging
from .models import ResearchTarget


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research-agent",
        description="Research a company and generate a reviewed outreach sequence.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="validate local setup without API calls")
    doctor.set_defaults(handler=_doctor)

    run = subparsers.add_parser("run", help="run live company research")
    run.add_argument("--company", required=True, help="target company name")
    run.add_argument("--industry", required=True, help="target company's industry")
    run.add_argument("--decision-maker", required=True, help="target contact name")
    run.add_argument("--position", required=True, help="target contact's role")
    run.add_argument("--milestone", required=True, help="recent event to investigate")
    run.add_argument("--output", type=Path, help="optional Markdown output path")
    run.set_defaults(handler=_run)
    return parser


def _doctor(_: argparse.Namespace) -> int:
    print("AI Research Agent setup check")
    print(f"  Python: {sys.version.split()[0]}")
    crewai_installed = importlib.util.find_spec("crewai") is not None
    print(f"  CrewAI: {'installed' if crewai_installed else 'missing'}")

    settings = Settings.from_env(require_live_credentials=False)
    credentials_ready = bool(settings.groq_api_key and settings.groq_model)
    print(f"  Live credentials: {'configured' if credentials_ready else 'missing'}")
    print(f"  Search provider: {settings.search_provider}")
    print(f"  Output directory: {settings.output_dir}")

    if not crewai_installed:
        print("\nInstall dependencies with: python -m pip install -e .")
    if not credentials_ready:
        print("Configure a local .env file from .env.example before a live run.")
    return 0 if crewai_installed and credentials_ready else 1


def _run(args: argparse.Namespace) -> int:
    settings = Settings.from_env(require_live_credentials=True)
    configure_logging(settings.verbose)
    target = ResearchTarget(
        company_name=args.company,
        industry=args.industry,
        key_decision_maker=args.decision_maker,
        position=args.position,
        recent_milestone=args.milestone,
    )

    from .workflow import run_research

    _, path = run_research(target, settings, output_path=args.output)
    print(f"Research completed: {path.resolve()}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (ConfigurationError, ResearchAgentError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
