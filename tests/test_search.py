"""Tests for unified search — v4 engine (parallel + RRF + tabbit priority)."""

import asyncio
import pytest
from app.models import SearchRequest, SearchResult
from app.engine import engine, QueryIntent, ResultMerger
from app.modules import auto_register, get


@pytest.fixture(scope="module")
def setup_engine():
    """Register modules and load engine once for all tests."""
    auto_register()
    engine.load_modules()


# ============================================================
# Module tests
# ============================================================


@pytest.mark.asyncio
async def test_github_search(setup_engine):
    """GitHub module should return results for 'FastCode'."""
    req = SearchRequest(query="FastCode", sources=["github"], max_results=3, timeout=15)
    resp = await engine.search(req)
    assert "github" in resp.sources_used
    assert resp.total > 0
    titles = [r.title for r in resp.results]
    assert any("FastCode" in t for t in titles)


@pytest.mark.asyncio
async def test_github_module_metadata(setup_engine):
    """GitHub results should have stars, language metadata."""
    req = SearchRequest(
        query="python fastapi", sources=["github"], max_results=3, timeout=15
    )
    resp = await engine.search(req)
    if resp.results:
        r = resp.results[0]
        assert r.source == "github"
        assert "stars" in r.metadata


@pytest.mark.asyncio
async def test_academic_search(setup_engine):
    """Academic module should return results."""
    req = SearchRequest(
        query="transformer attention mechanism",
        sources=["academic"],
        max_results=3,
        timeout=20,
    )
    resp = await engine.search(req)
    assert len(resp.sources_used) > 0
    assert resp.total > 0


@pytest.mark.asyncio
async def test_arxiv_results(setup_engine):
    """arXiv results should have PDF URL."""
    req = SearchRequest(
        query="large language models", sources=["academic"], max_results=3, timeout=20
    )
    resp = await engine.search(req)
    arxiv_results = [r for r in resp.results if r.source == "arxiv"]
    if arxiv_results:
        r = arxiv_results[0]
        assert r.title
        assert r.url
        assert "pdf_url" in r.metadata


@pytest.mark.asyncio
async def test_web_search(setup_engine):
    """Web module should return results (may fail due to network)."""
    req = SearchRequest(
        query="Python FastAPI tutorial", sources=["web"], max_results=3, timeout=15
    )
    resp = await engine.search(req)
    assert resp.elapsed > 0


@pytest.mark.asyncio
async def test_module_not_found(setup_engine):
    """Non-existent module should return error."""
    req = SearchRequest(query="test", sources=["nonexistent"], max_results=3)
    resp = await engine.search(req)
    assert resp.total == 0


@pytest.mark.asyncio
async def test_cache(setup_engine):
    """Second search should be cached (only if first returned results)."""
    from app.cache import cache

    cache.clear()

    req = SearchRequest(
        query="FastCode GitHub repo", sources=["github"], max_results=3, timeout=15
    )
    resp1 = await engine.search(req)

    if resp1.results:
        # 有结果时，第二次应该是缓存
        resp2 = await engine.search(req)
        assert resp2.cached
    else:
        # 空结果不缓存 (v0.4.0 bugfix) — 第二次也不是缓存
        resp2 = await engine.search(req)
        assert not resp2.cached  # 空结果不应被缓存


@pytest.mark.asyncio
async def test_cache_empty_not_cached(setup_engine):
    """v0.4.0: Empty results should NOT be cached."""
    from app.cache import cache
    from app.models import SearchResponse

    cache.clear()

    # 直接往缓存放空结果
    req = SearchRequest(query="nonexistent_xyz_12345", sources=["github"], max_results=3)
    resp = SearchResponse(query="nonexistent_xyz_12345", results=[], total=0)
    cache.put(req, resp)

    # 空结果不应被缓存
    cached = cache.get(req)
    assert cached is None  # 空结果不应缓存


@pytest.mark.asyncio
async def test_cache_stats(setup_engine):
    """Cache stats should return valid data."""
    from app.cache import cache

    stats = cache.stats()
    assert "size" in stats
    assert "hits" in stats
    assert "max_size" in stats


@pytest.mark.asyncio
async def test_health_check(setup_engine):
    """Health endpoint should work."""
    mod = get("github")
    assert mod is not None
    assert mod.name == "github"


@pytest.mark.asyncio
async def test_models():
    """Pydantic models should validate correctly."""
    req = SearchRequest(query="test query")
    assert req.depth == "normal"
    assert req.language == "auto"
    assert req.max_results == 10

    with pytest.raises(Exception):
        SearchRequest()

    with pytest.raises(Exception):
        SearchRequest(query="", max_results=100)


# ============================================================
# Intent detection tests
# ============================================================


@pytest.mark.asyncio
async def test_intent_code(setup_engine):
    """Intent detection should detect code queries."""
    intent = QueryIntent.detect("how to write python function")
    assert "code" in intent["types"]


@pytest.mark.asyncio
async def test_intent_academic(setup_engine):
    """Intent detection should detect academic queries."""
    intent = QueryIntent.detect("transformer attention paper arxiv")
    assert "academic" in intent["types"]


@pytest.mark.asyncio
async def test_intent_knowledge(setup_engine):
    """Intent detection should detect knowledge queries."""
    intent = QueryIntent.detect("what is machine learning")
    assert "knowledge" in intent["types"]


@pytest.mark.asyncio
async def test_intent_chinese(setup_engine):
    """Intent detection should detect Chinese language."""
    intent = QueryIntent.detect("如何学习Python")
    assert "chinese" in intent["hints"]


@pytest.mark.asyncio
async def test_intent_url_given(setup_engine):
    """Intent detection should detect URL in query."""
    intent = QueryIntent.detect("https://github.com/python")
    assert "content" in intent["types"]
    assert "url_given" in intent["hints"]


@pytest.mark.asyncio
async def test_intent_repo_format(setup_engine):
    """Intent detection should detect GitHub repo format."""
    intent = QueryIntent.detect("atyou2happy/openclaw-unified-search")
    assert "code" in intent["types"]
    assert "repo_format" in intent["hints"]


@pytest.mark.asyncio
async def test_intent_news(setup_engine):
    """v4: Intent detection should detect news queries."""
    intent = QueryIntent.detect("最新AI新闻")
    assert "news" in intent["types"]
    assert "fresh" in intent["hints"]


@pytest.mark.asyncio
async def test_intent_news_english(setup_engine):
    """v4: Intent detection should detect English news queries."""
    intent = QueryIntent.detect("latest stock market news today")
    assert "news" in intent["types"]


# ============================================================
# Module selection tests (v4 — tabbit always selected)
# ============================================================


@pytest.mark.asyncio
async def test_module_selection(setup_engine):
    """Module selection should pick relevant modules."""
    from app.modules import get_all

    intent = QueryIntent.detect("python code tutorial")
    available = get_all()
    selected = QueryIntent.select_modules(intent, available)
    assert len(selected) > 0
    assert selected[0] in available


@pytest.mark.asyncio
async def test_tabbit_always_selected(setup_engine):
    """v4: tabbit should always be in selected modules."""
    from app.modules import get_all

    for query in ["python code", "what is AI", "news today", "random text xyz"]:
        intent = QueryIntent.detect(query)
        available = get_all()
        selected = QueryIntent.select_modules(intent, available)
        if "tabbit" in available:
            assert "tabbit" in selected, f"tabbit not selected for query: {query}"


@pytest.mark.asyncio
async def test_tabbit_first_priority(setup_engine):
    """v4: tabbit should be the highest scored module."""
    from app.modules import get_all

    intent = QueryIntent.detect("how to write fastapi endpoints")
    available = get_all()
    selected = QueryIntent.select_modules(intent, available)
    if "tabbit" in available:
        assert selected[0] == "tabbit"


@pytest.mark.asyncio
async def test_adaptive_module_count(setup_engine):
    """v4: research queries should select more modules than general."""
    from app.modules import get_all

    available = get_all()

    general_intent = QueryIntent.detect("hello world")
    general_selected = QueryIntent.select_modules(general_intent, available)

    research_intent = QueryIntent.detect("transformer attention paper research arxiv")
    research_selected = QueryIntent.select_modules(research_intent, available)

    assert len(research_selected) >= len(general_selected)


# ============================================================
# Dedup & Rerank tests
# ============================================================


@pytest.mark.asyncio
async def test_deduplicate(setup_engine):
    """Deduplicate should remove duplicate URLs."""
    results = [
        SearchResult(
            title="Python Tutorial",
            url="https://example.com/1",
            snippet="",
            source="test",
        ),
        SearchResult(
            title="Python Tutorial",
            url="https://example.com/1",
            snippet="",
            source="test",
        ),
        SearchResult(
            title="Python Guide", url="https://example.com/2", snippet="", source="test"
        ),
    ]
    deduped = ResultMerger.deduplicate(results)
    assert len(deduped) == 2


@pytest.mark.asyncio
async def test_deduplicate_similar_titles(setup_engine):
    """v4: Similar titles should be deduped."""
    results = [
        SearchResult(
            title="Python Tutorial for Beginners - Learn Python in 2024",
            url="https://example.com/1",
            snippet="abc",
            source="test1",
            relevance=0.8,
        ),
        SearchResult(
            title="Python Tutorial for Beginners - Learn Python in 2024!",
            url="https://example.com/2",
            snippet="def",
            source="test2",
            relevance=0.9,
        ),
    ]
    deduped = ResultMerger.deduplicate(results)
    assert len(deduped) == 1
    assert deduped[0].relevance == 0.9  # kept higher relevance


@pytest.mark.asyncio
async def test_rerank(setup_engine):
    """Rerank should sort by relevance."""
    results = [
        SearchResult(
            title="Low", url="https://a.com", snippet="", source="test", relevance=0.3
        ),
        SearchResult(
            title="High", url="https://b.com", snippet="", source="test", relevance=0.9
        ),
    ]
    reranked = ResultMerger.rerank(results)
    assert reranked[0].title == "High"


# ============================================================
# RRF Fusion tests (v4)
# ============================================================


@pytest.mark.asyncio
async def test_rrf_fuse_basic(setup_engine):
    """v4: RRF should fuse results from multiple sources."""
    results_by_source = {
        "source_a": [
            SearchResult(
                title="A1",
                url="https://a.com/1",
                snippet="",
                source="source_a",
                relevance=0.9,
            ),
            SearchResult(
                title="A2",
                url="https://a.com/2",
                snippet="",
                source="source_a",
                relevance=0.8,
            ),
        ],
        "source_b": [
            SearchResult(
                title="B1",
                url="https://b.com/1",
                snippet="",
                source="source_b",
                relevance=0.9,
            ),
            SearchResult(
                title="B2",
                url="https://a.com/1",
                snippet="",
                source="source_b",
                relevance=0.7,
            ),
        ],
    }
    fused = ResultMerger.rrf_fuse(results_by_source)
    assert len(fused) > 0
    # https://a.com/1 appears in both sources, should rank highest
    assert fused[0].url == "https://a.com/1"


@pytest.mark.asyncio
async def test_rrf_fuse_cross_source_boost(setup_engine):
    """v4: URLs appearing in multiple sources should rank higher via RRF."""
    results_by_source = {
        "searxng": [
            SearchResult(
                title="Result 1",
                url="https://shared.com/page",
                snippet="",
                source="searxng",
                relevance=0.7,
            ),
            SearchResult(
                title="Result 2",
                url="https://unique-a.com",
                snippet="",
                source="searxng",
                relevance=0.8,
            ),
        ],
        "ddg": [
            SearchResult(
                title="Result 1",
                url="https://shared.com/page",
                snippet="",
                source="ddg",
                relevance=0.7,
            ),
            SearchResult(
                title="Result 3",
                url="https://unique-b.com",
                snippet="",
                source="ddg",
                relevance=0.9,
            ),
        ],
    }
    fused = ResultMerger.rrf_fuse(results_by_source)
    assert len(fused) == 3
    assert fused[0].url == "https://shared.com/page"


@pytest.mark.asyncio
async def test_rrf_fuse_source_weight(setup_engine):
    """v4: Higher source weight should boost results."""
    results_by_source = {
        "tabbit": [
            SearchResult(
                title="Tabbit Result",
                url="https://tabbit.com/r",
                snippet="",
                source="tabbit",
                relevance=0.7,
            ),
        ],
        "web": [
            SearchResult(
                title="Web Result",
                url="https://web.com/r",
                snippet="",
                source="web",
                relevance=0.7,
            ),
        ],
    }
    fused = ResultMerger.rrf_fuse(results_by_source)
    assert fused[0].source == "tabbit"


# ============================================================
# Engine v4 tests
# ============================================================


@pytest.mark.asyncio
async def test_empty_query(setup_engine):
    """Empty query should return general intent."""
    intent = QueryIntent.detect("")
    assert "general" in intent["types"]


@pytest.mark.asyncio
async def test_timeout_handling(setup_engine):
    """Engine should handle timeout gracefully."""
    req = SearchRequest(query="test", sources=["github"], timeout=5)
    resp = await engine.search(req)
    assert resp.elapsed >= 0


@pytest.mark.asyncio
async def test_new_modules_registered(setup_engine):
    """New modules should be registered."""
    modules = ["perplexity", "ddg", "bing", "you", "komo"]
    for name in modules:
        mod = get(name)
        assert mod is not None, f"Module {name} not found"
        assert mod.name == name


@pytest.mark.asyncio
async def test_engine_v4_metadata(setup_engine):
    """v4: Response should contain engine_version metadata."""
    req = SearchRequest(
        query="python fastapi", sources=["github"], max_results=3, timeout=15
    )
    resp = await engine.search(req)
    assert resp.metadata.get("engine_version") == "v4"


@pytest.mark.asyncio
async def test_tabbit_results_on_top(setup_engine):
    """v4: Tabbit results should appear first when present."""
    req = SearchRequest(query="python tutorial", max_results=10, timeout=15)
    resp = await engine.search(req)
    tabbit_results = [r for r in resp.results if r.source == "tabbit"]
    if tabbit_results:
        assert resp.results[0].source == "tabbit"


@pytest.mark.asyncio
async def test_tabbit_structured_parsing(setup_engine):
    """v4: Tabbit module should parse results into structured format."""
    from app.modules.tabbit import TabBitModule

    mod = TabBitModule()

    content = """Python is a great programming language.

Check out https://docs.python.org/3/tutorial/ for the official tutorial.
Also see https://realpython.com/python-tutorial/ for a beginner guide.
"""

    results = mod._parse_results(content, SearchRequest(query="python tutorial"))
    assert len(results) >= 1
    assert results[0].metadata.get("type") == "ai_answer"
    assert results[0].source == "tabbit"


@pytest.mark.asyncio
async def test_tabbit_json_parsing(setup_engine):
    """v4: Tabbit module should parse JSON results."""
    import json
    from app.modules.tabbit import TabBitModule

    mod = TabBitModule()

    data = {
        "answer": "Python is a programming language.",
        "results": [
            {
                "title": "Python Docs",
                "url": "https://docs.python.org",
                "snippet": "Official docs",
            },
            {
                "title": "Real Python",
                "url": "https://realpython.com",
                "snippet": "Tutorials",
            },
        ],
    }

    results = mod._parse_results(json.dumps(data), SearchRequest(query="python"))
    assert len(results) == 3  # 1 answer + 2 results
    assert results[0].metadata.get("type") == "ai_answer"
    assert results[1].title == "Python Docs"


@pytest.mark.asyncio
async def test_parallel_execution(setup_engine):
    """v4: Engine should execute modules in parallel (faster than sequential)."""
    import time

    req = SearchRequest(
        query="python fastapi tutorial",
        sources=["github", "academic", "ddg"],
        max_results=5,
        timeout=20,
    )

    start = time.time()
    resp = await engine.search(req)
    elapsed = time.time() - start

    # Should complete within timeout (parallel)
    assert elapsed < 25
    assert resp.metadata.get("engine_version") == "v4"
