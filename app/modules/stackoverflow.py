"""StackOverflow Search Module — StackExchange API 搜索.

免费，无需 API key。
使用 StackExchange API /search/advanced 端点。
"""

import logging
from app.modules.base import BaseSearchModule
from app.models import SearchResult

logger = logging.getLogger(__name__)


class StackOverflowModule(BaseSearchModule):
    """StackOverflow 搜索 — 编程问题精准匹配"""

    name = "stackoverflow"
    description = "StackOverflow 编程问答搜索（免费）"

    def __init__(self):
        super().__init__()

    async def is_available(self) -> bool:
        """Always available (free, no key needed)"""
        return True

    async def search(self, request, **kwargs) -> list[SearchResult]:
        """Search StackOverflow via StackExchange API"""
        try:
            client = await self.get_http_client(timeout=15)
            params = {
                "order": "desc",
                "sort": "relevance",
                "q": request.query,
                "site": "stackoverflow",
                "pagesize": min(request.max_results, 10),
                "filter": "withbody",  # 包含正文
            }

            resp = await client.get(
                "https://api.stackexchange.com/2.3/search/advanced",
                params=params,
            )

            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for item in data.get("items", []):
                # 清理 HTML 标签
                body = item.get("body", "")
                import re
                body_clean = re.sub(r'<[^>]+>', '', body)[:500]

                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=body_clean[:300] if body_clean else "",
                    source="stackoverflow",
                    relevance=min(item.get("score", 0) / 100, 1.0),  # 基于 score 计算
                    metadata={
                        "engine_primary": "stackoverflow",
                        "score": item.get("score", 0),
                        "answer_count": item.get("answer_count", 0),
                        "is_answered": item.get("is_answered", False),
                        "tags": item.get("tags", [])[:5],
                    },
                ))

            return results

        except Exception:
            return []
