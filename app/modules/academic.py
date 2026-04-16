"""Academic paper search module — Semantic Scholar + arXiv."""

from datetime import datetime
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class AcademicModule(BaseSearchModule):
    name = "academic"
    description = "学术论文搜索（Semantic Scholar + arXiv）"

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """并行搜索 Semantic Scholar + arXiv"""
        results = []

        # Semantic Scholar
        ss_results = await self._search_semantic_scholar(
            request.query, request.max_results
        )
        results.extend(ss_results)

        # arXiv
        arxiv_results = await self._search_arxiv(
            request.query, request.max_results
        )
        results.extend(arxiv_results)

        # Dedupe by title similarity
        return self._dedupe(results)

    async def _search_semantic_scholar(
        self, query: str, max_results: int
    ) -> list[SearchResult]:
        """搜索 Semantic Scholar"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                resp = await client.get(
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params={
                        "query": query,
                        "limit": min(max_results, 20),
                        "fields": "title,url,abstract,year,authors,citationCount,openAccessPdf",
                    },
                )
                if resp.status_code != 200:
                    return []

                results = []
                for paper in resp.json().get("data", []):
                    pdf_url = ""
                    oa_pdf = paper.get("openAccessPdf")
                    if oa_pdf:
                        pdf_url = oa_pdf.get("url", "")

                    authors = ", ".join(
                        a.get("name", "") for a in (paper.get("authors") or [])[:3]
                    )
                    year = paper.get("year")

                    results.append(SearchResult(
                        title=paper.get("title", ""),
                        url=paper.get("url", ""),
                        snippet=paper.get("abstract", "") or "",
                        source="semantic_scholar",
                        relevance=min((paper.get("citationCount") or 0) / 100, 1.0),
                        timestamp=datetime(year, 1, 1) if year else None,
                        metadata={
                            "authors": authors,
                            "year": year,
                            "citations": paper.get("citationCount", 0),
                            "pdf_url": pdf_url,
                        },
                    ))
                return results
        except Exception:
            return []

    async def _search_arxiv(
        self, query: str, max_results: int
    ) -> list[SearchResult]:
        """搜索 arXiv"""
        import arxiv

        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=min(max_results, 10),
                sort_by=arxiv.SortCriterion.Relevance,
            )

            results = []
            for paper in client.results(search):
                results.append(SearchResult(
                    title=paper.title,
                    url=paper.entry_id,
                    snippet=paper.summary[:500] if paper.summary else "",
                    source="arxiv",
                    relevance=0.7,
                    timestamp=paper.published,
                    metadata={
                        "authors": ", ".join(a.name for a in paper.authors[:3]),
                        "pdf_url": paper.pdf_url,
                        "categories": paper.categories,
                    },
                ))
            return results
        except Exception:
            return []

    def _dedupe(self, results: list[SearchResult]) -> list[SearchResult]:
        """按标题去重"""
        seen_titles = set()
        deduped = []
        for r in results:
            # Normalize title for comparison
            key = r.title.lower().strip()[:80]
            if key not in seen_titles:
                seen_titles.add(key)
                deduped.append(r)
        return deduped
