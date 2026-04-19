"""百科搜索模块 — 百度百科 + 维基百科."""

import re
import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class WikiModule(BaseSearchModule):
    name = "wiki"
    description = "百科搜索（百度百科 + 维基百科）"

    async def health_check(self) -> bool:
        # 百度百科直连即可
        try:
            proxy = Config.get_proxy()
            kwargs = {"timeout": 5}
            if proxy:
                kwargs["proxy"] = proxy
            kwargs["verify"] = False  # WestWorld self-signed cert
            async with httpx.AsyncClient(**kwargs) as client:
                r = await client.get(
                    "https://baike.baidu.com/item/Python",
                    headers={"User-Agent": "Mozilla/5.0"},
                    follow_redirects=True,
                )
                return r.status_code == 200
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        results = []

        # 1. 百度百科搜索（直连，无需代理）
        baidu_results = await self._search_baidu(request)
        results.extend(baidu_results)

        # 2. 维基百科搜索（需代理，可能 403）
        wiki_results = await self._search_wikipedia(request)
        results.extend(wiki_results)

        # 按相关性排序
        results.sort(key=lambda r: r.relevance, reverse=True)
        return results[:request.max_results]

    async def _search_baidu(self, request: SearchRequest) -> list[SearchResult]:
        """百度百科搜索"""
        proxy = Config.get_proxy()
        kwargs = {"timeout": 15, "follow_redirects": True}
        if proxy:
            kwargs["proxy"] = proxy
            kwargs["verify"] = False  # WestWorld self-signed cert

        results = []
        try:
            async with httpx.AsyncClient(**kwargs) as client:
                # 搜索
                r = await client.get(
                    "https://baike.baidu.com/search",
                    params={"word": request.query, "pn": 0, "rn": request.max_results},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                )
                if r.status_code == 200:
                    # 提取搜索结果
                    links = re.findall(
                        r'href="/item/([^"?#]+)[^"]*"[^>]*>([^<]+)</a>',
                        r.text
                    )
                    seen = set()
                    for slug, title in links[:request.max_results]:
                        if slug not in seen:
                            seen.add(slug)
                            # 获取词条摘要
                            summary = await self._get_baidu_summary(client, slug)
                            results.append(SearchResult(
                                title=title.strip(),
                                url=f"https://baike.baidu.com/item/{slug}",
                                snippet=summary[:500],
                                content=summary,
                                source="baidu_baike",
                                relevance=0.8,
                            ))

                # 如果搜索没结果，直接尝试词条
                if not results:
                    summary = await self._get_baidu_summary(client, request.query)
                    if summary:
                        results.append(SearchResult(
                            title=f"百度百科: {request.query}",
                            url=f"https://baike.baidu.com/item/{request.query}",
                            snippet=summary[:500],
                            content=summary,
                            source="baidu_baike",
                            relevance=0.75,
                        ))
        except Exception:
            pass
        return results

    async def _get_baidu_summary(self, client: httpx.AsyncClient, slug: str) -> str:
        """获取百度百科词条摘要"""
        try:
            r = await client.get(
                f"https://baike.baidu.com/item/{slug}",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            if r.status_code != 200:
                return ""

            text = r.text
            # 提取 meta description
            m = re.search(r'<meta name="description" content="(.*?)"', text)
            if m:
                return m.group(1)

            # 备选：提取 lemmaSummary
            m = re.search(r'class="lemma-summary"[^>]*>(.*?)</div>', text, re.DOTALL)
            if m:
                clean = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                return clean[:2000]
            return ""
        except Exception:
            return ""

    async def _search_wikipedia(self, request: SearchRequest) -> list[SearchResult]:
        """维基百科搜索（需代理，可能被墙）"""
        proxy = Config.get_proxy()
        kwargs = {"timeout": 10}
        if proxy:
            kwargs["proxy"] = proxy
            kwargs["verify"] = False  # WestWorld self-signed cert

        lang = "zh" if request.language in ("zh", "auto") else "en"
        results = []

        try:
            async with httpx.AsyncClient(**kwargs) as client:
                # 搜索
                r = await client.get(
                    f"https://{lang}.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": request.query,
                        "format": "json",
                        "srlimit": min(request.max_results, 5),
                    },
                    headers={"User-Agent": "UnifiedSearch/1.0"},
                )
                if r.status_code != 200:
                    return results

                data = r.json()
                for item in data.get("query", {}).get("search", []):
                    title = item["title"]
                    snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))

                    # 获取完整摘要
                    summary = await self._get_wiki_summary(client, title, lang)

                    results.append(SearchResult(
                        title=title,
                        url=f"https://{lang}.wikipedia.org/wiki/{title}",
                        snippet=snippet[:500],
                        content=summary or snippet,
                        source="wikipedia",
                        relevance=0.85,
                    ))
        except Exception:
            pass
        return results

    async def _get_wiki_summary(
        self, client: httpx.AsyncClient, title: str, lang: str
    ) -> str:
        """获取维基百科词条摘要"""
        try:
            r = await client.get(
                f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}",
                headers={"User-Agent": "UnifiedSearch/1.0"},
            )
            if r.status_code == 200:
                data = r.json()
                return data.get("extract", "")
        except Exception:
            pass
        return ""
