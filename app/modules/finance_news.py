"""Finance News Module — 聚合18+源财经新闻"""
import asyncio
import logging
import sys
from pathlib import Path

# 添加 daily-stock-report 的 scripts 目录到 path
DSR_SCRIPTS = Path("/mnt/g/knowledge/project/daily-stock-report/scripts")
if str(DSR_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DSR_SCRIPTS))

from app.modules.base import BaseSearchModule
from app.models import SearchRequest, SearchResult

logger = logging.getLogger(__name__)


class FinanceNewsModule(BaseSearchModule):
    """财经新闻聚合模块 — 18+源实时新闻"""

    name = "finance_news"
    description = "18+源财经新闻聚合（东方财富/财联社/金十/央视/证券时报/Reuters等）"

    def __init__(self):
        super().__init__()
        self._aggregator = None

    def _get_aggregator(self):
        """懒加载聚合器"""
        if self._aggregator is None:
            try:
                from news_sources.aggregator import NewsAggregator
                self._aggregator = NewsAggregator()
            except ImportError:
                logger.error("无法导入 news_sources 模块")
                raise
        return self._aggregator

    async def health_check(self) -> bool:
        """检查模块可用性"""
        try:
            agg = self._get_aggregator()
            return True
        except Exception:
            return False

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """搜索财经新闻"""
        query = request.query
        try:
            agg = self._get_aggregator()
            # 在线程池中运行同步的 fetch_all
            loop = asyncio.get_event_loop()
            items = await loop.run_in_executor(
                None,
                lambda: agg.fetch_all(
                    hours=24,
                    max_per_source=10,
                    max_total=50,
                )
            )

            # 按查询词过滤（简单关键词匹配）
            query_lower = query.lower()
            keywords = query_lower.split()

            results = []
            for item in items:
                title_lower = item.title.lower()
                summary_lower = (item.summary or "").lower()
                text = title_lower + " " + summary_lower

                # 计算相关度
                matched_keywords = sum(1 for kw in keywords if kw in text)
                if matched_keywords == 0 and len(keywords) > 0:
                    # 无关键词匹配但仍然返回（热度排序）
                    score = 0.3
                else:
                    score = 0.5 + 0.1 * matched_keywords

                results.append(SearchResult(
                    title=item.title,
                    url=item.url or "",
                    snippet=f"[{item.source}] {item.time} — {item.summary[:100]}" if item.summary else f"[{item.source}] {item.time}",
                    source=f"finance_news/{item.source}",
                    score=min(score, 1.0),
                    raw={
                        "source": item.source,
                        "time": item.time,
                        "sentiment": item.sentiment,
                        "is_policy": item.is_policy,
                    },
                ))

            return results[:request.max_results if hasattr(request, 'max_results') else 20]

        except Exception as e:
            logger.error(f"Finance news search failed: {e}")
            return []
