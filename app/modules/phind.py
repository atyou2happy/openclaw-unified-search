"""Phind module — 程序员AI搜索引擎."""

import httpx
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class PhindModule(BaseSearchModule):
    name = "phind"
    description = "Phind 程序员AI搜索（编程问题专用）"
    SEARCH_URL = "https://https.api.phind.com/search"

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5, proxy=self._get_proxy()) as client:
                resp = await client.get("https://www.phind.com", follow_redirects=True)
                return resp.status_code == 200
        except Exception:
            return False

    def _get_proxy(self) -> str | None:
        from app.config import Config
        return Config.get_proxy()

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        proxy = self._get_proxy()
        kwargs = {"timeout": request.timeout}
        if proxy:
            kwargs["proxy"] = proxy

        try:
            async with httpx.AsyncClient(**kwargs) as client:
                # Phind 搜索 API
                resp = await client.post(
                    "https://https.api.phind.com/search",
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    },
                    json={
                        "question": request.query,
                        "searchResults": min(request.max_results, 10),
                        "language": "zh-CN" if request.language in ("zh", "auto") else "en",
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = []

                # Phind 返回搜索结果
                for item in data.get("searchResults", []):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("snippet", "")[:500],
                        source="phind",
                        relevance=0.8,
                    ))

                # Phind 的 AI 答案
                answer = data.get("answer", "")
                if answer:
                    results.insert(0, SearchResult(
                        title=f"Phind Answer: {request.query}",
                        url="",
                        snippet=answer[:500],
                        content=answer[:8000] if request.depth != "quick" else "",
                        source="phind_answer",
                        relevance=0.95,
                    ))

                return results[:request.max_results]
        except Exception:
            return []
