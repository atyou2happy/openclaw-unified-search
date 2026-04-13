"""Brave Search module — 免费 2000次/月."""

import os
import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class BraveModule(BaseSearchModule):
    name = "brave"
    description = "Brave Search API（免费 2000次/月）"

    async def health_check(self) -> bool:
        # key 存在不代表有效，标记为可用由实际搜索验证
        return bool(os.environ.get("BRAVE_API_KEY"))

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        api_key = os.environ.get("BRAVE_API_KEY")
        if not api_key:
            return []

        proxy = Config.get_proxy()
        kwargs = {"timeout": request.timeout}
        if proxy:
            kwargs["proxy"] = proxy

        try:
            async with httpx.AsyncClient(**kwargs) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={
                        "q": request.query,
                        "count": min(request.max_results, 20),
                    },
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": api_key,
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = []
                for item in data.get("web", {}).get("results", []):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("description", ""),
                        content=item.get("extra", {}).get("snippet", "") if request.depth != "quick" else "",
                        source="brave",
                        relevance=0.85,
                    ))
                return results
        except Exception:
            return []
