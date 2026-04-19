"""Web search module — TabBitBrowser 优先, DDG 备用."""

import asyncio
import sys
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


def _proxy_client(**kwargs):
    proxy = Config.get_proxy()
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


import httpx


class WebSearchModule(BaseSearchModule):
    name = "web"
    description = "智能网页搜索（TabBitBrowser 优先, DDG 备用）"

    def __init__(self):
        super().__init__()
        self._tabbit_available: bool | None = None

    async def health_check(self) -> bool:
        return await self._check_tabbit() or await self._check_ddg()

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
    async def _check_ddg() -> bool:
        try:
            from ddgs import DDGS
            proxy = Config.get_proxy()
            with DDGS(proxy=proxy) as d:
                list(d.text("ping", max_results=1))
            return True
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        if await self._check_tabbit():
            results = await self._search_tabbit(request)
            if results:
                return results

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
    async def _search_ddg(request: SearchRequest) -> list[SearchResult]:
        region = "cn-zh" if request.language in ("zh", "auto") else "us-en"
        try:
            from ddgs import DDGS
            proxy = Config.get_proxy()
            results = []
            with DDGS(proxy=proxy) as ddgs:
                for r in ddgs.text(
                    request.query,
                    region=region,
                    max_results=request.max_results,
                ):
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        url=r.get("href", ""),
                        snippet=r.get("body", ""),
                        source="ddg",
                        relevance=0.7,
                    ))
            return results
        except Exception:
            return []
