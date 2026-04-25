"""DBLP — 计算机科学论文搜索（免费无限）.

DBLP 是计算机科学领域最大的开放论文数据库，覆盖 600万+ 论文。
API 完全免费，无需 key。

API: https://dblp.org/search/publ/api
"""

import httpx
from app.modules.base import BaseSearchModule
from app.models import SearchRequest, SearchResult
from app.config import Config


class DBLPModule(BaseSearchModule):
    """DBLP 计算机科学论文搜索 — 免费、无限制"""

    name = "dblp"
    description = "DBLP 计算机科学论文搜索（600万+论文，免费无限）"

    async def health_check(self) -> bool:
        return True

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        proxy = Config.get_proxy()
        kwargs = {"timeout": request.timeout}
        if proxy:
            kwargs["proxy"] = proxy

        try:
            async with httpx.AsyncClient(**kwargs) as client:
                resp = await client.get(
                    "https://dblp.org/search/publ/api",
                    params={
                        "q": request.query,
                        "format": "json",
                        "h": min(request.max_results, 20),
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            hits = data.get("result", {}).get("hits", {}).get("hit", [])
            if isinstance(hits, dict):
                hits = [hits]

            for hit in hits:
                info = hit.get("info", {})
                title = info.get("title", "Untitled")
                url = info.get("url", info.get("ee", ""))
                doi = info.get("doi", "")
                year = info.get("year", "")
                venue = info.get("venue", "")
                pub_type = info.get("type", "")

                # 作者
                authors_info = info.get("authors", {}).get("author", [])
                if isinstance(authors_info, dict):
                    authors_info = [authors_info]
                author_str = ", ".join(
                    a.get("text", "") for a in authors_info[:4]
                )

                snippet = f"{author_str} ({year}). {venue}"

                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="dblp",
                    metadata={
                        "doi": doi,
                        "authors": author_str,
                        "year": str(year),
                        "venue": venue,
                        "type": pub_type or "paper",
                    },
                ))

            return results

        except Exception:
            return []
