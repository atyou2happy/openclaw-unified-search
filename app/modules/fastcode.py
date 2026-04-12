"""FastCode integration module — 代码仓库深度分析.

流程：GitHub URL → clone → FastCode 分析 → 结构化结果
需要 FastCode 服务运行在 localhost:8000
"""

import re
import os
import tempfile
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class FastCodeModule(BaseSearchModule):
    name = "fastcode"
    description = "代码仓库深度分析（FastCode — clone + AST + 语义搜索）"
    FASTCODE_URL = "http://localhost:8000"
    GITHUB_PATTERN = re.compile(
        r"(?:https?://)?github\.com/([^/]+)/([^/\s?#]+)"
    )
    SHORT_PATTERN = re.compile(r"^([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.FASTCODE_URL}/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """分析代码仓库"""
        query = request.query.strip()
        repo_url = self._extract_repo_url(query)
        if not repo_url:
            return await self._search_github(query, request.max_results)

        # Full pipeline: load → index → analyze
        results = []
        try:
            # Step 1: Load and index via FastCode
            async with httpx.AsyncClient(timeout=120) as client:
                # Load and index
                resp = await client.post(
                    f"{self.FASTCODE_URL}/load-and-index",
                    json={"source": repo_url, "is_url": True},
                    timeout=120,
                )
                if resp.status_code != 200:
                    return [SearchResult(
                        title=f"FastCode analysis failed",
                        url=repo_url,
                        snippet=f"Error: {resp.text[:200]}",
                        source=self.name,
                        relevance=0.5,
                    )]

                data = resp.json()
                summary = data.get("summary", {})

                # Step 2: Get repository overview
                repo_overview = await self._get_overview(client)

                # Step 3: Run analysis queries
                analysis_results = await self._analyze_repo(
                    client, request.depth
                )

                # Build result
                content_parts = []
                if repo_overview:
                    content_parts.append(f"## 仓库概览\n{repo_overview}")
                if analysis_results:
                    content_parts.append(f"## 深度分析\n{analysis_results}")

                results.append(SearchResult(
                    title=f"代码分析: {repo_url}",
                    url=repo_url,
                    snippet=summary.get("overview", "")[:500] if isinstance(summary, dict) else str(summary)[:500],
                    content="\n\n".join(content_parts),
                    source=self.name,
                    relevance=0.95,
                    metadata={
                        "repo_url": repo_url,
                        "type": "code_analysis",
                        "analysis_depth": request.depth,
                    },
                ))

        except httpx.TimeoutException:
            results.append(SearchResult(
                title="FastCode analysis timeout",
                url=repo_url,
                snippet="Repository analysis timed out (>120s). Try a smaller repo.",
                source=self.name,
                relevance=0.3,
            ))
        except Exception as e:
            results.append(SearchResult(
                title="FastCode error",
                url=repo_url,
                snippet=str(e)[:200],
                source=self.name,
                relevance=0.3,
            ))

        return results

    async def _get_overview(self, client: httpx.AsyncClient) -> str:
        """Get repository summary"""
        try:
            resp = await client.get(f"{self.FASTCODE_URL}/summary", timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                summary = data.get("summary", {})
                if isinstance(summary, dict):
                    parts = []
                    for k, v in summary.items():
                        parts.append(f"**{k}**: {v}")
                    return "\n".join(parts)
                return str(summary)
        except Exception:
            pass
        return ""

    async def _analyze_repo(self, client: httpx.AsyncClient, depth: str) -> str:
        """Run analysis queries on the repo"""
        queries = [
            "What is the overall architecture and main components of this codebase?",
            "What are the core modules and their responsibilities?",
        ]
        if depth == "deep":
            queries.extend([
                "What design patterns are used in this codebase?",
                "What are the main dependencies and how do they interact?",
                "What are the potential areas for improvement?",
            ])

        results = []
        for q in queries:
            try:
                resp = await client.post(
                    f"{self.FASTCODE_URL}/query",
                    json={"question": q},
                    timeout=60,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data.get("answer", "")
                    if answer:
                        results.append(f"### {q}\n{answer}\n")
            except Exception:
                continue

        return "\n".join(results)

    async def _search_github(self, query: str, max_results: int) -> list[SearchResult]:
        """Fallback: search GitHub if no repo URL detected"""
        import httpx as hx
        results = []
        try:
            async with hx.AsyncClient(timeout=15) as client:
                headers = {"Accept": "application/vnd.github.v3+json"}
                token = os.environ.get("GITHUB_TOKEN")
                if token:
                    headers["Authorization"] = f"token {token}"
                resp = await client.get(
                    "https://api.github.com/search/repositories",
                    params={"q": query, "per_page": max_results},
                    headers=headers,
                )
                if resp.status_code == 200:
                    for item in resp.json().get("items", []):
                        results.append(SearchResult(
                            title=item.get("full_name", ""),
                            url=item.get("html_url", ""),
                            snippet=item.get("description", "") or "",
                            source="github",
                            relevance=min(item.get("stargazers_count", 0) / 1000, 1.0),
                        ))
        except Exception:
            pass
        return results

    def _extract_repo_url(self, query: str) -> Optional[str]:
        """Extract GitHub repo URL from query"""
        # Full URL
        m = self.GITHUB_PATTERN.search(query)
        if m:
            return f"https://github.com/{m.group(1)}/{m.group(2)}"

        # Short form: owner/repo
        m = self.SHORT_PATTERN.match(query)
        if m:
            return f"https://github.com/{m.group(1)}/{m.group(2)}"

        return None
