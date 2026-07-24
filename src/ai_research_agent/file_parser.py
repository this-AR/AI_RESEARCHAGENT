"""CSV and JSON lead-list parser with validation and normalization.

Intended for bulk-import workflows.  Reports malformed rows without claiming
successful extraction.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .models import ResearchTarget

LOGGER = logging.getLogger(__name__)

REQUIRED_FIELDS = {"company_name", "industry", "key_decision_maker", "position", "recent_milestone"}


def _normalize_company_name(name: str) -> str:
    return " ".join(name.split()).strip()


def _normalize_url(url: str) -> str | None:
    url = url.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def _normalize_contact(contact: dict[str, Any]) -> dict[str, Any]:
    """Clean and normalize contact fields."""
    cleaned: dict[str, Any] = {}
    for key, value in contact.items():
        if isinstance(value, str):
            cleaned[key] = value.strip()
        else:
            cleaned[key] = value
    if "company_name" in cleaned:
        cleaned["company_name"] = _normalize_company_name(cleaned["company_name"])
    if "website" in cleaned and cleaned["website"]:
        cleaned["website"] = _normalize_url(cleaned["website"])
    return cleaned


def _validate_row(row: dict[str, Any], row_number: int) -> tuple[ResearchTarget | None, str | None]:
    """Return (target, error_message).  Exactly one will be non-None."""
    missing = REQUIRED_FIELDS - set(row.keys())
    if missing:
        return None, f"Row {row_number}: missing required field(s): {', '.join(sorted(missing))}"

    for field in REQUIRED_FIELDS:
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            return None, f"Row {row_number}: field '{field}' is empty."

    try:
        target = ResearchTarget(
            company_name=row["company_name"],
            industry=row["industry"],
            key_decision_maker=row["key_decision_maker"],
            position=row["position"],
            recent_milestone=row["recent_milestone"],
        )
        return target, None
    except Exception as exc:
        return None, f"Row {row_number}: validation error: {exc}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_csv(path: Path | str) -> tuple[list[ResearchTarget], list[str]]:
    """Parse a CSV file and return (valid_targets, error_messages).

    The CSV must contain a header row with at least the required fields.
    """
    path = Path(path)
    if not path.exists():
        raise WorkflowError(f"File not found: {path}")

    targets: list[ResearchTarget] = []
    errors: list[str] = []

    try:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                errors.append("CSV has no header row.")
                return targets, errors

            missing_headers = REQUIRED_FIELDS - set(reader.fieldnames)
            if missing_headers:
                errors.append(f"CSV missing required header(s): {', '.join(sorted(missing_headers))}")
                return targets, errors

            for row_number, row in enumerate(reader, start=2):
                cleaned = _normalize_contact(row)
                target, error = _validate_row(cleaned, row_number)
                if error:
                    errors.append(error)
                elif target is not None:
                    targets.append(target)
    except Exception as exc:
        raise WorkflowError(f"Failed to parse CSV: {exc}") from exc

    LOGGER.info("CSV parsed: %s valid row(s), %s error(s)", len(targets), len(errors))
    return targets, errors


def parse_json(path: Path | str) -> tuple[list[ResearchTarget], list[str]]:
    """Parse a JSON file and return (valid_targets, error_messages).

    The file must contain either a single object or a list of objects.
    Each object must include the required fields.
    """
    path = Path(path)
    if not path.exists():
        raise WorkflowError(f"File not found: {path}")

    targets: list[ResearchTarget] = []
    errors: list[str] = []

    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        raise WorkflowError(f"Failed to parse JSON: {exc}") from exc

    if isinstance(data, dict):
        rows = [data]
    elif isinstance(data, list):
        rows = data
    else:
        errors.append("JSON root must be an object or a list of objects.")
        return targets, errors

    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"Row {row_number}: expected object, got {type(row).__name__}.")
            continue
        cleaned = _normalize_contact(row)
        target, error = _validate_row(cleaned, row_number)
        if error:
            errors.append(error)
        elif target is not None:
            targets.append(target)

    LOGGER.info("JSON parsed: %s valid row(s), %s error(s)", len(targets), len(errors))
    return targets, errors


def parse_file(path: Path | str) -> tuple[list[ResearchTarget], list[str]]:
    """Auto-detect format by extension and parse."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return parse_csv(path)
    if suffix in {".json", ".jsonl"}:
        return parse_json(path)
    raise WorkflowError(f"Unsupported file format: {suffix}. Use .csv or .json.")
