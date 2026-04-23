"""Reddit search module — via SearXNG (curl subprocess to bypass httpx 403)."""

import logging
import json
import asyncio
import subprocess
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class RedditModule(BaseSearchModule):
    name = "reddit"
    description = "Reddit 社区搜索（via SearXNG）"

    async def health_check(self) -> bool:
        try:
            r = subprocess.run(
                ["curl", "-s", "--noproxy", "localhost", "--max-time", "3",
                 "http://localhost:8080/healthz"],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        query = request.query.strip()
        max_results = request.max_results
        results = []

        try:
            # Use curl subprocess — httpx gets 403 from SearXNG upstream
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "--noproxy", "localhost", "--max-time", str(request.timeout),
                "http://localhost:8080/search",
                "--data-urlencode", f"q={query} site:reddit.com",
                "--data-urlencode", "format=json",
                "--data-urlencode", "categories=general",
                "-G",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=request.timeout + 5)
            data = json.loads(stdout)

            for item in data.get("results", []):
                url = item.get("url", "")
                if "reddit.com" not in url:
                    continue

                subreddit = ""
                if "/r/" in url:
                    parts = url.split("/r/")
                    if len(parts) > 1:
                        subreddit = parts[1].split("/")[0]

                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=url,
                    snippet=item.get("content", "")[:300],
                    source=self.name,
                    relevance=0.7,
                    metadata={
                        "engine": item.get("engine", ""),
                        "subreddit": subreddit,
                    }
                ))
                if len(results) >= max_results:
                    break

        except Exception as e:
            logger.error(f"Reddit search error: {e}")

        return results[:max_results]
