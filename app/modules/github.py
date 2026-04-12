"""GitHub module — 仓库搜索 + Zread.ai 深度分析."""

import os
import re
from datetime import datetime
import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class GitHubModule(BaseSearchModule):
    name = "github"
    description = "GitHub 仓库搜索 + Zread.ai 深度仓库分析"
    BASE_URL = "https://api.github.com"
    ZREAD_URL = "https://zread.ai"
    # 匹配 owner/repo 格式
    REPO_PATTERN = re.compile(r"^([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$")
    # 匹配 GitHub URL
    URL_PATTERN = re.compile(r"github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)")

    def _headers(self) -> dict:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "unified-search",
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"
        return headers

    def _proxy_kwargs(self, **kwargs):
        proxy = Config.get_proxy()
        if proxy:
            kwargs["proxy"] = proxy
        return kwargs

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(**self._proxy_kwargs(timeout=10)) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/rate_limit",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """智能搜索：检测 owner/repo 格式 → Zread 深度分析，否则 GitHub 搜索"""
        query = request.query.strip()

        # 检测是否为 owner/repo 格式
        m = self.REPO_PATTERN.match(query)
        if not m:
            m = self.URL_PATTERN.search(query)

        if m:
            owner, repo = m.group(1), m.group(2)
            # 去除 .git 后缀
            repo = repo.rstrip(".git") if repo.endswith(".git") else repo

            if request.depth in ("normal", "deep"):
                # Zread 深度分析
                zread = await self._zread_analyze(owner, repo, request)
                if zread:
                    return zread

            # fallback: GitHub API 基本信息
            gh = await self._github_repo_info(owner, repo)
            if gh:
                return gh

        # 普通搜索
        return await self._github_search(request)

    async def _zread_analyze(
        self, owner: str, repo: str, request: SearchRequest
    ) -> list[SearchResult] | None:
        """通过 Jina Reader 提取 Zread.ai 的仓库分析报告"""
        try:
            async with httpx.AsyncClient(**self._proxy_kwargs(timeout=30)) as client:
                resp = await client.get(
                    f"https://r.jina.ai/{self.ZREAD_URL}/{owner}/{repo}",
                    headers={"Accept": "text/plain"},
                )
                if resp.status_code != 200 or len(resp.text) < 200:
                    return None

                content = resp.text
                max_chars = 12000 if request.depth == "deep" else 8000
                return [SearchResult(
                    title=f"Zread: {owner}/{repo}",
                    url=f"{self.ZREAD_URL}/{owner}/{repo}",
                    snippet=content[:500],
                    content=content[:max_chars],
                    source="zread",
                    relevance=0.95,
                    metadata={
                        "type": "repo_analysis",
                        "repo": f"{owner}/{repo}",
                    },
                )]
        except Exception:
            return None

    async def _github_repo_info(self, owner: str, repo: str) -> list[SearchResult]:
        """GitHub API 获取仓库基本信息"""
        try:
            async with httpx.AsyncClient(**self._proxy_kwargs(timeout=15)) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/repos/{owner}/{repo}",
                    headers=self._headers(),
                )
                if resp.status_code != 200:
                    return []

                d = resp.json()
                content_parts = [
                    f"# {d.get('full_name', '')}",
                    f"\n{d.get('description', '') or ''}",
                    f"\n**Language:** {d.get('language', 'N/A')}",
                    f"**Stars:** {d.get('stargazers_count', 0)}",
                    f"**Forks:** {d.get('forks_count', 0)}",
                    f"**License:** {(d.get('license') or {}).get('spdx_id', 'N/A')}",
                    f"**Topics:** {', '.join(d.get('topics', []))}",
                    f"\n🔗 [Zread 深度分析]({self.ZREAD_URL}/{owner}/{repo})",
                ]
                return [SearchResult(
                    title=d.get("full_name", ""),
                    url=d.get("html_url", ""),
                    snippet=d.get("description", "") or "",
                    content="\n".join(content_parts),
                    source="github",
                    relevance=0.85,
                    metadata={
                        "stars": d.get("stargazers_count", 0),
                        "language": d.get("language", ""),
                        "license": (d.get("license") or {}).get("spdx_id", ""),
                        "forks": d.get("forks_count", 0),
                        "topics": d.get("topics", []),
                    },
                )]
        except Exception:
            return []

    async def _github_search(self, request: SearchRequest) -> list[SearchResult]:
        """普通 GitHub 仓库搜索"""
        try:
            async with httpx.AsyncClient(**self._proxy_kwargs(timeout=request.timeout)) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/search/repositories",
                    params={"q": request.query, "per_page": request.max_results},
                    headers=self._headers(),
                )
                if resp.status_code != 200:
                    return []

                results = []
                for item in resp.json().get("items", []):
                    owner_repo = item.get("full_name", "")
                    results.append(SearchResult(
                        title=owner_repo,
                        url=item.get("html_url", ""),
                        snippet=item.get("description", "") or "",
                        source="github",
                        relevance=min(item.get("stargazers_count", 0) / 1000, 1.0),
                        metadata={
                            "stars": item.get("stargazers_count", 0),
                            "language": item.get("language", ""),
                            "zread": f"{self.ZREAD_URL}/{owner_repo}",
                        },
                    ))
                return results
        except Exception:
            return []

    async def get_readme(self, owner: str, repo: str) -> str | None:
        """获取仓库 README"""
        try:
            import base64
            async with httpx.AsyncClient(**self._proxy_kwargs(timeout=15)) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/repos/{owner}/{repo}/readme",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    content = resp.json().get("content", "")
                    return base64.b64decode(content).decode("utf-8")
        except Exception:
            pass
        return None

    async def get_file(self, owner: str, repo: str, path: str) -> str | None:
        """获取仓库文件内容"""
        try:
            import base64
            async with httpx.AsyncClient(**self._proxy_kwargs(timeout=15)) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    content = resp.json().get("content", "")
                    return base64.b64decode(content).decode("utf-8")
        except Exception:
            pass
        return None
