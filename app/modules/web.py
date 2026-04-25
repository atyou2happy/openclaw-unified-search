"""Web search module — TabBitBrowser 优先, SearXNG 备用, DDG 兜底."""

import asyncio
import sys
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule
import httpx


def _proxy_client(**kwargs):
    proxy = Config.get_proxy()
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


class WebSearchModule(BaseSearchModule):
    name = "web"
    description = "智能网页搜索（TabBitBrowser 优先, SearXNG 备用, DDG 兜底）"

    def __init__(self):
        super().__init__()
        self._tabbit_available: bool | None = None

    async def health_check(self) -> bool:
        return await self._check_tabbit() or await self._check_searxng()

    async def _check_tabbit(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                resp = await client.get(
                    f"http://localhost:{Config.TABBIT_CDP_PORT}/json",
                )
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    async def _check_searxng() -> bool:
        try:
            async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                resp = await client.get("http://localhost:8080/healthz")
                return resp.status_code == 200
        except Exception:
            try:
                async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                    resp = await client.get("http://localhost:8080/", follow_redirects=True)
                    return resp.status_code == 200
            except Exception:
                return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        # 策略1: TabBitBrowser（质量最高）
        if await self._check_tabbit():
            results = await self._search_tabbit(request)
            if results:
                return results

        # 策略2: SearXNG（稳定快速，247+ 引擎聚合）
        results = await self._search_searxng(request)
        if results:
            return results

        # 策略3: DDG 兜底（较慢，5s 超时）
        return await self._search_ddg(request)

    async def search_content(self, request: SearchRequest) -> list[SearchResult]:
        results = await self.search(request)
        if request.depth != "deep" or not results:
            return results

        import trafilatura

        enriched = []
        async with _proxy_client(timeout=15, follow_redirects=True) as client:
            for r in results[:5]:
                try:
                    resp = await client.get(r.url)
                    content = trafilatura.extract(resp.text)
                    if content:
                        r.content = content[:10000]
                except Exception:
                    pass
                enriched.append(r)
        return enriched

    async def _search_tabbit(self, request: SearchRequest) -> list[SearchResult]:
        timeout = min(request.timeout, Config.TABBIT_TIMEOUT)
        max_chars = 8000 if request.depth == "deep" else 5000

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, Config.TABBIT_SCRIPT_PATH,
                request.query,
                "--port", str(Config.TABBIT_CDP_PORT),
                "--timeout", str(timeout),
                "--max-chars", str(max_chars),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout + 10
            )

            if proc.returncode != 0:
                return []

            content = stdout.decode("utf-8", errors="replace").strip()
            if not content:
                return []

            return [SearchResult(
                title=f"TabBitBrowser: {request.query}",
                url="",
                snippet=content[:500],
                content=content,
                source="tabbit",
                relevance=0.95,
            )]
        except (asyncio.TimeoutError, Exception):
            return []

    @staticmethod
    async def _search_searxng(request: SearchRequest) -> list[SearchResult]:
        """SearXNG 聚合搜索（247+ 引擎，稳定快速）"""
        try:
            async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                language = "zh-CN" if request.language in ("zh", "auto") else "en-US"
                resp = await client.get(
                    "http://localhost:8080/search",
                    params={
                        "q": request.query,
                        "format": "json",
                        "language": language,
                        "pageno": 1,
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = []
                for item in data.get("results", [])[:request.max_results]:
                    results.append(SearchResult(
                        title=item.get("title", "")[:200],
                        url=item.get("url", ""),
                        snippet=item.get("content", "")[:200],
                        source="searxng",
                        relevance=0.8,
                    ))
                return results
        except Exception:
            return []

    @staticmethod
    async def _search_ddg(request: SearchRequest) -> list[SearchResult]:
        """DDG 兜底（5s 超时限制）"""
        region = "cn-zh" if request.language in ("zh", "auto") else "us-en"
        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(WebSearchModule._ddgs_sync, request.query, region, request.max_results),
                timeout=5,
            )
            return results
        except Exception:
            return []

    @staticmethod
    def _ddgs_sync(query: str, region: str, max_results: int) -> list[SearchResult]:
        from ddgs import DDGS
        proxy = Config.get_proxy()
        results = []
        with DDGS(proxy=proxy) as ddgs:
            for r in ddgs.text(query, region=region, max_results=max_results):
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", ""),
                    source="ddg",
                    relevance=0.7,
                ))
        return results
