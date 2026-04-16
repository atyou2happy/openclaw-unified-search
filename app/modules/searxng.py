"""SearXNG module — 自建聚合搜索引擎（247+引擎）."""

import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class SearXNGModule(BaseSearchModule):
    name = "searxng"
    description = "SearXNG 聚合搜索（Google/Bing/DDG/Brave 等 247+ 引擎）"
    BASE_URL = "http://127.0.0.1:8080"
    health_check_timeout = 15.0  # Docker 网络可能慢

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                resp = await client.get(f"{self.BASE_URL}/search", params={"q": "health", "format": "json"})
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

            async with httpx.AsyncClient(timeout=request.timeout, trust_env=False) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/search",
                    params=params,
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()

            results = []
            for item in data.get("results", [])[:request.limit]:
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source=self.name,
                    score=item.get("score", 0),
                    engine=item.get("engine", ""),
                ))
            return results
        except Exception:
            return []
