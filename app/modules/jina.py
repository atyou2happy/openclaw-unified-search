"""Jina Reader module — 免费网页内容提取（r.jina.ai，无需API key）."""

import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class JinaModule(BaseSearchModule):
    name = "jina"
    description = "Jina Reader 网页内容提取（无需API key）"

    READ_URL = "https://r.jina.ai/"

    async def health_check(self) -> bool:
        # Jina 响应慢（21s+），跳过启动检查，按需失败
        return True

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """提取 URL 内容（query 应为 URL），或搜索关键词后提取"""
        query = request.query.strip()

        if query.startswith("http"):
            return await self._read_url(query, request)

        # 非URL：先DDG搜索获取URL，再提取内容
        return await self._search_and_read(request)

    async def _search_and_read(self, request: SearchRequest) -> list[SearchResult]:
        """搜索关键词后提取 Top 结果内容"""
        try:
            from ddgs import DDGS
            proxy = Config.get_proxy()
            urls = []
            with DDGS(proxy=proxy) as ddgs:
                for r in ddgs.text(request.query, max_results=request.max_results):
                    if r.get("href"):
                        urls.append((r.get("title", ""), r.get("href")))

            results = []
            for title, url in urls[:5]:
                read = await self._read_url(url, request)
                if read:
                    read[0].title = title or read[0].title
                    results.extend(read)
                else:
                    results.append(SearchResult(
                        title=title, url=url,
                        snippet="", source=self.name, relevance=0.6,
                    ))
            return results
        except Exception:
            return []

    async def _read_url(self, url: str, request: SearchRequest) -> list[SearchResult]:
        """提取单个 URL 的完整内容"""
        try:
            proxy = Config.get_proxy()
            kwargs = {"timeout": 30}
            if proxy:
                kwargs["proxy"] = proxy
            async with httpx.AsyncClient(**kwargs) as client:
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
