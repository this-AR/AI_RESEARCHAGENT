from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

from ai_research_agent.errors import ConfigurationError, WorkflowError
from ai_research_agent.schemas import ResearchSource
from ai_research_agent.search_engine import (
    _deduplicate,
    _normalize_result,
    _normalize_url,
    _SearchCache,
    search,
)


class NormalizeUrlTests(TestCase):
    def test_valid_url(self) -> None:
        self.assertEqual(_normalize_url("https://example.com"), "https://example.com/")

    def test_adds_https(self) -> None:
        self.assertEqual(_normalize_url("example.com"), "https://example.com/")

    def test_rejects_empty(self) -> None:
        self.assertIsNone(_normalize_url(""))
        self.assertIsNone(_normalize_url("N/A"))

    def test_rejects_invalid(self) -> None:
        self.assertIsNone(_normalize_url("not a url at all"))


class NormalizeResultTests(TestCase):
    def test_valid_dict(self) -> None:
        raw = {"title": "Hello", "href": "https://example.com", "body": "Snippet"}
        result = _normalize_result(raw, "Test")
        assert result is not None
        self.assertEqual(result.title, "Hello")
        self.assertEqual(str(result.url), "https://example.com/")
        self.assertEqual(result.provider, "Test")

    def test_missing_title_returns_none(self) -> None:
        raw = {"href": "https://example.com"}
        self.assertIsNone(_normalize_result(raw, "Test"))

    def test_missing_url_returns_none(self) -> None:
        raw = {"title": "Hello"}
        self.assertIsNone(_normalize_result(raw, "Test"))


class DeduplicateTests(TestCase):
    def test_removes_duplicates(self) -> None:
        results = [
            ResearchSource(url="https://example.com", title="A", provider="test"),
            ResearchSource(url="https://example.com", title="B", provider="test"),
            ResearchSource(url="https://other.com", title="C", provider="test"),
        ]
        deduped = _deduplicate(results)
        self.assertEqual(len(deduped), 2)


class SearchCacheTests(TestCase):
    def setUp(self):
        from ai_research_agent.search_engine import _SEARCH_CACHE
        _SEARCH_CACHE.clear()

    def test_get_hit(self) -> None:
        cache = _SearchCache()
        cache.clear()
        results = [ResearchSource(url="https://example.com", title="A", provider="test")]
        cache.set("query", "provider", results)
        hit = cache.get("query", "provider")
        self.assertIsNotNone(hit)
        self.assertEqual(len(hit), 1)
        self.assertEqual(str(hit[0].url), "https://example.com/")

    def test_get_miss(self) -> None:
        cache = _SearchCache()
        cache.clear()
        self.assertIsNone(cache.get("query", "provider"))

    def test_ttl_expires(self) -> None:
        import time
        cache = _SearchCache(ttl_seconds=0)
        cache.set("q", "p", [ResearchSource(url="https://example.com", title="A", provider="test")])
        time.sleep(0.01)
        self.assertIsNone(cache.get("q", "p"))


class SearchAPITests(TestCase):
    def test_empty_query_returns_empty(self) -> None:
        self.assertEqual(search(""), [])
        self.assertEqual(search("   "), [])

    def test_unsupported_provider_raises(self) -> None:
        with self.assertRaises(ConfigurationError):
            search("test", provider="unknown")

    def test_serper_without_key_raises(self) -> None:
        with self.assertRaises(ConfigurationError):
            search("test", provider="serper")

    @patch("ai_research_agent.search_engine._search_duckduckgo")
    def test_caches_results(self, mock_search) -> None:
        mock_search.return_value = [ResearchSource(url="https://example.com", title="A", provider="test")]
        # Clear cache state
        from ai_research_agent.search_engine import _SEARCH_CACHE
        _SEARCH_CACHE.clear()

        first = search("cached query", provider="duckduckgo", use_cache=True)
        second = search("cached query", provider="duckduckgo", use_cache=True)
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        mock_search.assert_called_once()

    @patch("ai_research_agent.search_engine._search_duckduckgo")
    def test_retry_on_failure(self, mock_search) -> None:
        mock_search.side_effect = WorkflowError("timeout")
        with self.assertRaises(WorkflowError):
            search("fail", provider="duckduckgo", max_attempts=2)
        self.assertEqual(mock_search.call_count, 2)

    @patch("ai_research_agent.search_engine._search_duckduckgo")
    def test_no_retry_on_non_retryable(self, mock_search) -> None:
        mock_search.side_effect = WorkflowError("bad request")
        with self.assertRaises(WorkflowError):
            search("fail", provider="duckduckgo", max_attempts=3)
        self.assertEqual(mock_search.call_count, 1)
