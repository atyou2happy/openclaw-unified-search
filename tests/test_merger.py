"""Tests for result deduplication, RRF fusion, and reranking."""

import pytest
from app.models import SearchResult
from app.engine.merger import ResultMerger


@pytest.mark.asyncio
async def test_deduplicate():
    results = [
        SearchResult(title="A", url="https://example.com/1", snippet="", source="s1"),
        SearchResult(title="A", url="https://example.com/1", snippet="", source="s1"),
        SearchResult(title="B", url="https://example.com/2", snippet="", source="s1"),
    ]
    deduped = ResultMerger.deduplicate(results)
    assert len(deduped) == 2


@pytest.mark.asyncio
async def test_deduplicate_similar_titles():
    results = [
        SearchResult(
            title="Python Tutorial for Beginners - Learn Python in 2024",
            url="https://example.com/1", snippet="abc", source="s1", relevance=0.8,
        ),
        SearchResult(
            title="Python Tutorial for Beginners - Learn Python in 2024!",
            url="https://example.com/2", snippet="def", source="s2", relevance=0.9,
        ),
    ]
    deduped = ResultMerger.deduplicate(results)
    assert len(deduped) == 1
    assert deduped[0].relevance == 0.9


@pytest.mark.asyncio
async def test_rerank():
    results = [
        SearchResult(title="Low", url="https://a.com", snippet="", source="s", relevance=0.3),
        SearchResult(title="High", url="https://b.com", snippet="", source="s", relevance=0.9),
    ]
    reranked = ResultMerger.rerank(results)
    assert reranked[0].title == "High"


@pytest.mark.asyncio
async def test_rrf_fuse_basic():
    results_by_source = {
        "a": [
            SearchResult(title="A1", url="https://a.com/1", snippet="", source="a", relevance=0.9),
            SearchResult(title="A2", url="https://a.com/2", snippet="", source="a", relevance=0.8),
        ],
        "b": [
            SearchResult(title="B1", url="https://b.com/1", snippet="", source="b", relevance=0.9),
            SearchResult(title="B2", url="https://a.com/1", snippet="", source="b", relevance=0.7),
        ],
    }
    fused = ResultMerger.rrf_fuse(results_by_source)
    assert len(fused) > 0
    assert fused[0].url == "https://a.com/1"


@pytest.mark.asyncio
async def test_rrf_fuse_cross_source_boost():
    results_by_source = {
        "searxng": [
            SearchResult(title="R1", url="https://shared.com/p", snippet="", source="searxng", relevance=0.7),
            SearchResult(title="R2", url="https://unique-a.com", snippet="", source="searxng", relevance=0.8),
        ],
        "ddg": [
            SearchResult(title="R1", url="https://shared.com/p", snippet="", source="ddg", relevance=0.7),
            SearchResult(title="R3", url="https://unique-b.com", snippet="", source="ddg", relevance=0.9),
        ],
    }
    fused = ResultMerger.rrf_fuse(results_by_source)
    assert len(fused) == 3
    assert fused[0].url == "https://shared.com/p"


@pytest.mark.asyncio
async def test_rrf_fuse_source_weight():
    results_by_source = {
        "tabbit": [
            SearchResult(title="T", url="https://t.com/r", snippet="", source="tabbit", relevance=0.7),
        ],
        "web": [
            SearchResult(title="W", url="https://w.com/r", snippet="", source="web", relevance=0.7),
        ],
    }
    fused = ResultMerger.rrf_fuse(results_by_source)
    assert fused[0].source == "tabbit"


@pytest.mark.asyncio
async def test_rerank_keyword_match():
    """Rerank should boost results whose titles match query keywords."""
    results = [
        SearchResult(title="Unrelated Topic", url="https://a.com", snippet="", source="s", relevance=0.5),
        SearchResult(title="Python FastAPI Tutorial", url="https://b.com", snippet="", source="s", relevance=0.5),
    ]
    reranked = ResultMerger.rerank(results, query="python fastapi")
    assert reranked[0].title == "Python FastAPI Tutorial"
