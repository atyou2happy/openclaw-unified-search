"""Base class for search modules."""

import asyncio
from abc import ABC, abstractmethod
from app.models import SearchRequest, SearchResult


class BaseSearchModule(ABC):
    """搜索模块抽象基类 — 所有模块必须继承此类"""

    name: str = ""
    description: str = ""

    def __init__(self):
        self._available: bool | None = None

    @abstractmethod
    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """执行搜索，返回结果列表"""

    async def health_check(self) -> bool:
        """检查模块是否可用（可被子类覆写）"""
        return True

    async def is_available(self) -> bool:
        """快速可用性检查（带缓存 + 超时保护）"""
        if self._available is None:
            try:
                self._available = await asyncio.wait_for(
                    self.health_check(), timeout=5.0
                )
            except (asyncio.TimeoutError, Exception):
                self._available = False
        return self._available

    def reset_availability(self):
        """重置可用性缓存"""
        self._available = None
