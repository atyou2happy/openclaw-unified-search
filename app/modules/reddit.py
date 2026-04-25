"""Reddit — Reddit 社区搜索（免费，无需 API Key）.

Reddit 的 JSON API 可以直接通过在 URL 后加 .json 获取搜索结果。
无需 API Key，有速率限制但够用。

API: https://www.reddit.com/search.json?q=...
"""

import httpx
from app.modules.base import BaseSearchModule
from app.models import SearchRequest, SearchResult
from app.config import Config


class RedditModule(BaseSearchModule):
    """Reddit 社区搜索 — 免费、无需 Key"""

    name = "reddit"
    description = "Reddit 社区搜索（免费，无需 API Key）"

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://www.reddit.com/.json",
                    headers={"User-Agent": "UnifiedSearch/0.8.0"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                params = {
                    "q": request.query,
                    "limit": min(request.max_results, 10),
                    "sort": "relevance",
                    "type": "link",
                }

                resp = await client.get(
                    "https://www.reddit.com/search.json",
                    params=params,
                    headers={"User-Agent": "UnifiedSearch/0.8.0 (research bot)"},
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            children = data.get("data", {}).get("children", [])

            for child in children:
                post = child.get("data", {})
                title = post.get("title", "").strip()
                url = f"https://www.reddit.com{post.get('permalink', '')}"
                snippet = post.get("selftext", "")[:300].strip()
                subreddit = post.get("subreddit", "")
                score = post.get("score", 0)
                num_comments = post.get("num_comments", 0)
                author = post.get("author", "")

                if not title:
                    continue

                if not snippet:
                    snippet = f"r/{subreddit} | ↑{score} | 💬{num_comments}"

                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="reddit",
                    metadata={
                        "subreddit": subreddit,
                        "score": score,
                        "comments": num_comments,
                        "author": author,
                        "type": "social",
                    },
                ))

            return results

        except Exception:
            return []
