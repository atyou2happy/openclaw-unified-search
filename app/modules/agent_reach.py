"""Agent Reach 模块 — 社交媒体+视频平台搜索桥接

支持: GitHub(gh CLI), Jina Reader(网页), RSS(feedparser)
"""

import json
import logging
import subprocess

from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class AgentReachModule(BaseSearchModule):
    name = "agent_reach"
    description = "Agent Reach 互联网能力（GitHub/RSS/Jina网页）"

    async def health_check(self) -> bool:
        try:
            r = subprocess.run(["gh", "--version"], capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        results = []
        query = request.query

        # GitHub repos
        try:
            r = subprocess.run(
                ["gh", "search", "repos", query,
                 "--json", "name,description,url,stargazersCount",
                 "--limit", str(request.max_results or 5)],
                capture_output=True, text=True, timeout=30,
                env={**subprocess.os.environ, "GH_TOKEN": subprocess.os.environ.get("GH_TOKEN", "")},
            )
            if r.returncode == 0 and r.stdout.strip():
                for item in json.loads(r.stdout):
                    results.append(SearchResult(
                        title=f"[GitHub] {item.get('name', '')}",
                        url=item.get("url", ""),
                        snippet=item.get("description", "")[:200],
                        source="github",
                        score=float(item.get("stargazersCount", 0)),
                    ))
        except Exception:
            pass

        # Jina Reader（URL直接读取）
        if query.startswith("http"):
            try:
                client = await self.get_http_client(timeout=20)
                resp = await client.get(f"https://r.jina.ai/{query}")
                if resp.status_code == 200:
                    results.append(SearchResult(
                        title=f"[网页] {query[:60]}",
                        url=query,
                        snippet=resp.text[:500],
                        source="jina",
                    ))
            except Exception:
                pass

        return results[:request.max_results or 10]
