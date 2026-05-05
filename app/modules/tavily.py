"""Tavily Search module — 免费 1000次/月, 专为 AI Agent 设计."""

import logging
import os
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class TavilyModule(BaseSearchModule):
    name = "tavily"
    description = "Tavily Search API（免费 1000次/月, AI 优化）"

    async def health_check(self) -> bool:
        return bool(os.environ.get("TAVILY_API_KEY"))

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return []

        try:
            client = await self.get_http_client(timeout=request.timeout)
            body = {
                "api_key": api_key,
                "query": request.query,
                "max_results": min(request.max_results, 10),
                "search_depth": "advanced" if request.depth == "deep" else "basic",
                "include_answer": True,
                "include_raw_content": request.depth == "deep",
            }
            resp = await client.post(
                "https://api.tavily.com/search",
                json=body,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []

            # Tavily 有直接答案
            if data.get("answer"):
                results.append(SearchResult(
                    title=f"Tavily Answer: {request.query}",
                    url="",
                    snippet=data["answer"][:500],
                    content=data["answer"],
                    source="tavily_answer",
                    relevance=0.95,
                ))

            # 搜索结果
            for item in data.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", "")[:500],
                    content=item.get("raw_content", "")[:8000] if request.depth == "deep" else "",
                    source="tavily",
                    relevance=float(item.get("score", 0.7)),
                ))
            return results
        except Exception:
            return []
