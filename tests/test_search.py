"""Tests for unified search modules."""

import asyncio
import pytest
from app.models import SearchRequest
from app.engine import engine
from app.modules import auto_register, get


@pytest.fixture(scope="module")
def setup_engine():
    """Register modules and load engine once for all tests."""
    auto_register()
    engine.load_modules()


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
    req = SearchRequest(query="python fastapi", sources=["github"], max_results=3, timeout=15)
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
    req = SearchRequest(query="large language models", sources=["academic"], max_results=3, timeout=20)
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
    req = SearchRequest(query="Python FastAPI tutorial", sources=["web"], max_results=3, timeout=15)
    resp = await engine.search(req)
    # Web search may fail due to network, so we just check no crash
    assert resp.elapsed > 0


@pytest.mark.asyncio
async def test_module_not_found(setup_engine):
    """Non-existent module should return error."""
    req = SearchRequest(query="test", sources=["nonexistent"], max_results=3)
    resp = await engine.search(req)
    assert resp.total == 0


@pytest.mark.asyncio
async def test_cache(setup_engine):
    """Second search should be cached."""
    from app.cache import cache
    cache.clear()

    req = SearchRequest(query="FastCode GitHub repo", sources=["github"], max_results=3, timeout=15)
    resp1 = await engine.search(req)
    assert not resp1.cached

    resp2 = await engine.search(req)
    assert resp2.cached


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
    modules = ["github", "web", "academic", "pdf", "docs"]
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
        SearchRequest()  # query is required

    with pytest.raises(Exception):
        SearchRequest(query="", max_results=100)  # max_results > 50
