"""FastCode direct integration — 不依赖 FastCode 服务，直接调用库.

流程：GitHub URL → git clone → FastCode 直接分析 → 结构化结果
"""

import os
import re
import tempfile
import asyncio
import subprocess
from pathlib import Path
from typing import Optional

import httpx
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class FastCodeModule(BaseSearchModule):
    name = "fastcode"
    description = "代码仓库深度分析（FastCode — clone + AST + 语义搜索）"
    GITHUB_PATTERN = re.compile(
        r"(?:https?://)?github\.com/([^/]+)/([^/\s?#]+)"
    )
    SHORT_PATTERN = re.compile(r"^([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$")

    # FastCode project path
    FASTCODE_DIR = "/mnt/g/knowledge/project/FastCode"

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """分析代码仓库"""
        query = request.query.strip()
        repo_url = self._extract_repo_url(query)
        if not repo_url:
            return await self._search_github(query, request.max_results)

        # Full pipeline: clone → analyze
        results = []
        tmpdir = None
        try:
            # Step 1: Clone repo
            tmpdir = tempfile.mkdtemp(prefix="fastcode_")
            repo_name = repo_url.rstrip("/").split("/")[-1]
            repo_path = os.path.join(tmpdir, repo_name)

            clone = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth", "1", repo_url, repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(clone.communicate(), timeout=60)

            if clone.returncode != 0:
                return [SearchResult(
                    title=f"Clone failed: {repo_url}",
                    url=repo_url,
                    snippet=stderr.decode("utf-8", errors="replace")[:200],
                    source=self.name,
                    relevance=0.3,
                )]

            # Step 2: Get GitHub metadata
            gh_meta = await self._get_github_meta(repo_url)

            # Step 3: Analyze with FastCode CLI
            analysis = await self._analyze_with_fastcode(
                repo_path, request.depth, request.query
            )

            # Step 4: Build result
            content_parts = []
            if gh_meta:
                content_parts.append(f"## 基本信息\n{gh_meta}")
            content_parts.append(f"## 代码分析\n{analysis}")

            results.append(SearchResult(
                title=f"代码分析: {repo_url}",
                url=repo_url,
                snippet=f"仓库 {repo_name} 深度分析完成",
                content="\n\n".join(content_parts),
                source=self.name,
                relevance=0.95,
                metadata={
                    "repo_url": repo_url,
                    "type": "code_analysis",
                    "analysis_depth": request.depth,
                },
            ))

        except asyncio.TimeoutError:
            results.append(SearchResult(
                title="Analysis timeout",
                url=repo_url,
                snippet="Repository analysis timed out. Try a smaller repo.",
                source=self.name,
                relevance=0.3,
            ))
        except Exception as e:
            results.append(SearchResult(
                title="Analysis error",
                url=repo_url,
                snippet=str(e)[:200],
                source=self.name,
                relevance=0.3,
            ))
        finally:
            # Cleanup
            if tmpdir and os.path.exists(tmpdir):
                subprocess.run(["rm", "-rf", tmpdir], timeout=10)

        return results

    async def _analyze_with_fastcode(
        self, repo_path: str, depth: str, query: str
    ) -> str:
        """Use FastCode CLI to analyze repo"""
        env = os.environ.copy()
        # Load .env for FastCode
        env_file = os.path.join(self.FASTCODE_DIR, ".env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k] = v

        # Analysis queries based on depth
        queries = [
            "What is the overall architecture and main components?",
        ]
        if depth in ("normal", "deep"):
            queries.append("What are the core modules and their responsibilities?")
        if depth == "deep":
            queries.extend([
                "What design patterns are used?",
                "What are potential improvements?",
            ])

        results = []
        for q in queries:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "/home/zccyman/anaconda3/envs/stock/bin/python",
                    os.path.join(self.FASTCODE_DIR, "main.py"),
                    "query",
                    "--repo-path", repo_path,
                    "--query", q,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=self.FASTCODE_DIR,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=120
                )
                if proc.returncode == 0 and stdout:
                    answer = stdout.decode("utf-8", errors="replace").strip()
                    if answer:
                        results.append(f"### {q}\n{answer}\n")
                else:
                    err = stderr.decode("utf-8", errors="replace")[:200]
                    results.append(f"### {q}\n*Analysis unavailable: {err}*\n")
            except asyncio.TimeoutError:
                results.append(f"### {q}\n*Timeout*\n")
            except Exception as e:
                results.append(f"### {q}\n*Error: {str(e)[:100]}*\n")

        return "\n".join(results)

    async def _get_github_meta(self, repo_url: str) -> str:
        """Get basic GitHub metadata"""
        m = self.GITHUB_PATTERN.search(repo_url)
        if not m:
            return ""
        owner, repo = m.group(1), m.group(2)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"Accept": "application/vnd.github.v3+json"}
                token = os.environ.get("GITHUB_TOKEN")
                if token:
                    headers["Authorization"] = f"token {token}"
                resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}",
                    headers=headers,
                )
                if resp.status_code == 200:
                    d = resp.json()
                    parts = [
                        f"- **名称**: {d.get('full_name', '')}",
                        f"- **描述**: {d.get('description', '') or 'N/A'}",
                        f"- **语言**: {d.get('language', 'N/A')}",
                        f"- **Star**: {d.get('stargazers_count', 0)}",
                        f"- **Fork**: {d.get('forks_count', 0)}",
                        f"- **License**: {(d.get('license') or {}).get('spdx_id', 'N/A')}",
                        f"- **创建**: {d.get('created_at', 'N/A')[:10]}",
                    ]
                    return "\n".join(parts)
        except Exception:
            pass
        return ""

    async def _search_github(self, query: str, max_results: int) -> list[SearchResult]:
        """Fallback: search GitHub"""
        results = []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
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
        m = self.GITHUB_PATTERN.search(query)
        if m:
            return f"https://github.com/{m.group(1)}/{m.group(2)}"
        m = self.SHORT_PATTERN.match(query)
        if m:
            return f"https://github.com/{m.group(1)}/{m.group(2)}"
        return None
