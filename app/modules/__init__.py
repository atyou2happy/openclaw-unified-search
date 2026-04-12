"""Module registry — 自动发现和注册搜索模块."""

from typing import Dict, Type
from app.modules.base import BaseSearchModule


_registry: Dict[str, BaseSearchModule] = {}


def register(module: BaseSearchModule) -> None:
    """注册一个搜索模块实例"""
    _registry[module.name] = module


def get(name: str) -> BaseSearchModule | None:
    """按名称获取模块"""
    return _registry.get(name)


def get_all() -> Dict[str, BaseSearchModule]:
    """获取所有已注册模块"""
    return _registry.copy()


def list_names() -> list[str]:
    """列出所有模块名"""
    return list(_registry.keys())


def auto_register():
    """自动导入并注册所有模块"""
    from app.modules import tabbit, web, github, pdf, docs, academic  # noqa: F401

    modules = []

    # TabBitBrowser
    m = tabbit.TabBitModule()
    register(m)
    modules.append(m)

    # Web Search (TabBit 优先, DDG 备用)
    m = web.WebSearchModule()
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
