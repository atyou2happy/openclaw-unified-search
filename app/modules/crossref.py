"""Crossref — 学术论文 DOI 搜索（免费无限）.

Crossref 是全球最大的学术 DOI 注册机构，覆盖 1.4 亿+ 学术记录。
API 免费无限使用，适合论文/学术搜索。

API: https://api.crossref.org/works
"""

import os
import httpx
from app.modules.base import BaseSearchModule
from app.models import SearchRequest, SearchResult
from app.config import Config


class CrossrefModule(BaseSearchModule):
    """Crossref 学术论文搜索 — 免费、无限制"""

    name = "crossref"
    description = "Crossref 学术论文搜索（1.4亿+DOI，免费无限）"

    async def health_check(self) -> bool:
        return True  # 无需 API key

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        proxy = Config.get_proxy()
        kwargs = {"timeout": request.timeout}
        if proxy:
            kwargs["proxy"] = proxy

        try:
            async with httpx.AsyncClient(**kwargs) as client:
                # 用 polite pool（加 mailto 参数提高速率限制）
                mailto = os.environ.get("CONTACT_EMAIL", "")
                params = {
                    "query": request.query,
                    "rows": min(request.max_results, 20),
                    "select": "DOI,title,URL,author,published-print,published-online,container-title,abstract",
                    "sort": "relevance",
                }
                if mailto:
                    params["mailto"] = mailto

                resp = await client.get(
                    "https://api.crossref.org/works",
                    params=params,
                    headers={"User-Agent": "UnifiedSearch/0.6.0 (mailto:contact@example.com)"},
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            items = data.get("message", {}).get("items", [])
            for item in items:
                title_list = item.get("title", [])
                title = title_list[0] if title_list else "Untitled"
                url = item.get("URL", "")
                doi = item.get("DOI", "")

                # 作者
                authors = item.get("author", [])
                author_str = ", ".join(
                    f"{a.get('family', '')} {a.get('given', '')}".strip()
                    for a in authors[:3]
                )
                if len(authors) > 3:
                    author_str += " et al."

                # 年份
                pub = item.get("published-print") or item.get("published-online") or {}
                year = pub.get("date-parts", [[""]])[0][0] if pub.get("date-parts") else ""

                # 期刊
                journal_list = item.get("container-title", [])
                journal = journal_list[0] if journal_list else ""

                # 摘要（部分论文有）
                abstract = item.get("abstract", "")
                # Crossref 返回的 abstract 带有 JATS 标签，清理掉
                import re
                abstract = re.sub(r"<[^>]+>", "", abstract).strip()
                snippet = abstract[:300] if abstract else f"{author_str} ({year}). {journal}"

                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="crossref",
                    metadata={
                        "doi": doi,
                        "authors": author_str,
                        "year": str(year),
                        "journal": journal,
                        "type": "paper",
                    },
                ))

            return results

        except Exception as e:
            return []
