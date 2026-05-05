"""Wikipedia Full Search — 维基百科全文搜索（中英文，免费无限）.

与现有 wiki 模块不同：
- wiki 模块：查百度百科 + 维基百科摘要（短文本）
- wikipedia 模块：维基百科全文搜索 + 完整摘要提取

API: https://{en,zh}.wikipedia.org/w/api.php
"""

import logging
import re

from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)


class WikipediaModule(BaseSearchModule):
    """Wikipedia 全文搜索 — 中英文，免费无限"""

    name = "wikipedia"
    description = "Wikipedia 维基百科全文搜索（中英文，免费无限）"

    async def health_check(self) -> bool:
        return True

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        # 根据语言选择 wiki
        has_chinese = any("\u4e00" <= c <= "\u9fff" for c in request.query)
        lang = "zh" if has_chinese or request.language == "zh" else "en"
        base_url = f"https://{lang}.wikipedia.org/w/api.php"

        results = []
        try:
            client = await self.get_http_client(timeout=request.timeout)
            # Step 1: 搜索
            resp = await client.get(base_url, params={
                "action": "query",
                "list": "search",
                "srsearch": request.query,
                "srlimit": min(request.max_results, 10),
                "format": "json",
            }, headers={"User-Agent": "UnifiedSearch/0.6.0 (research bot)"})
            resp.raise_for_status()
            data = resp.json()

            search_results = data.get("query", {}).get("search", [])
            if not search_results:
                return []

            # Step 2: 获取摘要（批量）
            page_ids = [str(r["pageid"]) for r in search_results]
            resp2 = await client.get(base_url, params={
                "action": "query",
                "pageids": "|".join(page_ids),
                "prop": "extracts|info",
                "exintro": 1,
                "explaintext": 1,
                "exsentences": 5,
                "inprop": "url",
                "format": "json",
            }, headers={"User-Agent": "UnifiedSearch/0.6.0 (research bot)"})
            resp2.raise_for_status()
            data2 = resp2.json()

            pages = data2.get("query", {}).get("pages", {})

            for sr in search_results:
                page_id = str(sr["pageid"])
                page = pages.get(page_id, {})
                title = page.get("title", sr.get("title", ""))
                url = page.get("fullurl", f"https://{lang}.wikipedia.org/wiki/{title}")
                extract = page.get("extract", "").strip()

                # 清理 HTML 标签（搜索结果 snippet 带有 <span>）
                snippet = re.sub(r"<[^>]+>", "", sr.get("snippet", ""))
                if extract:
                    snippet = extract[:300]

                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=f"wikipedia-{lang}",
                    metadata={
                        "pageid": sr["pageid"],
                        "lang": lang,
                        "wordcount": sr.get("wordcount", 0),
                        "timestamp": sr.get("timestamp", ""),
                        "type": "encyclopedia",
                    },
                ))

            return results

        except Exception:
            return []
