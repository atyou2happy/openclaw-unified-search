"""Komo module — 快速 AI 搜索."""

import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class KomoModule(BaseSearchModule):
    """Komo AI 搜索 — 免费快速"""

    name = "komo"
    description = "Komo AI 搜索（免费快速）"

    async def health_check(self) -> bool:
        # Komo 总是可用的（有 rate limit）
        return True

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        proxy = Config.get_proxy()
        kwargs = {"timeout": request.timeout}
        if proxy:
            kwargs["proxy"] = proxy

        try:
            async with httpx.AsyncClient(**kwargs) as client:
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
