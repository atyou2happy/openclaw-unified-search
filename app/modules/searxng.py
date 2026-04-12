"""SearXNG module — 自建聚合搜索引擎（247+引擎）."""

import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class SearXNGModule(BaseSearchModule):
    name = "searxng"
    description = "SearXNG 聚合搜索（Google/Bing/DDG/Brave 等 247+ 引擎）"
    BASE_URL = "http://127.0.0.1:8080"

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.BASE_URL}/healthz")
                return resp.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        try:
            params = {
                "q": request.query,
                "format": "json",
                "language": "zh-CN" if request.language in ("zh", "auto") else "en",
                "pageno": 1,
            }

            async with httpx.AsyncClient(timeout=request.timeout) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/search",
                    params=params,
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = []
                for item in data.get("results", []):
                    # SearXNG 返回的引擎列表
                    engines = item.get("engines", [])
                    engine_str = ",".join(engines[:3]) if engines else "searxng"

                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("content", "")[:500],
                        content=item.get("content", "")[:8000] if request.depth != "quick" else "",
                        source=f"searxng",
                        relevance=min(item.get("score", 0) / 5, 1.0) if item.get("score") else 0.7,
                        metadata={
                            "engines": engines,
                            "engine_primary": engines[0] if engines else "",
                        },
                    ))
                return results[:request.max_results]
        except Exception:
            return []
