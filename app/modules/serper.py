"""Serper.dev module — Google 搜索结果, 免费 2500次."""

import os
import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class SerperModule(BaseSearchModule):
    name = "serper"
    description = "Serper.dev Google 搜索（免费 2500次）"

    async def health_check(self) -> bool:
        return bool(os.environ.get("SERPER_API_KEY"))

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        api_key = os.environ.get("SERPER_API_KEY")
        if not api_key:
            return []

        proxy = Config.get_proxy()
        kwargs = {"timeout": request.timeout}
        if proxy:
            kwargs["proxy"] = proxy

        try:
            async with httpx.AsyncClient(**kwargs) as client:
                body = {
                    "q": request.query,
                    "num": min(request.max_results, 20),
                    "gl": "cn" if request.language in ("zh", "auto") else "us",
                    "hl": "zh-cn" if request.language in ("zh", "auto") else "en",
                }
                resp = await client.post(
                    "https://google.serper.dev/search",
                    json=body,
                    headers={"X-API-KEY": api_key},
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = []

                # 直接答案（Knowledge Graph）
                if data.get("knowledgeGraph"):
                    kg = data["knowledgeGraph"]
                    results.append(SearchResult(
                        title=kg.get("title", ""),
                        url=kg.get("website", "") or "",
                        snippet=kg.get("description", ""),
                        content=kg.get("description", ""),
                        source="serper_kg",
                        relevance=0.95,
                    ))

                # 普通搜索结果
                for item in data.get("organic", []):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        source="serper",
                        relevance=0.8,
                    ))

                return results
        except Exception:
            return []
