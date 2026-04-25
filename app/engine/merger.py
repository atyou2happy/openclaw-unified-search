"""Result deduplication, RRF fusion, and quality reranking."""

from collections import defaultdict
from difflib import SequenceMatcher
from urllib.parse import urlparse
from app.models import SearchResult

class ResultMerger:
    """结果去重与 RRF 融合 (v4)

    Reciprocal Rank Fusion:
    score(d) = Σ 1/(k + rank_i(d))  for each source ranking i
    k = 60 (standard)
    """

    RRF_K = 60  # RRF 常数

    # 权威来源域名
    AUTHORITY_DOMAINS = {
        "github.com",
        "stackoverflow.com",
        "wikipedia.org",
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
    }

    # source 模块类型权重 (v4 — AI 答案最高)
    SOURCE_WEIGHTS = {
        "tabbit": 1.5,  # 核心模块，最高优先级
        "reddit": 1.1,
        "hackernews": 1.1,
        "youtube": 1.05,
        "github_trending": 1.0,
        "metaso": 1.4,  # AI 深度答案
                "perplexity": 1.35,  # AI 答案
        "perplexity_cite": 1.2,
        "tavily_answer": 1.3,
        "you_ai": 1.2,
        "github": 1.15,
        "academic": 1.15,
        "wiki": 1.1,
        "searxng": 1.0,
        "ddg": 0.95,
        "brave": 0.95,
        "bing": 0.95,
        "bing_news": 0.9,
        "serper": 0.95,
        "serper_kg": 1.1,
        "web": 0.9,
        "komo": 0.9,
    }

    @classmethod
    def deduplicate(cls, results: list[SearchResult]) -> list[SearchResult]:
        """智能去重 — URL + 标题相似度 + 内容指纹"""
        seen_urls = set()
        deduped = []

        for r in results:
            # URL 去重
            url_key = cls._normalize_url(r.url)
            if url_key and url_key in seen_urls:
                # 合并：保留信息更丰富的那个
                cls._merge_into_existing(r, deduped, url_key)
                continue
            if url_key:
                seen_urls.add(url_key)

            # 标题相似度去重（> 0.90 相似度 + URL 同域视为重复）
            title_key = r.title.lower().strip()
            is_dup = False
            for existing in deduped:
                existing_title = existing.title.lower().strip()
                if title_key and existing_title:
                    sim = SequenceMatcher(
                        None, title_key[:80], existing_title[:80]
                    ).ratio()
                    if sim > 0.90:
                        # 同源同标题才去重，不同 URL 的不同视频保留
                        if r.source == existing.source and url_key == cls._normalize_url(existing.url):
                            is_dup = True
                            if r.relevance > existing.relevance:
                                existing.title = r.title
                                existing.snippet = r.snippet or existing.snippet
                                existing.relevance = r.relevance
                                if r.content:
                                    existing.content = r.content
                        elif r.source != existing.source:
                            # 不同源 + 高相似度 = 合并
                            is_dup = True
                            if r.relevance > existing.relevance:
                                existing.title = r.title
                                existing.snippet = r.snippet or existing.snippet
                                existing.relevance = r.relevance
                                if r.content:
                                    existing.content = r.content
                        # 同源不同URL（如YouTube不同视频）：不去重
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
                # 合并 metadata
                if new.metadata:
                    if not existing.metadata:
                        existing.metadata = {}
                    engines = set(existing.metadata.get("engines", []))
                    if new.source:
                        engines.add(new.source)
                    existing.metadata["engines"] = list(engines)
                # 保留更好的 snippet
                if new.snippet and len(new.snippet) > len(existing.snippet or ""):
                    existing.snippet = new.snippet
                # 保留更好的 content
                if new.content and len(new.content) > len(existing.content or ""):
                    existing.content = new.content
                # 保留更高的 relevance
                if new.relevance > existing.relevance:
                    existing.relevance = new.relevance
                break

    @classmethod
    def rrf_fuse(
        cls, results_by_source: dict[str, list[SearchResult]]
    ) -> list[SearchResult]:
        """Reciprocal Rank Fusion — 多源结果融合

        对每个结果按其在各源中的排名计算 RRF 分数，
        然后按 RRF 分数排序。这是业界标准的多源融合方法。
        """
        rrf_scores: dict[str, float] = defaultdict(float)
        url_to_result: dict[str, SearchResult] = {}

        for source, results in results_by_source.items():
            source_weight = cls.SOURCE_WEIGHTS.get(source, 1.0)
            for rank, r in enumerate(results, start=1):
                url_key = cls._normalize_url(r.url) or f"_content_{id(r)}"
                if url_key not in url_to_result:
                    url_to_result[url_key] = r
                else:
                    # 合并信息
                    existing = url_to_result[url_key]
                    if r.snippet and len(r.snippet) > len(existing.snippet or ""):
                        existing.snippet = r.snippet
                    if r.content and len(r.content) > len(existing.content or ""):
                        existing.content = r.content
                    # 合并 engines
                    if not existing.metadata:
                        existing.metadata = {}
                    engines = set(existing.metadata.get("engines", []))
                    if r.source:
                        engines.add(r.source)
                    existing.metadata["engines"] = list(engines)

                # RRF 公式：1/(k + rank) * source_weight
                rrf_scores[url_key] += (1.0 / (cls.RRF_K + rank)) * source_weight

        # 按 RRF 分数排序
        sorted_urls = sorted(
            rrf_scores.keys(), key=lambda u: rrf_scores[u], reverse=True
        )

        results = []
        for url_key in sorted_urls:
            r = url_to_result[url_key]
            r.relevance = min(rrf_scores[url_key] * 100, 1.0)  # 归一化到 0-1
            results.append(r)

        return results

    @classmethod
    def rerank(cls, results: list[SearchResult], query: str = "") -> list[SearchResult]:
        """质量重排 — v0.5.0: 加入标题-查询相似度计算"""
        query_lower = query.lower().strip()
        query_words = set(query_lower.split())

        for r in results:
            score = r.relevance

            # v0.5.0: 标题-查询相似度（核心改进）
            if query_lower and r.title:
                title_lower = r.title.lower()
                # 关键词命中
                hit_count = sum(1 for w in query_words if w in title_lower)
                keyword_score = hit_count / max(len(query_words), 1)
                # SequenceMatcher 相似度
                seq_score = SequenceMatcher(None, query_lower[:60], title_lower[:60]).ratio()
                # 综合：关键词命中权重更高
                relevance_boost = keyword_score * 0.5 + seq_score * 0.3
                score = max(score, relevance_boost)  # 取较大值，不降低

            # v0.5.0: snippet 中查询词命中
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
            # Preserve critical query params (YouTube v=, GitHub params, etc.)
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


# 搜索引擎 v4 — 真并行


