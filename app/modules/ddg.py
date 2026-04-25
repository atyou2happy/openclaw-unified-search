"""DuckDuckGo module — 免费无限额度的网页搜索."""

import asyncio
import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

# DDG 网络较慢（经代理绕路），设置独立超时上限避免拖慢整体
DDG_TIMEOUT = 5


class DuckDuckGoModule(BaseSearchModule):
    """DuckDuckGo 搜索 — 免费，无需 API Key"""

    name = "ddg"
    description = "DuckDuckGo 网页搜索（免费无限）"

    async def health_check(self) -> bool:
        return True

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        proxy = Config.get_proxy()
        timeout = min(request.timeout, DDG_TIMEOUT)

        # 策略1: ddgs 库（最可靠）
        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(self._ddgs_search, request.query, request.max_results, proxy),
                timeout=timeout,
            )
            if results:
                return results
        except Exception:
            pass

        # 策略2: httpx HTML 抓取
        try:
            kwargs = {"timeout": timeout}
            if proxy:
                kwargs["proxy"] = proxy
            async with httpx.AsyncClient(**kwargs) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": request.query, "b": min(request.max_results, 20)},
                )
                if resp.status_code == 200 and "result__" in resp.text:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    results = []
                    for result in soup.select(".result__body")[:request.max_results]:
                        title_elem = result.select_one(".result__a")
                        snippet_elem = result.select_one(".result__snippet")
                        if title_elem:
                            results.append(SearchResult(
                                title=title_elem.get_text()[:200],
                                url=title_elem.get("href", ""),
                                snippet=snippet_elem.get_text()[:200] if snippet_elem else "",
                                source="ddg",
                                relevance=0.7,
                            ))
                    return results
        except Exception:
            pass

        return []

    def _ddgs_search(self, query: str, max_results: int, proxy: str | None) -> list[SearchResult]:
        """同步 ddgs 搜索（在线程中运行）"""
        from ddgs import DDGS
        ddgs = DDGS(proxy=proxy)
        results = []
        for r in ddgs.text(query, max_results=max_results):
            results.append(SearchResult(
                title=r.get("title", "")[:200],
                url=r.get("href", ""),
                snippet=r.get("body", "")[:200],
                source="ddg",
                relevance=0.7,
            ))
        return results
