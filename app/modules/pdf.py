"""PDF online fetch and parse module."""

import tempfile
from pathlib import Path
import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule


class PDFModule(BaseSearchModule):
    name = "pdf"
    description = "在线 PDF 获取 + 文本提取"

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """如果 query 是 PDF URL，直接解析；否则搜索相关 PDF"""
        query = request.query.strip()

        # Direct URL mode
        if query.startswith("http") and query.lower().endswith(".pdf"):
            return await self.fetch_pdf(query)

        # Search mode: use DDG to find PDFs
        return await self._search_pdfs(query, request.max_results)

    async def fetch_pdf(self, url: str) -> list[SearchResult]:
        """下载并解析 PDF URL"""
        try:
            async with httpx.AsyncClient(
                timeout=30, follow_redirects=True
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []

                content_length = len(resp.content)
                if content_length > Config.PDF_MAX_SIZE_MB * 1024 * 1024:
                    return []

                text = self._extract_text(resp.content)
                if not text:
                    return []

                filename = url.split("/")[-1] or "document.pdf"
                return [SearchResult(
                    title=filename,
                    url=url,
                    snippet=text[:500],
                    content=text[:50000],
                    source=self.name,
                    relevance=0.9,
                    metadata={"pages": text.count("\f") + 1, "size_bytes": content_length},
                )]
        except Exception:
            return []

    async def _search_pdfs(self, query: str, max_results: int) -> list[SearchResult]:
        """通过 DuckDuckGo 搜索 PDF 文件"""
        from ddgs import DDGS

        results = []
        try:
            with DDGS() as ddgs:
                pdf_query = f"{query} filetype:pdf"
                for r in ddgs.text(pdf_query, max_results=max_results):
                    href = r.get("href", "")
                    if href.lower().endswith(".pdf"):
                        results.append(SearchResult(
                            title=r.get("title", ""),
                            url=href,
                            snippet=r.get("body", ""),
                            source=self.name,
                            relevance=0.7,
                        ))
        except Exception:
            pass
        return results

    def _extract_text(self, content: bytes) -> str:
        """从 PDF 字节提取文本"""
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(content))
            pages = []
            for i, page in enumerate(reader.pages):
                if i >= Config.PDF_MAX_PAGES:
                    break
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages)
        except Exception:
            return ""
