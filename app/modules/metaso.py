"""Metaso (秘塔AI搜索) module — 中文AI搜索最强引擎."""

import os
import httpx
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class MetasoModule(BaseSearchModule):
    name = "metaso"
    description = "秘塔AI搜索（中文最强，支持简洁/深入/研究模式）"
    BASE_URL = "http://127.0.0.1:8000"

    def _get_token(self) -> str:
        return os.environ.get("METASO_TOKEN", "")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                resp = await client.get(f"{self.BASE_URL}")
                return resp.status_code in (200, 401, 403)
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        token = self._get_token()
        if not token:
            return []

        try:
            async with httpx.AsyncClient(timeout=request.timeout, trust_env=False) as client:
                # 使用 OpenAI 兼容接口
                resp = await client.post(
                    f"{self.BASE_URL}/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}",
                    },
                    json={
                        "model": "metaso",
                        "messages": [
                            {"role": "user", "content": request.query}
                        ],
                        "stream": False,
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                content = ""

                # 解析响应
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")

                if not content:
                    return []

                return [SearchResult(
                    title=f"秘塔AI搜索: {request.query}",
                    url="https://metaso.cn",
                    snippet=content[:500],
                    content=content[:8000] if request.depth != "quick" else "",
                    source="metaso",
                    relevance=0.9,
                )]
        except Exception:
            return []
