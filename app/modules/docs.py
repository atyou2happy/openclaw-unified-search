"""Documentation site scraping module."""

import re
from urllib.parse import urljoin, urlparse
import httpx
import trafilatura
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class DocsModule(BaseSearchModule):
    name = "docs"
    description = "文档站点抓取 + 正文提取"

    # Common doc frameworks detected by URL patterns
    DOC_PATTERNS = [
        r"readthedocs\.io",
        r"docs\.py",
        r"documentation",
        r"/docs/",
        r"/guide/",
        r"/reference/",
        r"docusaurus",
        r"mkdocs",
        r"sphinx",
        r"gitbook",
        r"notion\.site",
    ]

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """如果 query 是 URL，直接抓取；否则搜索相关文档"""
        query = request.query.strip()

        if query.startswith("http"):
            return await self._fetch_doc(query, request.depth)

        return await self._search_docs(query, request.max_results)

    async def _fetch_doc(self, url: str, depth: str = "normal") -> list[SearchResult]:
        """抓取文档页面内容"""
        try:
            async with httpx.AsyncClient(
                timeout=20, follow_redirects=True
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []

                html = resp.text
                content = trafilatura.extract(html)
                if not content:
                    return []

                title = self._extract_title(html, url)
                results = [SearchResult(
                    title=title,
                    url=url,
                    snippet=content[:500],
                    content=content[:50000],
                    source=self.name,
                    relevance=0.85,
                )]

                # Deep mode: try to find sub-pages
                if depth == "deep":
                    sub_links = self._extract_sub_links(html, url, max_links=5)
                    for link in sub_links:
                        try:
                            sub_resp = await client.get(link)
                            if sub_resp.status_code == 200:
                                sub_content = trafilatura.extract(sub_resp.text)
                                if sub_content:
                                    results.append(SearchResult(
                                        title=self._extract_title(sub_resp.text, link),
                                        url=link,
                                        snippet=sub_content[:500],
                                        content=sub_content[:30000],
                                        source=self.name,
                                        relevance=0.75,
                                    ))
                        except Exception:
                            continue

                return results
        except Exception:
            return []

    async def _search_docs(self, query: str, max_results: int) -> list[SearchResult]:
        """通过 DuckDuckGo 搜索文档站点"""
        from ddgs import DDGS

        results = []
        try:
            doc_query = f"{query} (documentation OR docs OR tutorial OR guide)"
            with DDGS() as ddgs:
                for r in ddgs.text(doc_query, max_results=max_results):
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        url=r.get("href", ""),
                        snippet=r.get("body", ""),
                        source=self.name,
                        relevance=0.65,
                    ))
        except Exception:
            pass
        return results

    def _extract_title(self, html: str, fallback_url: str) -> str:
        """从 HTML 提取标题"""
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            # Clean up common suffixes
            for suffix in [" — Documentation", " - Docs", " | Documentation", " – "]:
                if suffix in title:
                    title = title.split(suffix)[0].strip()
            return title or fallback_url
        return fallback_url

    def _extract_sub_links(self, html: str, base_url: str, max_links: int = 5) -> list[str]:
        """从文档页面提取相关子链接"""
        links = []
        base_domain = urlparse(base_url).netloc
        for match in re.finditer(r'href=["\'](/[^"\']*)["\']', html):
            path = match.group(1)
            if any(ext in path.lower() for ext in [".css", ".js", ".png", ".jpg", ".svg", ".ico"]):
                continue
            full_url = urljoin(base_url, path)
            if urlparse(full_url).netloc == base_domain and full_url != base_url:
                links.append(full_url)
            if len(links) >= max_links:
                break
        return list(dict.fromkeys(links))[:max_links]  # dedupe preserving order
