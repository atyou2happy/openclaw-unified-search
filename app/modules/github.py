"""GitHub repository and code search module."""

import os
from datetime import datetime
import httpx
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class GitHubModule(BaseSearchModule):
    name = "github"
    description = "GitHub 仓库/代码搜索 + 文件内容获取"
    BASE_URL = "https://api.github.com"

    def _headers(self) -> dict:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "unified-search",
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"
        return headers

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/rate_limit",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """搜索 GitHub 仓库"""
        try:
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/search/repositories",
                    params={"q": request.query, "per_page": request.max_results},
                    headers=self._headers(),
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = []
                for item in data.get("items", []):
                    results.append(SearchResult(
                        title=item.get("full_name", ""),
                        url=item.get("html_url", ""),
                        snippet=item.get("description", "") or "",
                        source=self.name,
                        relevance=min(item.get("stargazers_count", 0) / 1000, 1.0),
                        timestamp=datetime.strptime(
                            item.get("updated_at", ""), "%Y-%m-%dT%H:%M:%SZ"
                        ) if item.get("updated_at") else None,
                        metadata={
                            "stars": item.get("stargazers_count", 0),
                            "language": item.get("language", ""),
                            "license": (item.get("license") or {}).get("spdx_id", ""),
                            "forks": item.get("forks_count", 0),
                            "topics": item.get("topics", []),
                        },
                    ))
                return results
        except Exception:
            return []

    async def get_readme(self, owner: str, repo: str) -> str | None:
        """获取仓库 README 内容"""
        try:
            import base64
            async with httpx.AsyncClient(timeout=15) as client:
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
            async with httpx.AsyncClient(timeout=15) as client:
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

    async def search_code(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """搜索代码"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/search/code",
                    params={"q": query, "per_page": max_results},
                    headers=self._headers(),
                )
                if resp.status_code != 200:
                    return []

                results = []
                for item in resp.json().get("items", []):
                    repo = item.get("repository", {})
                    results.append(SearchResult(
                        title=f"{repo.get('full_name', '')}: {item.get('path', '')}",
                        url=item.get("html_url", ""),
                        snippet=item.get("name", ""),
                        source="github_code",
                        relevance=0.6,
                    ))
                return results
        except Exception:
            return []
