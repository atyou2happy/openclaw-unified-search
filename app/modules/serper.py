"""Serper.dev module — Google 搜索结果, 免费 2500次."""

import logging
import os
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class SerperModule(BaseSearchModule):
    name = "serper"
    description = "Serper.dev Google 搜索（免费 2500次）"

    async def health_check(self) -> bool:
        return bool(os.environ.get("SERPER_API_KEY"))

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        api_key = os.environ.get("SERPER_API_KEY")
        if not api_key:
            return []

        try:
            client = await self.get_http_client(timeout=request.timeout)
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
