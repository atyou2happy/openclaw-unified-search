import os
"""Vane (Perplexica) — 开源 AI 搜索引擎（34K⭐）.

Vane（原名 Perplexica）是开源的 Perplexity 替代品，使用 SearXNG + LLM
提供带引用的 AI 搜索回答。

项目: https://github.com/ItzCrazyKns/Vane (34K⭐)
License: MIT
API: POST http://localhost:3000/api/search
"""

import httpx
from app.modules.base import BaseSearchModule
from app.models import SearchRequest, SearchResult



VANE_URL = os.environ.get("VANE_URL", "http://localhost:3000")


class VaneModule(BaseSearchModule):
    """Vane (Perplexica) AI 搜索引擎 — 自托管，免费"""

    name = "vane"
    description = "Vane AI 搜索引擎（Perplexica，34K⭐，自托管）"

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{VANE_URL}/api/providers")
                return resp.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                # Vane search API
                payload = {
                    "query": request.query,
                    "searchMode": "balanced",  # speed | balanced | quality
                    "optimizationMode": "balanced",  # speed | quality
                }
                
                resp = await client.post(
                    f"{VANE_URL}/api/search",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "UnifiedSearch/0.7.0",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            
            # Vane 返回结构：{ sources: [...], message: "..." }
            sources = data.get("sources", [])
            message = data.get("message", "")
            
            # 添加 AI 生成的主答案
            if message:
                results.append(SearchResult(
                    title=f"AI Summary: {request.query[:50]}",
                    url="",
                    snippet=message[:500],
                    source="vane-ai",
                    metadata={
                        "type": "ai-summary",
                    },
                ))
            
            # 添加引用来源
            for src in sources:
                title = src.get("title", "").strip()
                url = src.get("url", "")
                snippet = src.get("text", src.get("description", "")).strip()

                if not title:
                    continue

                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet[:300],
                    source="vane",
                    metadata={
                        "type": "web",
                    },
                ))

            return results[:request.max_results + 1]  # +1 for AI summary

        except Exception:
            return []
