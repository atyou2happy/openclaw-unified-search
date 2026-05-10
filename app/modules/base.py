"""Base class for search modules — with shared httpx connection pool."""

import asyncio
import logging
from abc import ABC, abstractmethod

import httpx

from app.models import SearchRequest, SearchResult

logger = logging.getLogger(__name__)


class BaseSearchModule(ABC):
    """搜索模块抽象基类 — 所有模块必须继承此类

    v1.0.0 changes:
    - Shared httpx.AsyncClient per module instance (connection pool reuse)
    - Async close_http_client() for graceful shutdown
    - get_http_client() auto-creates client with proxy config
    """

    name: str = ""
    description: str = ""
    health_check_timeout: float = 15.0  # 默认15秒（代理网络需更长时间）

    # Shared httpx client — created lazily, reused across requests
    _http_client: httpx.AsyncClient | None = None

    def __init__(self):
        self._available: bool | None = None

    # ============================================================
    # HTTP client pool (v1.0.0)
    # ============================================================

    # Set True in subclasses that connect to localhost services (bypasses proxy)
    _skip_proxy: bool = False

    def _get_proxy_url(self) -> str | None:
        """Get proxy URL from config. Override in subclasses if needed."""
        if self._skip_proxy:
            return None
        from app.config import Config
        return Config.get_proxy()

    def _get_client_kwargs(self, **overrides) -> dict:
        """Build httpx.AsyncClient kwargs with proxy + limits."""
        kwargs: dict = {
            "timeout": 30,
            "trust_env": False,
            "limits": httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
            "follow_redirects": True,
        }
        proxy = self._get_proxy_url()
        if proxy:
            kwargs["proxy"] = proxy
            kwargs["verify"] = False  # WestWorld proxy uses self-signed cert
        kwargs.update(overrides)
        return kwargs

    async def get_http_client(self, **kwargs) -> httpx.AsyncClient:
        """Get or create shared httpx client for this module.

        Args:
            **kwargs: Override default client settings (timeout, proxy, etc.)

        Returns:
            Reusable httpx.AsyncClient instance
        """
        if self._http_client is None or self._http_client.is_closed:
            client_kwargs = self._get_client_kwargs(**kwargs)
            self._http_client = httpx.AsyncClient(**client_kwargs)
        return self._http_client

    async def close_http_client(self):
        """Close httpx client gracefully. Called during app shutdown."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    # ============================================================
    # Abstract interface
    # ============================================================

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
