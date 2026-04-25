"""Tests for search engine, modules, and cache."""

import json
import pytest
from app.models import SearchRequest, SearchResponse, SearchResult
from app.engine import engine
from app.modules import auto_register, get
from app.cache import cache


@pytest.fixture(scope="module")
def setup_engine():
    auto_register()
    engine.load_modules()


# ============================================================
# Module tests
# ============================================================


@pytest.mark.asyncio
async def test_github_search(setup_engine):
    req = SearchRequest(query="FastCode", sources=["github"], max_results=3, timeout=15)
    resp = await engine.search(req)
    assert "github" in resp.sources_used
    assert resp.total > 0


@pytest.mark.asyncio
async def test_github_module_metadata(setup_engine):
    req = SearchRequest(query="python fastapi", sources=["github"], max_results=3, timeout=15)
    resp = await engine.search(req)
    if resp.results:
        assert "stars" in resp.results[0].metadata


@pytest.mark.asyncio
async def test_academic_search(setup_engine):
    req = SearchRequest(
        query="transformer attention mechanism",
        sources=["academic"], max_results=3, timeout=20,
    )
    resp = await engine.search(req)
    assert len(resp.sources_used) > 0
    assert resp.total > 0


@pytest.mark.asyncio
async def test_arxiv_results(setup_engine):
    req = SearchRequest(query="large language models", sources=["academic"], max_results=3, timeout=20)
    resp = await engine.search(req)
    arxiv = [r for r in resp.results if r.source == "arxiv"]
    if arxiv:
        assert "pdf_url" in arxiv[0].metadata


@pytest.mark.asyncio
async def test_web_search(setup_engine):
    req = SearchRequest(query="Python FastAPI tutorial", sources=["web"], max_results=3, timeout=15)
    resp = await engine.search(req)
    assert resp.elapsed > 0


@pytest.mark.asyncio
async def test_module_not_found(setup_engine):
    req = SearchRequest(query="test", sources=["nonexistent"], max_results=3)
    resp = await engine.search(req)
    assert resp.total == 0


# ============================================================
# Cache tests
# ============================================================


@pytest.mark.asyncio
async def test_cache(setup_engine):
    cache.clear()
    req = SearchRequest(query="FastCode GitHub repo", sources=["github"], max_results=3, timeout=15)
    resp1 = await engine.search(req)
    if resp1.results:
        resp2 = await engine.search(req)
        assert resp2.cached
    else:
        resp2 = await engine.search(req)
        assert not resp2.cached


@pytest.mark.asyncio
async def test_cache_empty_not_cached(setup_engine):
    cache.clear()
    req = SearchRequest(query="nonexistent_xyz_12345", sources=["github"], max_results=3)
    resp = SearchResponse(query="nonexistent_xyz_12345", results=[], total=0)
    cache.put(req, resp)
    assert cache.get(req) is None


@pytest.mark.asyncio
async def test_cache_stats(setup_engine):
    stats = cache.stats()
    assert "size" in stats
    assert "hits" in stats
    assert "max_size" in stats


# ============================================================
# Engine tests
# ============================================================


@pytest.mark.asyncio
async def test_health_check(setup_engine):
    mod = get("github")
    assert mod is not None
    assert mod.name == "github"


@pytest.mark.asyncio
async def test_models():
    req = SearchRequest(query="test query")
    assert req.depth == "normal"
    assert req.language == "auto"
    with pytest.raises(Exception):
        SearchRequest()
    with pytest.raises(Exception):
        SearchRequest(query="", max_results=100)


@pytest.mark.asyncio
async def test_timeout_handling(setup_engine):
    req = SearchRequest(query="test", sources=["github"], timeout=5)
    resp = await engine.search(req)
    assert resp.elapsed >= 0


@pytest.mark.asyncio
async def test_new_modules_registered(setup_engine):
    for name in ["perplexity", "ddg", "bing", "you", "komo"]:
        mod = get(name)
        assert mod is not None, f"Module {name} not found"


@pytest.mark.asyncio
async def test_engine_v4_metadata(setup_engine):
    req = SearchRequest(query="python fastapi", sources=["github"], max_results=3, timeout=15)
    resp = await engine.search(req)
    assert resp.metadata.get("engine_version") == "v4"


@pytest.mark.asyncio
async def test_tabbit_results_on_top(setup_engine):
    req = SearchRequest(query="python tutorial", max_results=10, timeout=15)
    resp = await engine.search(req)
    tabbit = [r for r in resp.results if r.source == "tabbit"]
    if tabbit:
        assert resp.results[0].source == "tabbit"


@pytest.mark.asyncio
async def test_tabbit_structured_parsing(setup_engine):
    from app.modules.tabbit import TabBitModule
    mod = TabBitModule()
    content = (
        "Python is a great programming language.\n\n"
        "Check out https://docs.python.org/3/tutorial/ for the official tutorial.\n"
        "Also see https://realpython.com/python-tutorial/ for a beginner guide."
    )
    results = mod._parse_results(content, SearchRequest(query="python tutorial"))
    assert len(results) >= 1
    assert results[0].metadata.get("type") == "ai_answer"


@pytest.mark.asyncio
async def test_tabbit_json_parsing(setup_engine):
    from app.modules.tabbit import TabBitModule
    mod = TabBitModule()
    data = {
        "answer": "Python is a programming language.",
        "results": [
            {"title": "Python Docs", "url": "https://docs.python.org", "snippet": "Official docs"},
            {"title": "Real Python", "url": "https://realpython.com", "snippet": "Tutorials"},
        ],
    }
    results = mod._parse_results(json.dumps(data), SearchRequest(query="python"))
    assert len(results) == 3
    assert results[0].metadata.get("type") == "ai_answer"


@pytest.mark.asyncio
async def test_parallel_execution(setup_engine):
    import time
    req = SearchRequest(
        query="python fastapi tutorial",
        sources=["github", "academic", "ddg"],
        max_results=5, timeout=20,
    )
    start = time.time()
    resp = await engine.search(req)
    assert time.time() - start < 25
    assert resp.metadata.get("engine_version") == "v4"
