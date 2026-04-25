"""Exa AI Search Module — 高质量语义搜索.

Exa (exa.ai) 是一个 AI 原生搜索引擎，支持语义搜索和精确搜索。
免费 tier: 1000 次搜索/月。
"""

import httpx
from app.modules.base import BaseSearchModule
from app.models import SearchResult
from app.config import Config


class ExaModule(BaseSearchModule):
    """Exa AI 搜索 — 语义搜索，高质量结果"""

    name = "exa"
    description = "Exa AI 语义搜索（免费 1000次/月）"

    def __init__(self):
        super().__init__()
        self._api_key = None
        self._base_url = "https://api.exa.ai"

    def _get_api_key(self) -> str | None:
        """Get API key from env"""
        if self._api_key:
            return self._api_key
        import os
        self._api_key = os.environ.get("EXA_API_KEY")
        return self._api_key

    async def is_available(self) -> bool:
        """Check if Exa API key is configured"""
        return bool(self._get_api_key())

    async def search(self, request, **kwargs) -> list[SearchResult]:
        """Search using Exa AI"""
        api_key = self._get_api_key()
        if not api_key:
            return []

        try:
            async with httpx.AsyncClient(
                timeout=request.timeout if hasattr(request, 'timeout') else 15,
                proxy=Config.get_proxy(),
            ) as client:
                resp = await client.post(
                    f"{self._base_url}/search",
                    headers={
                        "x-api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": request.query,
                        "num_results": min(request.max_results, 10),
                        "use_autoprompt": True,
                        "type": "auto",  # auto: 让 Exa 自动选择 keyword/neural
                        "contents": {
                            "text": {"maxCharacters": 500},
                            "highlights": True,
                        },
                    },
                )

                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = []
                for item in data.get("results", []):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("highlights", [""])[0] if item.get("highlights") else item.get("text", "")[:300],
                        source="exa",
                        relevance=0.8,  # Exa 语义搜索默认高质量
                        content=item.get("text", "")[:1000] if item.get("text") else None,
                        metadata={"engine_primary": "exa"},
                    ))

                return results

        except Exception:
            return []
