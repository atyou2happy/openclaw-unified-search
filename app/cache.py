"""In-memory LRU cache for search results."""

import hashlib
import time
from threading import Lock
from typing import Optional

from app.models import SearchRequest, SearchResponse
from app.config import Config


class SearchCache:
    """Thread-safe LRU cache for search results."""

    def __init__(
        self,
        max_size: int = Config.CACHE_MAX_SIZE,
        ttl: int = Config.CACHE_TTL_SECONDS,
    ):
        self._max_size = max_size
        self._ttl = ttl
        self._cache: dict[str, tuple[SearchResponse, float]] = {}
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(request: SearchRequest) -> str:
        """Generate cache key from request."""
        raw = f"{request.query}|{sorted(request.sources)}|{request.language}|{request.depth}|{request.max_results}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, request: SearchRequest) -> Optional[SearchResponse]:
        """Get cached response if exists and not expired."""
        key = self._make_key(request)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            response, ts = entry
            if time.time() - ts > self._ttl:
                del self._cache[key]
                self._misses += 1
                return None

            self._hits += 1
            response.cached = True
            return response.model_copy()

    def put(self, request: SearchRequest, response: SearchResponse) -> None:
        """Store response in cache."""
        key = self._make_key(request)
        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self._max_size and key not in self._cache:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[key] = (response.model_copy(), time.time())

    def clear(self) -> int:
        """Clear all cache entries. Returns count of cleared entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            return count

    def stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
            }


# Global cache instance
cache = SearchCache()
