"""DuckDuckGo web search module."""

from datetime import datetime
from ddgs import DDGS
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class WebSearchModule(BaseSearchModule):
    name = "web"
    description = "DuckDuckGo 通用网页搜索（免费无限）"

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        region = "cn-zh" if request.language in ("zh", "auto") else "us-en"
        max_results = request.max_results

        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(
                    request.query,
                    region=region,
                    max_results=max_results,
                ):
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        url=r.get("href", ""),
                        snippet=r.get("body", ""),
                        source=self.name,
                        relevance=0.7,
                    ))
            return results
        except Exception:
            return []

    async def search_content(self, request: SearchRequest) -> list[SearchResult]:
        """深度搜索：获取 Top N 结果的完整正文"""
        results = await self.search(request)

        if request.depth != "deep" or not results:
            return results

        import trafilatura
        import httpx

        enriched = []
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for r in results[:5]:  # Top 5 only for deep mode
                try:
                    resp = await client.get(r.url)
                    content = trafilatura.extract(resp.text)
                    if content:
                        r.content = content[:10000]
                        enriched.append(r)
                    else:
                        enriched.append(r)
                except Exception:
                    enriched.append(r)

        return enriched
