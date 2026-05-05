"""You.com module — AI 增强的搜索引擎."""

import logging
import os
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class YouModule(BaseSearchModule):
    """You.com 搜索 — AI 增强的搜索引擎"""

    name = "you"
    description = "You.com AI 搜索"

    async def health_check(self) -> bool:
        return bool(os.environ.get("YOU_API_KEY"))

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        api_key = os.environ.get("YOU_API_KEY")
        if not api_key:
            return []

        try:
            client = await self.get_http_client(timeout=request.timeout)
            resp = await client.get(
                "https://api.you.com/search",
                params={
                    "query": request.query,
                    "num": min(request.max_results, 20),
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []

            for item in data.get("organic", []):
                results.append(
                    SearchResult(
                        title=item.get("title", "")[:200],
                        url=item.get("url", ""),
                        snippet=item.get("snippet", ""),
                        source="you",
                        relevance=0.75,
                    )
                )

            # AI 摘要
            if data.get("ai_summary"):
                results.insert(
                    0,
                    SearchResult(
                        title=f"You.com AI: {request.query[:50]}",
                        url="https://you.com",
                        snippet=data.get("ai_summary", "")[:300],
                        content=data.get("ai_summary", ""),
                        source="you_ai",
                        relevance=0.9,
                    ),
                )

            return results
        except Exception:
            return []
