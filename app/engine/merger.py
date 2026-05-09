"""Result deduplication, RRF fusion, and quality reranking (v6 — v2.0 quality upgrade).

v6 changes:
- RRF score normalization fix: no more premature min(score*100, 1.0) truncation
- QualityScorer integration: multi-dimensional quality evaluation
- Diversity injection: max_per_source limit + category balancing
- TF-IDF-lite semantic reranking (no external deps)
- Position decay: later positions get lower scores
"""

import math
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from urllib.parse import urlparse

from app.models import SearchResult
from app.engine.quality_scorer import QualityScorer


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
        """Reciprocal Rank Fusion — multi-source result fusion (v7: adaptive k + consensus).

        v6 fix: RRF scores are raw floats, NOT prematurely truncated to [0,1].
        v7 update: adaptive k-value + multi-engine consensus boost.
        """
        rrf_scores: dict[str, float] = defaultdict(float)
        url_to_result: dict[str, SearchResult] = {}

        # v7: compute adaptive k based on total result count
        total_results = sum(len(v) for v in results_by_source.values())
        adaptive_k = cls._adaptive_k(total_results)

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

                rrf_scores[url_key] += (1.0 / (adaptive_k + rank)) * source_weight

        # v7: Consensus boost — results found by multiple engines get bonus
        for url_key, r in url_to_result.items():
            engines = r.metadata.get("engines", []) if r.metadata else []
            if len(engines) > 1:
                # Boost proportional to consensus count (capped at 1.5x)
                consensus_factor = min(1.0 + 0.15 * (len(engines) - 1), 1.5)
                rrf_scores[url_key] *= consensus_factor

        # Sort by raw RRF score, THEN normalize
        sorted_urls = sorted(
            rrf_scores.keys(), key=lambda u: rrf_scores[u], reverse=True
        )

        # Normalize to [0, 1] based on max score
        max_score = rrf_scores[sorted_urls[0]] if sorted_urls else 1.0

        results = []
        for url_key in sorted_urls:
            r = url_to_result[url_key]
            r.relevance = min(rrf_scores[url_key] / max(max_score, 0.001), 1.0)
            results.append(r)

        return results

    @classmethod
    def rerank(
        cls,
        results: list[SearchResult],
        query: str = "",
        intent: dict | None = None,
        max_per_source: int = 3,
    ) -> list[SearchResult]:
        """Quality rerank v7 — BM25 + QualityScorer + SimHash + diversity + clustering + position decay."""
        from app.engine.text_scorer import BM25Scorer

        query_lower = query.lower().strip()
        needs_freshness = intent and "fresh" in intent.get("hints", set())
        intent_type = "general"
        if intent:
            types = intent.get("types", [])
            if isinstance(types, list) and types:
                intent_type = types[0] if isinstance(types[0], str) else "general"

        # Phase 1: BM25 text scoring (v3.0 — replaces SequenceMatcher)
        if query and results:
            # Build corpus for IDF computation from all results
            corpus = [
                BM25Scorer._tokenize(f"{r.title or ''} {r.snippet or ''}")
                for r in results
            ]
            for r in results:
                doc_text = f"{r.title or ''} {r.snippet or ''}"
                bm25_score = BM25Scorer.bm25_score(
                    query, doc_text, corpus_tokens=corpus
                )
                # Blend: 50% BM25 + 50% existing relevance (from RRF)
                r.relevance = r.relevance * 0.5 + bm25_score * 0.5

            # Source weight — SKIP: already applied in rrf_fuse()
            # v7: removed double-counting of SOURCE_WEIGHTS (was applied both in rrf_fuse and rerank)

            # Authority domain boost
            if r.url:
                domain = cls._extract_domain(r.url)
                if domain in cls.AUTHORITY_DOMAINS:
                    r.relevance += 0.1

            # Freshness boost
            if needs_freshness and r.url:
                domain = cls._extract_domain(r.url)
                if domain in cls.FRESHNESS_DOMAINS:
                    r.relevance += 0.15

            # Content richness boost
            if r.content and len(r.content) > 200:
                r.relevance += 0.05

            # Multi-engine consensus boost (v6: increased from 0.05 to 0.08)
            engines = r.metadata.get("engines", []) if r.metadata else []
            if len(engines) > 1:
                r.relevance += 0.08 * min(len(engines), 3)

            r.relevance = min(r.relevance, 1.0)

        # Phase 2: QualityScorer integration (blended 50/50 with existing score)
        if query:
            for r in results:
                quality_score, breakdown = QualityScorer.score(
                    r, query=query, intent_type=intent_type
                )
                # Blend: 60% existing relevance + 40% quality score
                r.relevance = min(r.relevance * 0.6 + quality_score * 0.4, 1.0)

        results.sort(key=lambda r: r.relevance, reverse=True)

        # Phase 2.5: SimHash near-duplicate removal (v3.0)
        if len(results) > 1:
            results = cls._simhash_dedup(results, threshold=3)

        # Phase 3: Diversity injection — limit same-source results
        if max_per_source > 0:
            results = cls._inject_diversity(results, max_per_source)

        # Phase 4: Position decay — apply mild decay to lower positions
        for i, r in enumerate(results):
            decay = 1.0 / (1.0 + 0.02 * i)  # Gentle decay
            r.relevance = round(r.relevance * decay, 4)

        # Phase 5: Result clustering (v3.0)
        if len(results) > 2:
            from app.engine.result_clustering import ResultClustering
            ResultClustering.annotate(results)

        return results

    # Category mapping: module type → result category
    MODULE_CATEGORY_MAP = {
        # Academic
        "academic": "academic", "crossref": "academic", "dblp": "academic",
        "semantic_scholar": "academic",
        # Code
        "github": "code", "stackoverflow": "code", "devto": "code",
        "github_trending": "code",
        # Social / discussion
        "reddit": "social", "hackernews": "social", "x_twitter": "social",
        # Video
        "youtube": "video",
        # News
        "bing_news": "news", "finance_news": "news",
        # Knowledge
        "wikipedia": "knowledge", "wiki": "knowledge",
        # AI answers
        "tabbit": "answer", "metaso": "answer", "perplexity": "answer",
        "deepseek": "answer", "gemini": "answer", "grok": "answer",
        "kimi": "answer", "glm": "answer", "qwen": "answer",
        "vane": "answer",
    }

    @classmethod
    def categorize(cls, result: SearchResult) -> str:
        """Auto-categorize a result based on its source module."""
        source = result.source or ""
        return cls.MODULE_CATEGORY_MAP.get(source, "web")

    @classmethod
    def _inject_diversity(
        cls, results: list[SearchResult], max_per_source: int
    ) -> list[SearchResult]:
        """Ensure source + category diversity in results.

        v7: two-level diversity — per-source limit + per-category minimum.
        1. Limit same-source to max_per_source
        2. Ensure each represented category has at least min_per_category in top slots
        """
        source_counts: Counter = Counter()
        category_counts: Counter = Counter()
        diverse: list[SearchResult] = []
        overflow: list[SearchResult] = []

        # Auto-categorize all results
        for r in results:
            cat = cls.categorize(r)
            if "category" not in (r.metadata or {}):
                if not r.metadata:
                    r.metadata = {}
                r.metadata["category"] = cat

        min_per_category = 1  # Each category gets at least 1 in diverse list
        total_categories = len(set(r.metadata.get("category", "web") for r in results))

        for r in results:
            source = r.source or "unknown"
            cat = r.metadata.get("category", "web")
            source_ok = source_counts[source] < max_per_source

            if source_ok:
                diverse.append(r)
                source_counts[source] += 1
                category_counts[cat] += 1
            else:
                overflow.append(r)

        # Ensure category diversity: if a category has 0 in diverse, pull from overflow
        represented_cats = set(category_counts.keys())
        all_cats = set(r.metadata.get("category", "web") for r in results)
        missing_cats = all_cats - represented_cats

        if missing_cats:
            still_overflow = []
            for r in overflow:
                cat = r.metadata.get("category", "web")
                if cat in missing_cats and category_counts[cat] < min_per_category:
                    diverse.append(r)
                    category_counts[cat] += 1
                    if cat not in missing_cats or category_counts[cat] >= min_per_category:
                        missing_cats.discard(cat)
                else:
                    still_overflow.append(r)
            overflow = still_overflow

        return diverse + overflow

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

    # ── v3.0: Adaptive RRF k-value ────────────────────────────

    @classmethod
    def _adaptive_k(cls, result_count: int) -> float:
        """Compute adaptive RRF k-value based on result set size.

        Small sets → smaller k (emphasizes rank position)
        Large sets → larger k (smoother distribution)

        Values calibrated from IR literature and SearXNG weight/position patterns.
        """
        if result_count <= 10:
            return 30.0   # Small: emphasize rank
        elif result_count <= 30:
            return 60.0   # Standard
        else:
            return 90.0   # Large: smooth

    # ── v3.0: SimHash for near-duplicate detection ─────────────

    _SIMHASH_BITS = 64

    @classmethod
    def _compute_simhash(cls, text: str) -> int:
        """Compute 64-bit SimHash fingerprint for content dedup.

        Inspired by: Google SimHash (Manku et al., 2007)

        Steps:
        1. Tokenize text into features
        2. Hash each feature to 64-bit via Python's built-in hash
        3. Weighted sum: +weight on 1-bits, -weight on 0-bits
        4. Sign: positive → 1, negative → 0
        """
        if not text:
            return 0

        # Simple feature extraction: word bigrams
        words = text.lower().split()
        features: list[str] = []
        for i, w in enumerate(words):
            if len(w) >= 2:
                features.append(w)
            if i < len(words) - 1:
                features.append(f"{words[i]}_{words[i+1]}")

        if not features:
            return 0

        # 64-bit vector of accumulated weights
        v = [0] * cls._SIMHASH_BITS

        for feat in features:
            # Use Python's built-in hash (64-bit on 64-bit Python)
            h = hash(feat)
            # Weight: longer features have slightly more weight
            weight = min(len(feat) / 10.0, 2.0)

            for bit in range(cls._SIMHASH_BITS):
                if h & (1 << bit):
                    v[bit] += weight
                else:
                    v[bit] -= weight

        # Sign: positive → 1, negative → 0
        fingerprint = 0
        for bit in range(cls._SIMHASH_BITS):
            if v[bit] > 0:
                fingerprint |= (1 << bit)

        return fingerprint

    @classmethod
    def _hamming_distance(cls, a: int, b: int) -> int:
        """Compute Hamming distance between two 64-bit integers (popcount of XOR)."""
        xor = a ^ b
        return xor.bit_count()

    @classmethod
    def _simhash_dedup(
        cls, results: list[SearchResult], threshold: int = 3
    ) -> list[SearchResult]:
        """Remove near-duplicate results using SimHash.

        Two results with Hamming distance < threshold are considered duplicates.
        The one with higher relevance is kept.
        """
        if len(results) <= 1:
            return results

        # Compute fingerprints and text for all results
        fingerprints: list[tuple[int, str]] = []
        for r in results:
            text = f"{r.title or ''} {r.snippet or ''}"
            fp = cls._compute_simhash(text)
            fingerprints.append((fp, text))

        deduped: list[SearchResult] = []
        skip: set[int] = set()

        for i, r in enumerate(results):
            if i in skip:
                continue
            fp_i, _ = fingerprints[i]

            # Check against already-added results
            for j in range(len(deduped)):
                fp_j, _ = fingerprints[j]
                if cls._hamming_distance(fp_i, fp_j) < threshold:
                    # Near-duplicate: keep the one with higher relevance
                    if r.relevance > deduped[j].relevance:
                        deduped[j] = r
                    skip.add(i)
                    break

            if i not in skip:
                deduped.append(r)

        return deduped
