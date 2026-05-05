"""Bing Search module — Microsoft Bing API."""

import logging
import os
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class BingModule(BaseSearchModule):
    """Bing Search — Microsoft 免费 1000次/月"""

    name = "bing"
    description = "Bing Search（Microsoft，免费 1000次/月）"

    async def health_check(self) -> bool:
        return bool(os.environ.get("BING_API_KEY"))

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        api_key = os.environ.get("BING_API_KEY")
        if not api_key:
            return []

        try:
            client = await self.get_http_client(timeout=request.timeout)
            resp = await client.get(
                "https://api.bing.microsoft.com/v7.0/search",
                params={
                    "q": request.query,
                    "count": min(request.max_results, 50),
                },
                headers={
                    "Ocp-Apim-Subscription-Key": api_key,
                },
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []

            for item in data.get("webPages", {}).get("value", []):
                results.append(
                    SearchResult(
                        title=item.get("name", "")[:200],
                        url=item.get("url", ""),
                        snippet=item.get("snippet", ""),
                        source="bing",
                        relevance=0.8,
                    )
                )

            # 资讯卡片
            for item in data.get("news", {}).get("value", [])[:3]:
                results.append(
                    SearchResult(
                        title=item.get("name", "")[:200],
                        url=item.get("url", ""),
                        snippet=item.get("description", "")[:200],
                        source="bing_news",
                        relevance=0.75,
                    )
                )

            return results
        except Exception:
            return []
