"""Module registry — 自动发现和注册搜索模块."""

from typing import Dict, Type
from app.modules.base import BaseSearchModule


_registry: Dict[str, BaseSearchModule] = {}


def register(module: BaseSearchModule) -> None:
    _registry[module.name] = module


def get(name: str) -> BaseSearchModule | None:
    return _registry.get(name)


def get_all() -> Dict[str, BaseSearchModule]:
    return _registry.copy()


def list_names() -> list[str]:
    return list(_registry.keys())


def auto_register():
    """自动导入并注册所有模块"""
    from app.modules import (
        tabbit,
        web,
        github,
        pdf,
        docs,
        academic,
        jina,
        wiki,
        brave,
        tavily,
        serper,
        searxng,
        metaso,
        phind,
        ddg,
        bing,
        you,
        komo,
        perplexity,  # noqa: F401
    )

    modules = []

    # SearXNG (聚合搜索，247+引擎)
    m = searxng.SearXNGModule()
    register(m)
    modules.append(m)

    # 秘塔AI搜索 (中文最强)
    m = metaso.MetasoModule()
    register(m)
    modules.append(m)

    # Phind (程序员搜索)
    m = phind.PhindModule()
    register(m)
    modules.append(m)

    # TabBitBrowser
    m = tabbit.TabBitModule()
    register(m)
    modules.append(m)

    # Web Search (TabBit 优先, DDG 备用)
    m = web.WebSearchModule()
    register(m)
    modules.append(m)

    # Jina Reader (网页内容提取)
    m = jina.JinaModule()
    register(m)
    modules.append(m)

    # GitHub + Zread.ai
    m = github.GitHubModule()
    register(m)
    modules.append(m)

    # PDF
    m = pdf.PDFModule()
    register(m)
    modules.append(m)

    # Docs
    m = docs.DocsModule()
    register(m)
    modules.append(m)

    # Academic
    m = academic.AcademicModule()
    register(m)
    modules.append(m)

    # Wiki (百度百科 + 维基百科)
    m = wiki.WikiModule()
    register(m)
    modules.append(m)

    # Brave Search (需 BRAVE_API_KEY)
    m = brave.BraveModule()
    register(m)
    modules.append(m)

    # Tavily (需 TAVILY_API_KEY)
    m = tavily.TavilyModule()
    register(m)
    modules.append(m)

    # Serper.dev (需 SERPER_API_KEY)
    m = serper.SerperModule()
    register(m)
    modules.append(m)

    # Perplexity AI (需 PERPLEXITY_API_KEY)
    m = perplexity.PerplexityModule()
    register(m)
    modules.append(m)

    # DuckDuckGo (免费无限)
    m = ddg.DuckDuckGoModule()
    register(m)
    modules.append(m)

    # Bing Search (需 BING_API_KEY)
    m = bing.BingModule()
    register(m)
    modules.append(m)

    # You.com (需 YOU_API_KEY)
    m = you.YouModule()
    register(m)
    modules.append(m)

    # Komo (免费快速)
    m = komo.KomoModule()
    register(m)
    modules.append(m)

    return modules
