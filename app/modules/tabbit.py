"""TabBitBrowser search module — 核心 AI 搜索（结构化多结果）.

v2 改进：
- 解析搜索结果为多条结构化结果（标题+URL+snippet）
- AI 回答作为最高质量结果单独输出
- 支持深度模式返回更多内容
"""

import asyncio
import json
import re
import sys
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class TabBitModule(BaseSearchModule):
    name = "tabbit"
    description = "TabBitBrowser AI 搜索（本地 CDP，质量最高）"

    def __init__(self):
        super().__init__()
        self._cdp_port = Config.TABBIT_CDP_PORT
        self._script_path = Config.TABBIT_SCRIPT_PATH

    async def health_check(self) -> bool:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                resp = await client.get(
                    f"http://localhost:{self._cdp_port}/json",
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        timeout = min(request.timeout, Config.TABBIT_TIMEOUT)
        max_chars = 12000 if request.depth == "deep" else 6000

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                self._script_path,
                request.query,
                "--port",
                str(self._cdp_port),
                "--timeout",
                str(timeout),
                "--max-chars",
                str(max_chars),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout + 10
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

    def _parse_results(
        self, content: str, request: SearchRequest
    ) -> list[SearchResult]:
        """将 TabBit 输出解析为多条结构化结果

        策略：
        1. 尝试 JSON 解析（如果脚本返回结构化数据）
        2. 回退到文本解析（提取 URL + 标题 + 段落）
        3. AI 回答始终作为第一条结果
        """
        results: list[SearchResult] = []

        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return self._parse_json_results(data, request)
            if isinstance(data, list):
                return self._parse_json_list(data, request)
        except (json.JSONDecodeError, TypeError):
            pass

        urls_found = re.findall(
            r"(?:^|\n)\s*(?:\d+[\.\)]\s*)?(\[([^\]]+)\]\s*\((https?://[^\s\)]+)\)|(https?://[^\s]+))",
            content,
        )

        paragraphs = [
            p.strip()
            for p in content.split("\n\n")
            if p.strip() and len(p.strip()) > 30
        ]

        answer_text = content
        if paragraphs:
            answer_text = "\n\n".join(paragraphs[:3])

        results.append(
            SearchResult(
                title=f"TabBit AI: {request.query}",
                url="",
                snippet=answer_text[:500],
                content=content if request.depth != "quick" else answer_text[:3000],
                source=self.name,
                relevance=0.95,
                metadata={"type": "ai_answer"},
            )
        )

        seen_urls = set()
        for match in urls_found:
            title = match[1] if match[1] else ""
            url = match[2] if match[2] else match[3]
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            snippet = self._find_snippet_near_url(content, url)
            results.append(
                SearchResult(
                    title=title or self._title_from_url(url),
                    url=url,
                    snippet=snippet,
                    source=self.name,
                    relevance=0.85,
                    metadata={"type": "search_result"},
                )
            )

        return results[: request.max_results]

    def _parse_json_results(
        self, data: dict, request: SearchRequest
    ) -> list[SearchResult]:
        results: list[SearchResult] = []

        if data.get("answer"):
            results.append(
                SearchResult(
                    title=f"TabBit AI: {request.query}",
                    url="",
                    snippet=data["answer"][:500],
                    content=data["answer"],
                    source=self.name,
                    relevance=0.95,
                    metadata={"type": "ai_answer"},
                )
            )

        for item in data.get("results", data.get("items", [])):
            if isinstance(item, dict):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", item.get("href", "")),
                        snippet=item.get("snippet", item.get("content", ""))[:500],
                        source=self.name,
                        relevance=float(item.get("score", 0.85)),
                        metadata={"type": "search_result"},
                    )
                )
            elif isinstance(item, str) and item.startswith("http"):
                results.append(
                    SearchResult(
                        title=self._title_from_url(item),
                        url=item,
                        snippet="",
                        source=self.name,
                        relevance=0.8,
                        metadata={"type": "search_result"},
                    )
                )

        return (
            results[: request.max_results]
            if results
            else [
                SearchResult(
                    title=f"TabBit AI: {request.query}",
                    url="",
                    snippet=str(data)[:500],
                    content=str(data),
                    source=self.name,
                    relevance=0.95,
                    metadata={"type": "ai_answer"},
                )
            ]
        )

    def _parse_json_list(
        self, data: list, request: SearchRequest
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        for item in data:
            if isinstance(item, dict):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", item.get("href", "")),
                        snippet=item.get("snippet", item.get("content", ""))[:500],
                        source=self.name,
                        relevance=float(item.get("score", 0.85)),
                        metadata={"type": "search_result"},
                    )
                )
            elif isinstance(item, str):
                results.append(
                    SearchResult(
                        title=item[:100],
                        url="",
                        snippet=item[:500],
                        source=self.name,
                        relevance=0.8,
                        metadata={"type": "search_result"},
                    )
                )

        return (
            results[: request.max_results]
            if results
            else [
                SearchResult(
                    title=f"TabBit AI: {request.query}",
                    url="",
                    snippet=str(data)[:500],
                    source=self.name,
                    relevance=0.95,
                    metadata={"type": "ai_answer"},
                )
            ]
        )

    @staticmethod
    def _find_snippet_near_url(content: str, url: str) -> str:
        idx = content.find(url)
        if idx < 0:
            return ""
        start = max(0, idx - 200)
        end = min(len(content), idx + len(url) + 200)
        snippet = content[start:end].replace(url, "").strip()
        snippet = re.sub(r"\s+", " ", snippet)[:300]
        return snippet

    @staticmethod
    def _title_from_url(url: str) -> str:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            path = parsed.path.rstrip("/").split("/")[-1]
            return (
                path.replace("-", " ").replace("_", " ").title()
                if path
                else parsed.netloc
            )
        except Exception:
            return url[:80]
