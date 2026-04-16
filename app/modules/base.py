"""Base class for search modules."""

import asyncio
import logging
from abc import ABC, abstractmethod
from app.models import SearchRequest, SearchResult

logger = logging.getLogger(__name__)


class BaseSearchModule(ABC):
    """搜索模块抽象基类 — 所有模块必须继承此类"""

    name: str = ""
    description: str = ""
    health_check_timeout: float = 15.0  # 默认15秒（代理网络需更长时间）

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
                    self.health_check(), timeout=self.health_check_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Module {self.name} health check timed out ({self.health_check_timeout}s)")
                self._available = False
            except Exception as e:
                logger.warning(f"Module {self.name} health check failed: {e}")
                self._available = False
        return self._available

    def reset_availability(self):
        """重置可用性缓存"""
        self._available = None
