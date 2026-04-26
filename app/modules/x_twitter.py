"""X/Twitter search module — multi-fallback approach.

Primary: Nitter instances (public, no API key)
Fallback: SearXNG with twitter/x.com filter
"""

import logging
from typing import Any

import httpx

from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class XTwitterModule(BaseSearchModule):
    name = "x_twitter"
    """X/Twitter 搜索模块

    策略：
    1. 尝试 Nitter 实例搜索（免费，无需 API key）
    2. 备用：SearXNG + x.com 域名过滤
    """

    # Nitter 实例列表（按优先级排序）
    NITTER_INSTANCES = [
        "nitter.net",
        "nitter.poast.org",
        "nitter.privacydev.net",
    ]

    async def is_available(self) -> bool:
        """检查是否有可用的 Nitter 实例或 SearXNG"""
        if self._available is not None:
            return self._available
        try:
            for host in self.NITTER_INSTANCES:
                try:
                    async with httpx.AsyncClient(
                        timeout=5, follow_redirects=True
                    ) as client:
                        resp = await client.get(
                            f"https://{host}/",
                            headers={"User-Agent": "Mozilla/5.0"},
                        )
                        if resp.status_code == 200:
                            self._available = True
                            return True
                except Exception:
                    continue
            # Fallback: SearXNG 可用即可
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(
                        Config.get_searxng_url() + "/healthz"
                    )
                    self._available = resp.status_code == 200
                    return self._available
            except Exception:
                pass
            self._available = False
            return False
        except Exception:
            self._available = False
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """搜索 X/Twitter 内容"""
        results: list[SearchResult] = []

        # 策略 1: Nitter 搜索
        nitter_results = await self._search_nitter(request)
        results.extend(nitter_results)

        # 策略 2: SearXNG 备用（如果 Nitter 没返回足够结果）
        if len(results) < 3:
            searxng_results = await self._search_searxng(request)
            results.extend(searxng_results)

        return results[: request.max_results]

    async def _search_nitter(
        self, request: SearchRequest
    ) -> list[SearchResult]:
        """通过 Nitter 实例搜索"""
        query = request.query
        results: list[SearchResult] = []

        for host in self.NITTER_INSTANCES:
            try:
                async with httpx.AsyncClient(
                    timeout=request.timeout,
                    follow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0"},
                ) as client:
                    # Nitter 搜索页面
                    resp = await client.get(
                        f"https://{host}/search",
                        params={"q": query, "f": "tweets"},
                    )
                    if resp.status_code != 200:
                        continue

                    # 解析 HTML 结果
                    results = self._parse_nitter_html(
                        resp.text, host, query
                    )
                    if results:
                        return results
            except Exception as e:
                logger.debug(f"Nitter {host} failed: {e}")
                continue

        return results

    def _parse_nitter_html(
        self, html: str, host: str, query: str
    ) -> list[SearchResult]:
        """解析 Nitter HTML 结果"""
        import re

        results: list[SearchResult] = []

        # 提取推文内容和链接
        # Nitter HTML 结构: class="tweet-content" 包含推文文本
        tweet_pattern = re.compile(
            r'class="tweet-content[^"]*"[^>]*>(.*?)</div>',
            re.DOTALL,
        )
        link_pattern = re.compile(r'href="/([^/]+)/status/(\d+)"')
        author_pattern = re.compile(r'class="fullname"[^>]*>([^<]+)')

        tweets = tweet_pattern.findall(html)
        links = link_pattern.findall(html)
        authors = author_pattern.findall(html)

        for i, tweet_html in enumerate(tweets):
            # 清理 HTML 标签
            text = re.sub(r"<[^>]+>", "", tweet_html).strip()
            text = re.sub(r"\s+", " ", text)

            if not text or len(text) < 10:
                continue

            author = authors[i].strip() if i < len(authors) else ""
            username = links[i][0] if i < len(links) else ""
            tweet_id = links[i][1] if i < len(links) else ""

            url = f"https://x.com/{username}/status/{tweet_id}" if username and tweet_id else ""

            results.append(
                SearchResult(
                    title=f"@{username}: {text[:60]}" if username else text[:80],
                    url=url,
                    snippet=text[:300],
                    source="x_twitter",
                    relevance=0.8,
                    metadata={
                        "author": author,
                        "username": username,
                        "platform": "x/twitter",
                    },
                )
            )

        return results[:10]

    async def _search_searxng(
        self, request: SearchRequest
    ) -> list[SearchResult]:
        """通过 SearXNG 搜索 X/Twitter 相关内容（备用方案）"""
        results: list[SearchResult] = []

        try:
            searxng_url = Config.get_searxng_url()
            proxy = Config.get_proxy()
            kwargs: dict[str, Any] = {"timeout": request.timeout}
            if proxy:
                kwargs["proxy"] = proxy

            async with httpx.AsyncClient(**kwargs) as client:
                resp = await client.get(
                    f"{searxng_url}/search",
                    params={
                        "q": f"{request.query} x.com OR twitter.com",
                        "format": "json",
                    },
                )
                if resp.status_code != 200:
                    return results

                data = resp.json()
                for r in data.get("results", []):
                    url = r.get("url", "")
                    if "x.com" in url or "twitter.com" in url:
                        results.append(
                            SearchResult(
                                title=r.get("title", ""),
                                url=url,
                                snippet=r.get("content", ""),
                                source="x_twitter",
                                relevance=0.7,
                                metadata={"platform": "x/twitter"},
                            )
                        )
        except Exception as e:
            logger.debug(f"SearXNG X search failed: {e}")

        return results
