"""Pure unit tests — no network, no I/O.

Tests for models, cache, intent detection, RRF fusion, and config.
These tests run in <1s and should always pass regardless of network.
"""

import pytest
from app.models import SearchRequest, SearchResponse, SearchResult
from app.cache import SearchCache
from app.engine.intent import QueryIntent
from app.engine.merger import ResultMerger
from app.engine.availability import AvailabilityCache
from app.config import Config


# ============================================================
# Models
# ============================================================


class TestModels:
    """Tests for Pydantic data models."""

    def test_search_request_defaults(self):
        req = SearchRequest(query="test")
        assert req.max_results == 10
        assert req.timeout == 30
        assert req.depth == "normal"
        assert req.language == "auto"
        assert req.sources == []

    def test_search_request_validation_empty_query(self):
        with pytest.raises(Exception):
            SearchRequest()

    def test_search_request_validation_empty_string(self):
        with pytest.raises(Exception):
            SearchRequest(query="")

    def test_search_request_validation_max_results(self):
        with pytest.raises(Exception):
            SearchRequest(query="test", max_results=100)

    def test_search_request_validation_depth(self):
        with pytest.raises(Exception):
            SearchRequest(query="test", depth="invalid")

    def test_search_result_defaults(self):
        r = SearchResult(source="test")
        assert r.title == ""
        assert r.url == ""
        assert r.relevance == 0.0
        assert r.content is None
        assert r.metadata == {}

    def test_search_response_defaults(self):
        resp = SearchResponse(query="test")
        assert resp.results == []
        assert resp.total == 0
        assert resp.elapsed == 0.0
        assert resp.cached is False


# ============================================================
# Cache
# ============================================================


class TestCache:
    """Tests for LRU search cache."""

    def test_put_and_get(self):
        cache = SearchCache(max_size=10, ttl=60)
        req = SearchRequest(query="python")
        resp = SearchResponse(query="python", results=[
            SearchResult(title="Python", url="https://python.org", source="test")
        ], total=1)
        cache.put(req, resp)
        cached = cache.get(req)
        assert cached is not None
        assert cached.cached is True
        assert cached.total == 1

    def test_empty_results_not_cached(self):
        cache = SearchCache(max_size=10, ttl=60)
        req = SearchRequest(query="empty")
        resp = SearchResponse(query="empty", results=[], total=0)
        cache.put(req, resp)
        assert cache.get(req) is None

    def test_cache_miss(self):
        cache = SearchCache(max_size=10, ttl=60)
        req = SearchRequest(query="miss")
        assert cache.get(req) is None

    def test_cache_stats(self):
        cache = SearchCache(max_size=10, ttl=60)
        stats = cache.stats()
        assert "size" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "max_size" in stats
        assert "hit_rate" in stats
        assert stats["max_size"] == 10

    def test_cache_clear(self):
        cache = SearchCache(max_size=10, ttl=60)
        req = SearchRequest(query="test")
        resp = SearchResponse(query="test", results=[
            SearchResult(title="T", url="https://t.com", source="s")
        ], total=1)
        cache.put(req, resp)
        count = cache.clear()
        assert count == 1
        assert cache.get(req) is None

    def test_cache_eviction(self):
        cache = SearchCache(max_size=3, ttl=60)
        for i in range(5):
            req = SearchRequest(query=f"q{i}")
            resp = SearchResponse(query=f"q{i}", results=[
                SearchResult(title=f"T{i}", url=f"https://{i}.com", source="s")
            ], total=1)
            cache.put(req, resp)
        stats = cache.stats()
        assert stats["size"] <= 3


# ============================================================
# Intent Detection
# ============================================================


class TestIntent:
    """Tests for query intent detection (pure logic, no network)."""

    def test_code_intent(self):
        intent = QueryIntent.detect("how to write python function")
        assert "code" in intent["types"]

    def test_academic_intent(self):
        intent = QueryIntent.detect("transformer attention paper arxiv")
        assert "academic" in intent["types"]

    def test_knowledge_intent(self):
        intent = QueryIntent.detect("what is machine learning")
        assert "knowledge" in intent["types"]

    def test_news_intent_chinese(self):
        intent = QueryIntent.detect("最新AI新闻")
        assert "news" in intent["types"]
        assert "fresh" in intent["hints"]

    def test_news_intent_english(self):
        intent = QueryIntent.detect("latest stock market news today")
        assert "news" in intent["types"]

    def test_url_intent(self):
        intent = QueryIntent.detect("https://github.com/python")
        assert "content" in intent["types"]
        assert "url_given" in intent["hints"]

    def test_repo_format(self):
        intent = QueryIntent.detect("atyou2happy/openclaw-unified-search")
        assert "code" in intent["types"]
        assert "repo_format" in intent["hints"]

    def test_chinese_hint(self):
        intent = QueryIntent.detect("如何学习Python")
        assert "chinese" in intent["hints"]

    def test_empty_query(self):
        intent = QueryIntent.detect("")
        assert "general" in intent["types"]


# ============================================================
# RRF Fusion & Merger
# ============================================================


class TestMerger:
    """Tests for result dedup, RRF fusion, and reranking."""

    def test_deduplicate_urls(self):
        results = [
            SearchResult(title="A", url="https://example.com/1", source="s1"),
            SearchResult(title="A", url="https://example.com/1", source="s1"),
            SearchResult(title="B", url="https://example.com/2", source="s1"),
        ]
        deduped = ResultMerger.deduplicate(results)
        assert len(deduped) == 2

    def test_deduplicate_similar_titles(self):
        results = [
            SearchResult(title="Python Tutorial 2024", url="https://a.com", snippet="abc",
                         source="s1", relevance=0.8),
            SearchResult(title="Python Tutorial 2024!", url="https://b.com", snippet="def",
                         source="s2", relevance=0.9),
        ]
        deduped = ResultMerger.deduplicate(results)
        assert len(deduped) == 1
        assert deduped[0].relevance == 0.9

    def test_rerank_by_relevance(self):
        results = [
            SearchResult(title="Low", url="https://a.com", source="s", relevance=0.3),
            SearchResult(title="High", url="https://b.com", source="s", relevance=0.9),
        ]
        reranked = ResultMerger.rerank(results)
        assert reranked[0].title == "High"

    def test_rerank_keyword_match(self):
        results = [
            SearchResult(title="Unrelated", url="https://a.com", source="s", relevance=0.5),
            SearchResult(title="Python FastAPI Tutorial", url="https://b.com", source="s", relevance=0.5),
        ]
        reranked = ResultMerger.rerank(results, query="python fastapi")
        assert reranked[0].title == "Python FastAPI Tutorial"

    def test_rrf_fuse_basic(self):
        by_source = {
            "a": [
                SearchResult(title="A1", url="https://a.com/1", source="a", relevance=0.9),
                SearchResult(title="A2", url="https://a.com/2", source="a", relevance=0.8),
            ],
            "b": [
                SearchResult(title="B1", url="https://b.com/1", source="b", relevance=0.9),
                SearchResult(title="B2", url="https://a.com/1", source="b", relevance=0.7),
            ],
        }
        fused = ResultMerger.rrf_fuse(by_source)
        assert len(fused) > 0
        assert fused[0].url == "https://a.com/1"  # Cross-source boost

    def test_rrf_fuse_source_weight(self):
        by_source = {
            "tabbit": [SearchResult(title="T", url="https://t.com/r", source="tabbit", relevance=0.7)],
            "web": [SearchResult(title="W", url="https://w.com/r", source="web", relevance=0.7)],
        }
        fused = ResultMerger.rrf_fuse(by_source)
        assert fused[0].source == "tabbit"  # Higher weight

    def test_rrf_empty_input(self):
        assert ResultMerger.rrf_fuse({}) == []


# ============================================================
# Availability Cache
# ============================================================


class TestAvailabilityCache:
    """Tests for module availability TTL cache."""

    def test_cache_miss(self):
        cache = AvailabilityCache(ttl=60)
        assert cache.get("nonexistent") is None

    def test_cache_set_and_get(self):
        cache = AvailabilityCache(ttl=60)
        cache.set("github", True)
        assert cache.get("github") is True

    def test_cache_invalidate_single(self):
        cache = AvailabilityCache(ttl=60)
        cache.set("github", True)
        cache.invalidate("github")
        assert cache.get("github") is None

    def test_cache_invalidate_all(self):
        cache = AvailabilityCache(ttl=60)
        cache.set("a", True)
        cache.set("b", False)
        cache.invalidate()
        assert cache.get("a") is None
        assert cache.get("b") is None


# ============================================================
# Config
# ============================================================


class TestConfig:
    """Tests for configuration management."""

    def test_defaults(self):
        assert Config.HOST == "127.0.0.1"
        assert Config.PORT == 8900
        assert Config.DEBUG is False
        assert Config.DEFAULT_TIMEOUT == 30

    def test_get_proxy_fallback(self):
        # get_proxy should return class default when no env set
        proxy = Config.get_proxy()
        # Result depends on env, just verify it doesn't crash
        assert proxy is None or isinstance(proxy, str)
