"""Tests for QualityScorer — v2.0 multi-dimensional quality evaluation."""

import pytest
from datetime import datetime, timedelta

from app.models import SearchResult
from app.engine.quality_scorer import QualityScorer


def _make_result(
    title="Test Result",
    url="https://example.com/page",
    snippet="This is a test snippet with some content",
    source="test",
    relevance=0.7,
    content=None,
    timestamp=None,
) -> SearchResult:
    return SearchResult(
        title=title,
        url=url,
        snippet=snippet,
        source=source,
        relevance=relevance,
        content=content,
        timestamp=timestamp,
    )


class TestRelevanceScoring:
    """Relevance dimension scoring tests."""

    def test_exact_match_high_relevance(self):
        r = _make_result(title="Python async await tutorial")
        score, breakdown = QualityScorer.score(r, query="python async await")
        assert breakdown["relevance"] > 0.5

    def test_no_match_low_relevance(self):
        r = _make_result(title="Cooking recipes for beginners")
        score, breakdown = QualityScorer.score(r, query="python async await")
        assert breakdown["relevance"] < 0.5

    def test_partial_match_medium_relevance(self):
        r = _make_result(title="Python programming guide")
        score, breakdown = QualityScorer.score(r, query="python async await")
        assert 0.1 < breakdown["relevance"] < 0.8

    def test_empty_query_uses_module_relevance(self):
        r = _make_result(relevance=0.8)
        score, breakdown = QualityScorer.score(r, query="")
        assert breakdown["relevance"] == 0.8


class TestAuthorityScoring:
    """Authority dimension scoring tests."""

    def test_tier1_github(self):
        r = _make_result(url="https://github.com/python/cpython")
        score, breakdown = QualityScorer.score(r)
        assert breakdown["authority"] == 0.95

    def test_tier1_wikipedia(self):
        r = _make_result(url="https://en.wikipedia.org/wiki/Python")
        score, breakdown = QualityScorer.score(r)
        assert breakdown["authority"] == 0.95

    def test_tier2_devto(self):
        r = _make_result(url="https://dev.to/some-post")
        score, breakdown = QualityScorer.score(r)
        assert breakdown["authority"] == 0.80

    def test_tier2_subdomain(self):
        r = _make_result(url="https://docs.github.com/actions")
        score, breakdown = QualityScorer.score(r)
        assert breakdown["authority"] == 0.90

    def test_unknown_domain(self):
        r = _make_result(url="https://random-blog.xyz/post")
        score, breakdown = QualityScorer.score(r)
        assert breakdown["authority"] == 0.50

    def test_no_url(self):
        r = _make_result(url="")
        score, breakdown = QualityScorer.score(r)
        assert breakdown["authority"] == 0.30


class TestCompletenessScoring:
    """Completeness dimension scoring tests."""

    def test_full_result(self):
        r = _make_result(
            title="A" * 50,
            snippet="B" * 200,
            content="C" * 1000,
        )
        score, breakdown = QualityScorer.score(r)
        assert breakdown["completeness"] > 0.8

    def test_title_only(self):
        r = _make_result(title="Short", snippet="", content=None)
        score, breakdown = QualityScorer.score(r)
        assert breakdown["completeness"] < 0.4

    def test_no_content(self):
        r = _make_result(
            title="Python Guide",
            snippet="A good guide",
            content=None,
        )
        score, breakdown = QualityScorer.score(r)
        assert 0.1 < breakdown["completeness"] < 0.6


class TestTotalScore:
    """Total score and dimension weight tests."""

    def test_weights_sum_to_one(self):
        assert sum(QualityScorer.DIMENSION_WEIGHTS.values()) == pytest.approx(1.0)

    def test_high_quality_result(self):
        r = _make_result(
            title="Python async await comprehensive guide",
            url="https://docs.python.org/3/library/asyncio.html",
            snippet="Complete guide to async await in Python with examples",
            content="D" * 2000,
            relevance=0.9,
        )
        score, breakdown = QualityScorer.score(r, query="python async await")
        assert score > 0.6

    def test_low_quality_result(self):
        r = _make_result(
            title="",
            url="",
            snippet="",
            source="spam",
            relevance=0.1,
        )
        score, breakdown = QualityScorer.score(r, query="python async await")
        assert score < 0.4


class TestBatchScoring:
    """Batch scoring and sorting tests."""

    def test_batch_sorted_by_quality(self):
        results = [
            _make_result(title="Low relevance", relevance=0.2, url="https://random.com"),
            _make_result(
                title="Python async await guide",
                relevance=0.9,
                url="https://docs.python.org/async",
                snippet="Full guide",
                content="C" * 500,
            ),
            _make_result(
                title="Medium post",
                relevance=0.5,
                url="https://medium.com/post",
            ),
        ]
        scored = QualityScorer.score_batch(results, query="python async await")
        # Highest quality should be first
        assert scored[0][0].title == "Python async await guide"

    def test_batch_preserves_all_results(self):
        results = [_make_result(title=f"Result {i}") for i in range(5)]
        scored = QualityScorer.score_batch(results, query="test")
        assert len(scored) == 5
