"""Module availability cache — TTL-based, avoids repeated health checks."""

import time


class AvailabilityCache:
    """模块可用性缓存 — TTL 60s，减少 is_available() 调用"""

    def __init__(self, ttl: int = 60):
        self._cache: dict[str, tuple[bool, float]] = {}
        self._ttl = ttl

    def get(self, module_name: str) -> bool | None:
        if module_name in self._cache:
            available, ts = self._cache[module_name]
            if time.time() - ts < self._ttl:
                return available
        return None

    def set(self, module_name: str, available: bool):
        self._cache[module_name] = (available, time.time())

    def invalidate(self, module_name: str = None):
        if module_name:
            self._cache.pop(module_name, None)
        else:
            self._cache.clear()


avail_cache = AvailabilityCache()
