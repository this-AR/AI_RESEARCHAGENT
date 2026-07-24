"""Search provider abstraction with caching, deduplication, retries, and normalization.

This module is intentionally free of CrewAI imports so it can be tested offline.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import HttpUrl

from .errors import ConfigurationError, DependencyError, WorkflowError
from .schemas import ResearchSource

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

class _SearchCache:
    """Simple in-memory LRU cache with TTL."""

    def __init__(self, maxsize: int = 128, ttl_seconds: int = 300) -> None:
        self._store: OrderedDict[str, tuple[float, list[ResearchSource]]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl_seconds

    def _key(self, query: str, provider: str) -> str:
        return hashlib.sha256(f"{provider}:{query}".encode()).hexdigest()

    def get(self, query: str, provider: str) -> list[ResearchSource] | None:
        key = self._key(query, provider)
        now = time.time()
        if key in self._store:
            inserted, results = self._store[key]
            if now - inserted <= self._ttl:
                self._store.move_to_end(key)
                LOGGER.debug("Cache hit for query: %s", query[:60])
                return results
            del self._store[key]
        return None

    def set(self, query: str, provider: str, results: list[ResearchSource]) -> None:
        key = self._key(query, provider)
        self._store[key] = (time.time(), results)
        self._store.move_to_end(key)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)


# Global process-level cache instance.
_SEARCH_CACHE = _SearchCache()


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str | None:
    """Return a canonical URL string or None if invalid."""
    url = url.strip()
    if not url or url.lower() in {"n/a", "na", "none"}:
        return None
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    try:
        parsed = HttpUrl(url)
        return str(parsed)
    except Exception:
        return None


def _normalize_result(raw: dict[str, Any], provider: str) -> ResearchSource | None:
    """Convert a raw provider result dict into a validated ResearchSource."""
    title = raw.get("title", "").strip()
    url = _normalize_url(raw.get("href", raw.get("url", "")))
    if not title or not url:
        return None
    return ResearchSource(
        url=url,
        title=title,
        snippet=raw.get("body", raw.get("snippet", "")).strip(),
        provider=provider,
        retrieved_at=datetime.now(timezone.utc),
    )


def _deduplicate(results: list[ResearchSource]) -> list[ResearchSource]:
    """Remove duplicates by normalized URL, preserving order."""
    seen: set[str] = set()
    out: list[ResearchSource] = []
    for r in results:
        key = str(r.url).lower().rstrip("/")
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _search_duckduckgo(query: str, max_results: int = 5) -> list[ResearchSource]:
    try:
        from ddgs import DDGS
    except ImportError as exc:
        raise DependencyError("DuckDuckGo search requires the 'ddgs' package.") from exc

    try:
        raw_results = DDGS().text(query, max_results=max_results)
    except Exception as exc:
        raise WorkflowError(f"DuckDuckGo search failed: {exc}") from exc

    parsed = [_normalize_result(r, "DuckDuckGo") for r in raw_results]
    return [r for r in parsed if r is not None]


def _search_serper(query: str, api_key: str, max_results: int = 5) -> list[ResearchSource]:
    try:
        import requests
    except ImportError as exc:
        raise DependencyError("Serper search requires the 'requests' package.") from exc

    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": max_results}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise WorkflowError(f"Serper search failed: {exc}") from exc

    raw_results = data.get("organic", [])
    parsed = [_normalize_result(r, "Serper") for r in raw_results]
    return [r for r in parsed if r is not None]


# ---------------------------------------------------------------------------
# Retries
# ---------------------------------------------------------------------------

def _with_retry(
    fn: Callable[[], list[ResearchSource]],
    max_attempts: int = 3,
    base_delay: float = 2.0,
) -> list[ResearchSource]:
    """Call *fn* with exponential backoff on WorkflowError."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except WorkflowError as exc:
            last_exc = exc
            msg = str(exc).lower()
            retryable = any(token in msg for token in ("rate limit", "rate_limit", "timeout", "temporarily", "failed"))
            if not retryable or attempt == max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            LOGGER.warning("Search error (attempt %s/%s); retrying in %ss: %s", attempt, max_attempts, delay, exc)
            time.sleep(delay)
    raise last_exc or WorkflowError("Search stopped without producing a result.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search(
    query: str,
    *,
    provider: str = "duckduckgo",
    api_key: str | None = None,
    max_results: int = 5,
    use_cache: bool = True,
    max_attempts: int = 3,
) -> list[ResearchSource]:
    """Run a web search and return normalized, deduplicated ResearchSources.

    Parameters
    ----------
    query:
        The search query string.
    provider:
        One of ``"duckduckgo"`` or ``"serper"``.
    api_key:
        Required when *provider* is ``"serper"``.
    max_results:
        Maximum number of results to request from the provider.
    use_cache:
        Whether to read from or write to the in-memory query cache.
    max_attempts:
        Number of retry attempts with exponential backoff.

    Returns
    -------
    list[ResearchSource]
        Deduplicated, validated search results.
    """
    query = query.strip()
    if not query:
        return []

    provider = provider.lower().strip()

    if use_cache:
        cached = _SEARCH_CACHE.get(query, provider)
        if cached is not None:
            return cached

    LOGGER.info("Searching '%s...' via %s", query[:60], provider)

    if provider == "duckduckgo":
        results = _with_retry(lambda: _search_duckduckgo(query, max_results), max_attempts)
    elif provider == "serper":
        if not api_key:
            raise ConfigurationError("Serper provider requires an API key.")
        results = _with_retry(lambda: _search_serper(query, api_key, max_results), max_attempts)
    else:
        raise ConfigurationError(f"Unsupported search provider: {provider}")

    results = _deduplicate(results)

    if use_cache:
        _SEARCH_CACHE.set(query, provider, results)

    LOGGER.info("Search returned %s unique result(s)", len(results))
    return results
