"""DuckDuckGo module — 免费无限额度的网页搜索."""

import os
import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class DuckDuckGoModule(BaseSearchModule):
    """DuckDuckGo 搜索 — 免费，无需 API Key"""

    name = "ddg"
    description = "DuckDuckGo 网页搜索（免费无限）"

    async def health_check(self) -> bool:
        # DDG 总是可用的
        return True

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        proxy = Config.get_proxy()
        kwargs = {"timeout": request.timeout}
        if proxy:
            kwargs["proxy"] = proxy

        try:
            async with httpx.AsyncClient(**kwargs) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={
                        "q": request.query,
                        "b": min(request.max_results, 20),
                    },
                )
                if resp.status_code != 200:
                    return []

                # 使用 ddgs 库作为备用
                from ddgs import DDGS

                try:
                    ddgs = DDGS(proxy=proxy)
                    results = []
                    for r in ddgs.text(request.query, max_results=request.max_results):
                        results.append(
                            SearchResult(
                                title=r.get("title", "")[:200],
                                url=r.get("href", ""),
                                snippet=r.get("body", "")[:200],
                                source="ddg",
                                relevance=0.7,
                            )
                        )
                    return results
                except Exception:
                    pass

                # HTML 解析备用方案
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for result in soup.select(".result__body")[: request.max_results]:
                    title_elem = result.select_one(".result__a")
                    snippet_elem = result.select_one(".result__snippet")
                    if title_elem:
                        results.append(
                            SearchResult(
                                title=title_elem.get_text()[:200],
                                url=title_elem.get("href", ""),
                                snippet=snippet_elem.get_text()[:200]
                                if snippet_elem
                                else "",
                                source="ddg",
                                relevance=0.7,
                            )
                        )
                return results
        except Exception:
            return []
