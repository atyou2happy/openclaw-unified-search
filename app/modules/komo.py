"""Komo module — 快速 AI 搜索."""

import logging
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class KomoModule(BaseSearchModule):
    """Komo AI 搜索 — 免费快速"""

    name = "komo"
    description = "Komo AI 搜索（免费快速）"

    async def health_check(self) -> bool:
        # API 已变更，暂时不可用
        return False

    async def _disabled_health_check(self) -> bool:
        # Komo 总是可用的（有 rate limit）
        return True

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        try:
            client = await self.get_http_client(timeout=request.timeout)
            resp = await client.post(
                "https://api.komo.ai/api/v3/search",
                json={
                    "query": request.query,
                    "limit": min(request.max_results, 10),
                },
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []

            for item in data.get("results", []):
                results.append(
                    SearchResult(
                        title=item.get("title", "")[:200],
                        url=item.get("url", ""),
                        snippet=item.get("snippet", ""),
                        source="komo",
                        relevance=0.7,
                    )
                )

            return results
        except Exception:
            return []
