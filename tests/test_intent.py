"""Tests for query intent detection and module selection."""

import pytest
from app.engine.intent import QueryIntent
from app.modules import auto_register, get_all


@pytest.fixture(scope="module")
def setup():
    auto_register()


@pytest.mark.asyncio
async def test_intent_code(setup):
    intent = QueryIntent.detect("how to write python function")
    assert "code" in intent["types"]


@pytest.mark.asyncio
async def test_intent_academic(setup):
    intent = QueryIntent.detect("transformer attention paper arxiv")
    assert "academic" in intent["types"]


@pytest.mark.asyncio
async def test_intent_knowledge(setup):
    intent = QueryIntent.detect("what is machine learning")
    assert "knowledge" in intent["types"]


@pytest.mark.asyncio
async def test_intent_chinese(setup):
    intent = QueryIntent.detect("如何学习Python")
    assert "chinese" in intent["hints"]


@pytest.mark.asyncio
async def test_intent_url_given(setup):
    intent = QueryIntent.detect("https://github.com/python")
    assert "content" in intent["types"]
    assert "url_given" in intent["hints"]


@pytest.mark.asyncio
async def test_intent_repo_format(setup):
    intent = QueryIntent.detect("atyou2happy/openclaw-unified-search")
    assert "code" in intent["types"]
    assert "repo_format" in intent["hints"]


@pytest.mark.asyncio
async def test_intent_news(setup):
    intent = QueryIntent.detect("最新AI新闻")
    assert "news" in intent["types"]
    assert "fresh" in intent["hints"]


@pytest.mark.asyncio
async def test_intent_news_english(setup):
    intent = QueryIntent.detect("latest stock market news today")
    assert "news" in intent["types"]


@pytest.mark.asyncio
async def test_empty_query(setup):
    intent = QueryIntent.detect("")
    assert "general" in intent["types"]


@pytest.mark.asyncio
async def test_module_selection(setup):
    intent = QueryIntent.detect("python code tutorial")
    available = get_all()
    selected = QueryIntent.select_modules(intent, available)
    assert len(selected) > 0
    assert selected[0] in available


@pytest.mark.asyncio
async def test_tabbit_always_selected(setup):
    available = get_all()
    for query in ["python code", "what is AI", "news today", "random text xyz"]:
        intent = QueryIntent.detect(query)
        selected = QueryIntent.select_modules(intent, available)
        if "tabbit" in available:
            assert "tabbit" in selected, f"tabbit not selected for: {query}"


@pytest.mark.asyncio
async def test_tabbit_first_priority(setup):
    intent = QueryIntent.detect("how to write fastapi endpoints")
    available = get_all()
    selected = QueryIntent.select_modules(intent, available)
    if "tabbit" in available:
        assert selected[0] == "tabbit"


@pytest.mark.asyncio
async def test_adaptive_module_count(setup):
    available = get_all()
    general_selected = QueryIntent.select_modules(
        QueryIntent.detect("hello world"), available
    )
    research_selected = QueryIntent.select_modules(
        QueryIntent.detect("transformer attention paper research arxiv"), available
    )
    assert len(research_selected) >= len(general_selected)
