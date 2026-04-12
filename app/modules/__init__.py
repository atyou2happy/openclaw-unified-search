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
    from app.modules import tabbit, web, github, pdf, docs, academic, jina  # noqa: F401

    modules = []

    # TabBitBrowser
    m = tabbit.TabBitModule()
    register(m)
    modules.append(m)

    # Web Search (TabBit 优先, DDG 备用)
    m = web.WebSearchModule()
    register(m)
    modules.append(m)

    # Jina Reader (免费搜索+内容提取)
    m = jina.JinaModule()
    register(m)
    modules.append(m)

    # GitHub
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

    return modules
