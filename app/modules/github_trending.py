"""GitHub Trending module — search GitHub repos via trending + gh API."""

import logging
import httpx
import re
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class GitHubTrendingModule(BaseSearchModule):
    name = "github_trending"
    description = "GitHub Trending 热门仓库搜索（免费）"

    async def health_check(self) -> bool:
        return True  # GitHub always available via proxy

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        query = request.query.strip()
        max_results = request.max_results
        proxy = Config.get_proxy()
        results = []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept": "text/html",
            }

            async with httpx.AsyncClient(timeout=request.timeout, proxy=proxy, follow_redirects=True) as client:
                # Strategy 1: GitHub search (HTML scrape)
                search_results = await self._search_repos(client, headers, query, max_results)
                results.extend(search_results)

                # Strategy 2: Fallback to trending
                if len(results) < max_results:
                    trending = await self._search_trending(client, headers, max_results - len(results))
                    results.extend(trending)

        except Exception as e:
            logger.error(f"GitHub trending search error: {e}")

        return results[:max_results]

    async def _search_repos(self, client, headers, query: str, max_results: int) -> list[SearchResult]:
        """Search GitHub repos via HTML scraping."""
        results = []
        try:
            r = await client.get(
                "https://github.com/search",
                params={"q": query, "type": "repositories", "s": "stars", "o": "desc"},
                headers=headers,
            )
            if r.status_code != 200:
                return results

            # Extract repo paths from embedded payload JSON
            # GitHub embeds search data as JSON in script tags
            repo_pattern = re.compile(r'"repoName":"([^"]+)"')
            repos = repo_pattern.findall(r.text)

            # Deduplicate
            seen = set()
            for repo in repos:
                if repo in seen:
                    continue
                seen.add(repo)
                results.append(SearchResult(
                    title=f"[GitHub] {repo}",
                    url=f"https://github.com/{repo}",
                    snippet=f"GitHub repository: {repo}",
                    source=self.name,
                    relevance=0.6,
                    metadata={"repo": repo}
                ))
                if len(results) >= max_results:
                    break

        except Exception as e:
            logger.warning(f"GitHub search scrape failed: {e}")

        return results

    async def _search_trending(self, client, headers, max_results: int) -> list[SearchResult]:
        """Scrape GitHub trending page."""
        results = []
        try:
            r = await client.get("https://github.com/trending", headers=headers)
            if r.status_code != 200:
                return results

            # h2 > a pattern for trending repos
            repos = re.findall(r'<h2[^>]*>.*?<a[^>]*href="(/[^"]+)"', r.text, re.DOTALL)
            seen = set()
            for repo in repos:
                repo = repo.strip('/')
                if repo in seen or 'login' in repo or 'trending' in repo:
                    continue
                seen.add(repo)
                results.append(SearchResult(
                    title=f"[GitHub Trending] {repo}",
                    url=f"https://github.com/{repo}",
                    snippet=f"Trending repository: {repo}",
                    source=self.name,
                    relevance=0.5,
                    metadata={"repo": repo, "trending": True}
                ))
                if len(results) >= max_results:
                    break
        except Exception as e:
            logger.warning(f"Trending scrape failed: {e}")

        return results
