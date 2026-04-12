"""Base class for search modules."""

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
        """快速可用性检查（带缓存）"""
        if self._available is None:
            try:
                self._available = await self.health_check()
            except Exception:
                self._available = False
        return self._available

    def reset_availability(self):
        """重置可用性缓存"""
        self._available = None
