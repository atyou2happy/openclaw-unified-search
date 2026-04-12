"""Jina Reader module — 免费网页搜索+内容提取，无需API key."""

import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


def _get_client(timeout: int = 15) -> httpx.AsyncClient:
    proxy = Config.get_proxy()
    kwargs = {"timeout": timeout}
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


class JinaModule(BaseSearchModule):
    name = "jina"
    description = "Jina Reader 免费网页搜索+内容提取（无需API key）"

    SEARCH_URL = "https://s.jina.ai/"
    READ_URL = "https://r.jina.ai/"

    async def health_check(self) -> bool:
        try:
            async with _get_client(10) as client:
                resp = await client.get(
                    self.SEARCH_URL,
                    headers={"Accept": "application/json"},
                    params={"q": "ping", "num": 1},
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        try:
            headers = {"Accept": "application/json"}
            params = {
                "q": request.query,
                "num": min(request.max_results, 20),
            }

            async with _get_client(request.timeout) as client:
                resp = await client.get(
                    self.SEARCH_URL,
                    headers=headers,
                    params=params,
                )

                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = []
                for item in data.get("data", []):
                    title = item.get("title", "")
                    url = item.get("url", "")
                    snippet = item.get("description", "") or item.get("content", "")[:300]
                    content = item.get("content", "")

                    results.append(SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet[:500],
                        content=content[:8000] if request.depth != "quick" else "",
                        source=self.name,
                        relevance=0.85,
                    ))
                return results

        except Exception:
            return []

    async def search_content(self, request: SearchRequest) -> list[SearchResult]:
        query = request.query.strip()

        if query.startswith("http"):
            return await self._read_url(query, request)

        results = await self.search(request)
        if request.depth != "deep" or not results:
            return results

        enriched = []
        for r in results[:3]:
            read_results = await self._read_url(r.url, request)
            if read_results:
                r.content = read_results[0].content
            enriched.append(r)
        return enriched

    async def _read_url(self, url: str, request: SearchRequest) -> list[SearchResult]:
        try:
            async with _get_client(30) as client:
                resp = await client.get(
                    f"{self.READ_URL}{url}",
                    headers={"Accept": "text/plain"},
                )
                if resp.status_code != 200:
                    return []

                content = resp.text
                max_chars = 10000 if request.depth == "deep" else 5000
                return [SearchResult(
                    title=f"Jina Reader: {url}",
                    url=url,
                    snippet=content[:500],
                    content=content[:max_chars],
                    source=self.name,
                    relevance=0.9,
                )]
        except Exception:
            return []
