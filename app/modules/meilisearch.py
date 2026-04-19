"""Meilisearch module — 本地知识库搜索（459篇wiki）"""

import httpx
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

MEILI_URL = "http://localhost:7700"
MASTER_KEY = "claw2026"
INDEX_NAME = "wiki"


class MeilisearchModule(BaseSearchModule):
    name = "meilisearch"
    description = "本地知识库搜索（Meilisearch，459篇wiki，毫秒级）"

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                r = await client.get(f"{MEILI_URL}/health")
                return r.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        query = request.query
        limit = request.max_results or 5

        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                r = await client.post(
                    f"{MEILI_URL}/indexes/{INDEX_NAME}/search",
                    headers={
                        "Authorization": f"Bearer {MASTER_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "q": query,
                        "limit": limit,
                        "attributesToCrop": ["content"],
                        "cropLength": 200,
                        "attributesToHighlight": ["title", "content"],
                    },
                )

                if r.status_code != 200:
                    return []

                data = r.json()
                results = []

                for hit in data.get("hits", []):
                    # Get highlighted content if available
                    formatted = hit.get("_formatted", {})
                    content_preview = formatted.get("content", hit.get("content", ""))[:300]
                    title = formatted.get("title", hit.get("title", ""))

                    results.append(SearchResult(
                        title=f"📚 {title}",
                        url=hit.get("path", ""),
                        content=content_preview,
                        source="meilisearch",
                        metadata={
                            "tags": hit.get("tags", []),
                            "category": hit.get("category", ""),
                        },
                    ))

                return results

        except Exception:
            return []
