"""Result deduplication, RRF fusion, and quality reranking (v5)."""

from collections import defaultdict
from difflib import SequenceMatcher
from urllib.parse import urlparse
from app.models import SearchResult


class ResultMerger:
    """结果去重与 RRF 融合 (v5 — 查询相关融合 + freshness boost + 全模块权重)

    Reciprocal Rank Fusion:
    score(d) = Σ 1/(k + rank_i(d)) * source_weight  for each source ranking i
    k = 60 (standard)
    """

    RRF_K = 60

    # 权威来源域名
    AUTHORITY_DOMAINS = {
        "github.com",
        "stackoverflow.com",
        "wikipedia.org",
        "en.wikipedia.org",
        "zh.wikipedia.org",
        "arxiv.org",
        "python.org",
        "docs.python.org",
        "developer.mozilla.org",
        "baike.baidu.com",
        "zhihu.com",
        "csdn.net",
        "npmjs.com",
        "pypi.org",
        "crates.io",
        "metaso.cn",
        "perplexity.ai",
        "dev.to",
        "medium.com",
        "huggingface.co",
        "paperswithcode.com",
        "semanticscholar.org",
        "dl.acm.org",
        "ieeexplore.ieee.org",
    }

    # v5: 全模块 SOURCE_WEIGHTS（38个模块全覆盖）
    SOURCE_WEIGHTS = {
        # AI 搜索引擎
        "tabbit": 1.5,
        "metaso": 1.4,
        "perplexity": 1.35,
        "vane": 1.35,
        "deepseek": 1.3,
        "gemini": 1.25,
        "grok": 1.2,
        "kimi": 1.15,
        "glm": 1.15,
        "qwen": 1.1,
        # 权威知识源
        "wikipedia": 1.3,
        "wiki": 1.1,
        "academic": 1.2,
        "crossref": 1.2,
        "dblp": 1.2,
        # 编程
        "github": 1.2,
        "stackoverflow": 1.25,
        "devto": 1.1,
        "github_trending": 1.0,
        # 社交/趋势
        "reddit": 1.15,
        "x_twitter": 1.1,
        "hackernews": 1.1,
        "youtube": 1.05,
        # 通用搜索
        "searxng": 1.0,
        "ddg": 0.95,
        "brave": 0.95,
        "bing": 0.95,
        "serper": 0.95,
        "tavily": 1.1,
        "exa": 1.15,
        "perplexity_cite": 1.2,
        "tavily_answer": 1.3,
        "you": 1.05,
        "you_ai": 1.2,
        "komo": 0.9,
        "bing_news": 0.9,
        "serper_kg": 1.1,
        # 内容/文档
        "web": 0.9,
        "jina": 1.0,
        "pdf": 0.95,
        "docs": 1.0,
        "phind": 1.0,
        # 本地搜索
        "meilisearch": 1.0,
    }

    # v5: freshness_boost 时效性域名
    FRESHNESS_DOMAINS = {
        "news.ycombinator.com",
        "reddit.com",
        "twitter.com",
        "x.com",
        "weibo.com",
        "zhihu.com",
    }

    @classmethod
    def deduplicate(cls, results: list[SearchResult]) -> list[SearchResult]:
        """智能去重 v5 — 阈值从0.90降到0.85，更激进去重"""
        seen_urls = set()
        deduped = []

        for r in results:
            url_key = cls._normalize_url(r.url)
            if url_key and url_key in seen_urls:
                cls._merge_into_existing(r, deduped, url_key)
                continue
            if url_key:
                seen_urls.add(url_key)

            # v5: 标题相似度阈值从 0.90 → 0.85
            title_key = r.title.lower().strip()
            is_dup = False
            for existing in deduped:
                existing_title = existing.title.lower().strip()
                if title_key and existing_title:
                    sim = SequenceMatcher(
                        None, title_key[:80], existing_title[:80]
                    ).ratio()
                    if sim > 0.85:  # v5: 0.90 → 0.85
                        if r.source == existing.source and url_key == cls._normalize_url(existing.url):
                            is_dup = True
                            if r.relevance > existing.relevance:
                                existing.title = r.title
                                existing.snippet = r.snippet or existing.snippet
                                existing.relevance = r.relevance
                                if r.content:
                                    existing.content = r.content
                        elif r.source != existing.source:
                            is_dup = True
                            if r.relevance > existing.relevance:
                                existing.title = r.title
                                existing.snippet = r.snippet or existing.snippet
                                existing.relevance = r.relevance
                                if r.content:
                                    existing.content = r.content
                        break
            if is_dup:
                continue

            deduped.append(r)

        return deduped

    @classmethod
    def _merge_into_existing(
        cls, new: SearchResult, existing_list: list[SearchResult], url_key: str
    ):
        """将重复 URL 的信息合并到已有结果中"""
        for existing in existing_list:
            if cls._normalize_url(existing.url) == url_key:
                if new.metadata:
                    if not existing.metadata:
                        existing.metadata = {}
                    engines = set(existing.metadata.get("engines", []))
                    if new.source:
                        engines.add(new.source)
                    existing.metadata["engines"] = list(engines)
                if new.snippet and len(new.snippet) > len(existing.snippet or ""):
                    existing.snippet = new.snippet
                if new.content and len(new.content) > len(existing.content or ""):
                    existing.content = new.content
                if new.relevance > existing.relevance:
                    existing.relevance = new.relevance
                break

    @classmethod
    def rrf_fuse(
        cls, results_by_source: dict[str, list[SearchResult]]
    ) -> list[SearchResult]:
        """Reciprocal Rank Fusion — 多源结果融合 (v5: 全模块权重)"""
        rrf_scores: dict[str, float] = defaultdict(float)
        url_to_result: dict[str, SearchResult] = {}

        for source, results in results_by_source.items():
            source_weight = cls.SOURCE_WEIGHTS.get(source, 1.0)
            for rank, r in enumerate(results, start=1):
                url_key = cls._normalize_url(r.url) or f"_content_{id(r)}"
                if url_key not in url_to_result:
                    url_to_result[url_key] = r
                else:
                    existing = url_to_result[url_key]
                    if r.snippet and len(r.snippet) > len(existing.snippet or ""):
                        existing.snippet = r.snippet
                    if r.content and len(r.content) > len(existing.content or ""):
                        existing.content = r.content
                    if not existing.metadata:
                        existing.metadata = {}
                    engines = set(existing.metadata.get("engines", []))
                    if r.source:
                        engines.add(r.source)
                    existing.metadata["engines"] = list(engines)

                rrf_scores[url_key] += (1.0 / (cls.RRF_K + rank)) * source_weight

        sorted_urls = sorted(
            rrf_scores.keys(), key=lambda u: rrf_scores[u], reverse=True
        )

        results = []
        for url_key in sorted_urls:
            r = url_to_result[url_key]
            r.relevance = min(rrf_scores[url_key] * 100, 1.0)
            results.append(r)

        return results

    @classmethod
    def rerank(
        cls,
        results: list[SearchResult],
        query: str = "",
        intent: dict | None = None,
    ) -> list[SearchResult]:
        """质量重排 v5 — 查询相关融合 + freshness boost"""
        query_lower = query.lower().strip()
        query_words = set(query_lower.split())
        needs_freshness = intent and "fresh" in intent.get("hints", set())

        for r in results:
            score = r.relevance

            # 标题-查询相似度
            if query_lower and r.title:
                title_lower = r.title.lower()
                hit_count = sum(1 for w in query_words if w in title_lower)
                keyword_score = hit_count / max(len(query_words), 1)
                seq_score = SequenceMatcher(
                    None, query_lower[:60], title_lower[:60]
                ).ratio()
                relevance_boost = keyword_score * 0.5 + seq_score * 0.3
                score = max(score, relevance_boost)

            # snippet 中查询词命中
            if query_lower and r.snippet:
                snippet_lower = r.snippet.lower()
                snippet_hits = sum(1 for w in query_words if w in snippet_lower)
                score += min(snippet_hits / max(len(query_words), 1), 1.0) * 0.2

            # 模块权重
            source = (
                r.metadata.get("engine_primary", r.source) if r.metadata else r.source
            )
            score *= cls.SOURCE_WEIGHTS.get(source, 1.0)

            # 权威来源加成
            if r.url:
                domain = cls._extract_domain(r.url)
                if domain in cls.AUTHORITY_DOMAINS:
                    score += 0.1

            # v5: freshness boost — 新闻/实时查询优先时效性来源
            if needs_freshness and r.url:
                domain = cls._extract_domain(r.url)
                if domain in cls.FRESHNESS_DOMAINS:
                    score += 0.15

            # 有完整内容加成
            if r.content and len(r.content) > 200:
                score += 0.05

            # 多引擎共识加成
            engines = r.metadata.get("engines", []) if r.metadata else []
            if len(engines) > 1:
                score += 0.05 * min(len(engines), 3)

            r.relevance = min(score, 1.0)

        results.sort(key=lambda r: r.relevance, reverse=True)
        return results

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            key = f"{parsed.netloc.replace('www.', '')}{parsed.path.rstrip('/')}"
            critical_params = ("v", "p", "id", "q", "repo", "issue", "pull")
            if parsed.query:
                from urllib.parse import parse_qs

                qs = parse_qs(parsed.query)
                kept = {k: v[0] for k, v in qs.items() if k in critical_params}
                if kept:
                    from urllib.parse import urlencode

                    key += "?" + urlencode(kept)
            return key.lower()
        except Exception:
            return url.lower()

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            return urlparse(url).netloc.replace("www.", "").lower()
        except Exception:
            return ""
