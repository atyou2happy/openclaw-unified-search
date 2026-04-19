"""Gemini search module — 通过 TabBitBrowser CDP 访问 Google Gemini 获取 AI 搜索结果."""

import asyncio
import json
import sys
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class GeminiModule(BaseSearchModule):
    name = "gemini"
    description = "Google Gemini AI 搜索（TabBitBrowser CDP，高质量）"

    def __init__(self):
        super().__init__()
        self._cdp_port = Config.TABBIT_CDP_PORT
        self._script_path = "/mnt/g/knowledge/claw-mem/tools/gemini_cdp_search.py"

    async def health_check(self) -> bool:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                resp = await client.get(f"http://localhost:{self._cdp_port}/json")
                return resp.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        timeout = min(request.timeout, 180)
        max_chars = 12000 if request.depth == "deep" else 6000

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                self._script_path,
                request.query,
                "--port", str(self._cdp_port),
                "--timeout", str(timeout),
                "--max-chars", str(max_chars),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout + 60
            )

            if proc.returncode != 0:
                self._available = False
                return []

            content = stdout.decode("utf-8", errors="replace").strip()
            if not content:
                return []

            return self._parse_results(content, request)

        except asyncio.TimeoutError:
            return []
        except Exception:
            return []

    def _parse_results(self, content: str, request: SearchRequest) -> list[SearchResult]:
        results: list[SearchResult] = []

        try:
            data = json.loads(content)
            answer = data.get("answer", "")
            if answer and len(answer.strip()) > 20:
                results.append(
                    SearchResult(
                        title=f"Gemini AI: {request.query}",
                        url="",
                        snippet=answer[:500],
                        content=answer,
                        source=self.name,
                        relevance=0.95,
                        metadata={"type": "ai_answer"},
                    )
                )
        except (json.JSONDecodeError, TypeError):
            # Fallback: treat raw output as answer
            if content and len(content.strip()) > 20:
                results.append(
                    SearchResult(
                        title=f"Gemini AI: {request.query}",
                        url="",
                        snippet=content[:500],
                        content=content,
                        source=self.name,
                        relevance=0.95,
                        metadata={"type": "ai_answer"},
                    )
                )

        return results[:request.max_results]
