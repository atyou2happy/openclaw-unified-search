"""Perplexity AI module — 最火的 AI 搜索，答案质量高."""

import os
import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class PerplexityModule(BaseSearchModule):
    """Perplexity AI 搜索 — 需要 API Key"""

    name = "perplexity"
    description = "Perplexity AI 搜索（答案引擎）"

    MODEL = "llama-3.1-sonar-large-128k-online"

    async def health_check(self) -> bool:
        return bool(os.environ.get("PERPLEXITY_API_KEY"))

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        api_key = os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            return []

        proxy = Config.get_proxy()
        kwargs = {"timeout": request.timeout}
        if proxy:
            kwargs["proxy"] = proxy

        try:
            async with httpx.AsyncClient(**kwargs) as client:
                # Perplexity 需要将搜索转为对话
                resp = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    json={
                        "model": self.MODEL,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful AI assistant.",
                            },
                            {
                                "role": "user",
                                "content": f"Search and provide information about: {request.query}",
                            },
                        ],
                        "max_tokens": 2000,
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )

                if not content:
                    return []

                # 解析结果，提取引用
                results = []

                # 直接答案作为第一个结果（高相关性）
                results.append(
                    SearchResult(
                        title=f"Perplexity Answer: {request.query[:50]}",
                        url="https://perplexity.ai",
                        snippet=content[:300],
                        content=content,
                        source="perplexity",
                        relevance=0.95,
                    )
                )

                # 提取 citations
                citations = data.get("citations", [])
                for i, cite in enumerate(citations[: request.max_results]):
                    results.append(
                        SearchResult(
                            title=cite.get("title", f"Source {i + 1}")[:100],
                            url=cite.get("url", ""),
                            snippet=cite.get("text", "")[:200],
                            source="perplexity_cite",
                            relevance=0.8,
                        )
                    )

                return results
        except Exception:
            return []
