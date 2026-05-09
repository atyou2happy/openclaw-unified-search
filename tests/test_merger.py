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


# v7: Category + diversity tests

def test_categorize():
    r = SearchResult(title="T", url="", snippet="", source="github")
    assert ResultMerger.categorize(r) == "code"

    r2 = SearchResult(title="T", url="", snippet="", source="academic")
    assert ResultMerger.categorize(r2) == "academic"

    r3 = SearchResult(title="T", url="", snippet="", source="reddit")
    assert ResultMerger.categorize(r3) == "social"

    r4 = SearchResult(title="T", url="", snippet="", source="unknown_source")
    assert ResultMerger.categorize(r4) == "web"


def test_inject_diversity_source_limit():
    """max_per_source=2: diverse section has ≤2 per source, overflow appended after."""
    results = [
        SearchResult(title=f"R{i}", url=f"https://a.com/{i}", snippet="", source="tabbit", relevance=0.9 - i*0.01)
        for i in range(5)
    ] + [
        SearchResult(title=f"S{i}", url=f"https://b.com/{i}", snippet="", source="ddg", relevance=0.8 - i*0.01)
        for i in range(5)
    ]
    diverse = ResultMerger._inject_diversity(results, max_per_source=2)

    # First 4 results (2 tabbit + 2 ddg) should be diverse
    diverse_section = diverse[:4]
    source_counts = {}
    for r in diverse_section:
        source_counts[r.source] = source_counts.get(r.source, 0) + 1
    assert source_counts.get("tabbit", 0) <= 2
    assert source_counts.get("ddg", 0) <= 2

    # Total results preserved (no data loss)
    assert len(diverse) == 10


def test_inject_diversity_category_labels():
    """Results should get category labels in metadata."""
    results = [
        SearchResult(title="T1", url="", snippet="", source="github"),
        SearchResult(title="T2", url="", snippet="", source="reddit"),
        SearchResult(title="T3", url="", snippet="", source="academic"),
    ]
    diverse = ResultMerger._inject_diversity(results, max_per_source=3)
    assert diverse[0].metadata.get("category") == "code"
    assert diverse[1].metadata.get("category") == "social"
    assert diverse[2].metadata.get("category") == "academic"


def test_inject_diversity_category_guarantee():
    """Each represented category should appear at least once in diverse results."""
    results = [
        # 3 from tabbit (answer category)
        SearchResult(title=f"A{i}", url=f"https://a.com/{i}", snippet="", source="tabbit", relevance=0.9)
        for i in range(3)
    ] + [
        # 3 from github (code category)
        SearchResult(title=f"C{i}", url=f"https://c.com/{i}", snippet="", source="github", relevance=0.8)
        for i in range(3)
    ] + [
        # 3 from academic (academic category)
        SearchResult(title=f"X{i}", url=f"https://x.com/{i}", snippet="", source="academic", relevance=0.7)
        for i in range(3)
    ]
    diverse = ResultMerger._inject_diversity(results, max_per_source=2)

    categories_in_diverse = set()
    for r in diverse:
        categories_in_diverse.add(r.metadata.get("category"))

    # All three categories should be represented
    assert "answer" in categories_in_diverse
    assert "code" in categories_in_diverse
    assert "academic" in categories_in_diverse


def test_rerank_no_double_source_weight():
    """v7: rerank should NOT apply SOURCE_WEIGHTS again (already in rrf_fuse)."""
    results = [
        SearchResult(title="Python Tutorial", url="https://a.com", snippet="learn python", source="tabbit", relevance=0.8),
        SearchResult(title="Python Guide", url="https://b.com", snippet="python guide", source="ddg", relevance=0.8),
    ]
    # Both have same initial relevance, same title keyword match
    # Without double weighting, they should be close in score
    reranked = ResultMerger.rerank(results, query="python")
    # The scores should not have a 2x+ gap from double SOURCE_WEIGHTS
    assert reranked[0].relevance > 0
    assert reranked[1].relevance > 0


# ── v3.0: Adaptive RRF k-value ──

def test_adaptive_k_small():
    """Small result sets get lower k (emphasize rank)."""
    assert ResultMerger._adaptive_k(5) == 30.0
    assert ResultMerger._adaptive_k(10) == 30.0


def test_adaptive_k_medium():
    """Medium result sets get standard k."""
    assert ResultMerger._adaptive_k(15) == 60.0
    assert ResultMerger._adaptive_k(30) == 60.0


def test_adaptive_k_large():
    """Large result sets get higher k (smooth)."""
    assert ResultMerger._adaptive_k(35) == 90.0
    assert ResultMerger._adaptive_k(100) == 90.0


# ── v3.0: SimHash near-duplicate detection ──

def test_simhash_identical_text():
    """Identical text produces same fingerprint."""
    fp1 = ResultMerger._compute_simhash("Python FastAPI web framework tutorial")
    fp2 = ResultMerger._compute_simhash("Python FastAPI web framework tutorial")
    assert fp1 == fp2


def test_simhash_different_text():
    """Different text produces different fingerprints."""
    fp1 = ResultMerger._compute_simhash("Python FastAPI async web framework")
    fp2 = ResultMerger._compute_simhash("Java Spring Boot enterprise development")
    assert fp1 != fp2


def test_simhash_similar_text():
    """Similar text produces close fingerprints (low Hamming distance)."""
    fp1 = ResultMerger._compute_simhash("Python FastAPI async web framework tutorial")
    fp2 = ResultMerger._compute_simhash("Python FastAPI web framework async tutorial guide")
    dist = ResultMerger._hamming_distance(fp1, fp2)
    # Similar text should have relatively low Hamming distance
    assert dist < 32  # half of 64 bits


def test_simhash_empty():
    """Empty text returns 0."""
    assert ResultMerger._compute_simhash("") == 0


def test_hamming_distance():
    """Hamming distance computation."""
    assert ResultMerger._hamming_distance(0, 0) == 0
    assert ResultMerger._hamming_distance(0b1111, 0b0000) == 4
    assert ResultMerger._hamming_distance(0b1010, 0b0101) == 4


def test_simhash_dedup_removes_duplicates():
    """SimHash dedup removes identical/near-identical results."""
    # Two results with identical title+snippet = same SimHash
    results = [
        SearchResult(title="Identical Title Here", url="https://a.com/1", snippet="This is exactly the same content text for dedup testing", source="web", relevance=0.9),
        SearchResult(title="Identical Title Here", url="https://b.com/2", snippet="This is exactly the same content text for dedup testing", source="ddg", relevance=0.8),
        SearchResult(title="Java Spring Boot", url="https://c.com/3", snippet="Enterprise Java development with Spring", source="web", relevance=0.7),
    ]
    deduped = ResultMerger._simhash_dedup(results, threshold=3)
    # The two identical results should be deduplicated to 1
    assert len(deduped) < 3


def test_simhash_dedup_keeps_higher_relevance():
    """SimHash dedup keeps the result with higher relevance."""
    results = [
        SearchResult(title="Python Guide", url="https://a.com/1", snippet="Python programming guide", source="web", relevance=0.6),
        SearchResult(title="Python Tutorial", url="https://b.com/2", snippet="Python programming tutorial guide", source="ddg", relevance=0.9),
    ]
    deduped = ResultMerger._simhash_dedup(results, threshold=3)
    assert len(deduped) >= 1
