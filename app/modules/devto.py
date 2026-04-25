"""DevTo — 技术文章搜索（免费，无需 API Key）.

Dev.to (DEV Community) 是全球最大的开发者社区之一。
API 完全免费，无需 Key，适合技术文章搜索。

API: https://dev.to/api/articles
Docs: https://developers.forem.com/api
"""

import httpx
from app.modules.base import BaseSearchModule
from app.models import SearchRequest, SearchResult
from app.config import Config


class DevToModule(BaseSearchModule):
    """DevTo 技术文章搜索 — 免费、无需 Key"""

    name = "devto"
    description = "DevTo 技术文章搜索（免费，无需 API Key）"

    async def health_check(self) -> bool:
        return True  # DEV API 永远在线

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                # DevTo search API
                params = {
                    "per_page": min(request.max_results, 10),
                    "tag": "",  # 可选：按 tag 过滤
                }

                # DevTo 搜索策略：尝试 tag 匹配，否则取最新文章过滤
                words = request.query.lower().split()
                tag_candidates = ["python", "javascript", "react", "rust", "go", "docker",
                                  "kubernetes", "ai", "machinelearning", "webdev", "tutorial",
                                  "fastapi", "django", "flask", "llm", "opensource", "programming",
                                  "database", "security", "devops", "cloud", "agents", "rag",
                                  "llms", "chatgpt", "openai", "ollama"]
                matched_tags = [w for w in words if w in tag_candidates]
                if matched_tags:
                    params["tag"] = matched_tags[0]
                else:
                    # 无 tag 匹配时，获取更多文章做关键词过滤
                    params["per_page"] = min(request.max_results * 3, 30)

                resp = await client.get(
                    "https://dev.to/api/articles",
                    params=params,
                    headers={"User-Agent": "UnifiedSearch/0.8.0"},
                )
                resp.raise_for_status()
                articles = resp.json()

            results = []
            for article in articles:
                title = article.get("title", "").strip()
                url = article.get("url", "")
                desc = article.get("description", "").strip()
                tags = article.get("tag_list", [])
                positive_reactions = article.get("positive_reactions_count", 0)
                comments = article.get("comments_count", 0)
                reading_time = article.get("reading_time_minutes", 0)
                author = article.get("user", {}).get("name", "")

                # 相关性过滤：任意关键词命中标题或描述
                title_lower = title.lower()
                desc_lower = desc.lower()
                if not any(w in title_lower or w in desc_lower for w in words):
                    continue

                if not title or not url:
                    continue

                snippet = desc if desc else f"By {author} | ⬆{positive_reactions} | 💬{comments} | {reading_time}min"

                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="devto",
                    metadata={
                        "tags": tags,
                        "reactions": positive_reactions,
                        "comments": comments,
                        "reading_time": reading_time,
                        "author": author,
                        "type": "article",
                    },
                ))

            return results

        except Exception:
            return []
