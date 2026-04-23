"""Module registry — 动态发现和注册搜索模块.

借鉴 Google Workspace CLI (gws) 的 Discovery Service 思路：
- 扫描 app/modules/ 目录下所有 .py 文件
- 自动查找 BaseSearchModule 子类
- 通过类属性声明式注册（name/description/dependencies）
- 无需手动维护模块列表

新增模块只需：
1. 在 app/modules/ 下创建 .py 文件
2. 继承 BaseSearchModule 并实现 search()
3. 设置类属性 name, description
4. 自动被发现和注册
"""

import importlib
import inspect
import logging
import os
from pathlib import Path
from typing import Dict, List, Type

from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)

_registry: Dict[str, BaseSearchModule] = {}

# 模块加载顺序（影响 health_check 优先级）
# 未在此列表中的模块按字母序排在后面
_PRIORITY_ORDER = [
    "searxng",      # 聚合搜索基础
    "metaso",        # 秘塔AI
    "tabbit",        # TabBitBrowser
    "meilisearch",   # 本地知识库
    "web",           # 网页搜索
    "jina",          # 网页提取
    "github",        # GitHub
    "pdf",           # PDF
    "docs",          # 文档
    "reddit",        # Reddit 社区
    "hackernews",   # Hacker News
    "youtube",      # YouTube 视频
    "github_trending", # GitHub Trending
    "academic",      # 学术
    "wiki",          # 百科
    "ddg",           # DuckDuckGo
    # CDP 模块（按降级链顺序）
    "deepseek", "gemini", "grok", "kimi", "glm", "qwen",
    # API 模块（需 key）
    "brave", "tavily", "serper", "perplexity", "bing", "you", "komo",
]

# 排除的文件（不作为模块加载）
_EXCLUDED = {"__init__", "base", "cdp_pool"}


def register(module: BaseSearchModule) -> None:
    _registry[module.name] = module


def get(name: str) -> BaseSearchModule | None:
    return _registry.get(name)


def get_all() -> Dict[str, BaseSearchModule]:
    return _registry.copy()


def list_names() -> list[str]:
    return list(_registry.keys())


def _discover_module_classes(package_path: Path) -> Dict[str, Type[BaseSearchModule]]:
    """扫描目录，发现所有 BaseSearchModule 子类"""
    classes = {}

    for py_file in sorted(package_path.glob("*.py")):
        module_name = py_file.stem

        # 跳过排除文件
        if module_name in _EXCLUDED or module_name.startswith("_"):
            continue

        try:
            # 动态导入模块
            mod = importlib.import_module(f"app.modules.{module_name}")

            # 查找所有 BaseSearchModule 子类
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, BaseSearchModule)
                    and attr is not BaseSearchModule
                    and hasattr(attr, "name")
                    and attr.name  # 必须有 name 属性
                ):
                    classes[attr.name] = attr
                    logger.debug(f"Discovered module: {attr.name} from {module_name}.{attr_name}")

        except Exception as e:
            logger.warning(f"Failed to load module {module_name}: {e}")

    return classes


def auto_register():
    """自动发现、实例化并注册所有搜索模块.

    借鉴 gws Discovery Service:
    1. 扫描 app/modules/ 目录
    2. 动态导入每个 .py 文件
    3. 发现 BaseSearchModule 子类
    4. 按 _PRIORITY_ORDER 排序后实例化注册
    """
    modules_dir = Path(__file__).parent
    discovered = _discover_module_classes(modules_dir)

    # 按优先级排序
    def sort_key(name):
        try:
            return _PRIORITY_ORDER.index(name)
        except ValueError:
            return len(_PRIORITY_ORDER) + ord(name[0])

    sorted_names = sorted(discovered.keys(), key=sort_key)

    modules = []
    for name in sorted_names:
        cls = discovered[name]
        try:
            instance = cls()
            register(instance)
            modules.append(instance)
            logger.info(f"Registered module: {name}")
        except Exception as e:
            logger.error(f"Failed to instantiate module {name}: {e}")

    logger.info(f"Auto-registered {len(modules)} modules: {sorted_names}")
    return modules
