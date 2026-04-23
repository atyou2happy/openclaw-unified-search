"""Hacker News search module — HN Algolia API，免费无需 key."""

import httpx
from datetime import datetime
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

import logging
logger = logging.getLogger(__name__)


class HackerNewsModule(BaseSearchModule):
    name = "hackernews"
    description = "Hacker News 搜索（Algolia API，免费）"

    SEARCH_URL = "https://hn.algolia.com/api/v1/search"
    SEARCH_BY_DATE_URL = "https://hn.algolia.com/api/v1/search_by_date"

    async def health_check(self) -> bool:
        return True  # HN Algolia API always available
        _ = None  #
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    self.SEARCH_URL,
                    params={"query": "test", "hitsPerPage": 1}
                )
                return r.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        query = request.query.strip()
        max_results = request.max_results

        results = []

        try:
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                # Search by relevance (default Algolia)
                params = {
                    "query": query,
                    "hitsPerPage": min(max_results, 20),
                    "tags": "story",
                    "numericFilters": "points>5",
                }

                r = await client.get(self.SEARCH_URL, params=params)

                if r.status_code != 200:
                    logger.warning(f"HN search failed: {r.status_code}")
                    return results

                data = r.json()
                hits = data.get("hits", [])

                for hit in hits:
                    title = hit.get("title", "")
                    url = hit.get("url", "")
                    object_id = hit.get("objectID", "")
                    points = hit.get("points", 0) or 0
                    num_comments = hit.get("num_comments", 0) or 0
                    author = hit.get("author", "")
                    created_at = hit.get("created_at", "")

                    # HN discussion link
                    hn_url = f"https://news.ycombinator.com/item?id={object_id}"

                    # Use HN link if no external URL
                    if not url:
                        url = hn_url

                    snippet = f"by {author} · ↑{points} · 💬{num_comments}"

                    ts = None
                    if created_at:
                        try:
                            ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        except Exception:
                            pass

                    results.append(SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source=self.name,
                        relevance=min(points / 200, 1.0) if points > 0 else 0.1,
                        timestamp=ts,
                        metadata={
                            "points": points,
                            "num_comments": num_comments,
                            "author": author,
                            "hn_url": hn_url,
                        }
                    ))

        except Exception as e:
            logger.error(f"HN search error: {e}")

        return results[:max_results]
