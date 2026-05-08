"""Result quality scorer — v2.0 multi-dimensional quality evaluation.

Evaluates each search result across 4 dimensions:
1. Relevance (40%) — query-title/snippet similarity
2. Authority (20%) — domain trustworthiness
3. Freshness (20%) — temporal recency
4. Completeness (20%) — result information richness

Inspired by:
- Google's ranking factors: relevance + authority + freshness + UX signals
- SearXNG's score field: weighted multi-signal scoring
- Elasticsearch's function_score: decay functions for freshness
"""

import math
import re
import time
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urlparse

from app.models import SearchResult


class QualityScorer:
    """Multi-dimensional result quality scorer."""

    # Dimension weights (must sum to 1.0)
    DIMENSION_WEIGHTS = {
        "relevance": 0.40,
        "authority": 0.20,
        "freshness": 0.20,
        "completeness": 0.20,
    }

    # Authority tier system (inspired by Google PageRank concept)
    # Tier 1: highest trust (academic, official docs)
    TIER1_DOMAINS = {
        "github.com", "stackoverflow.com", "docs.python.org", "python.org",
        "developer.mozilla.org", "arxiv.org", "wikipedia.org", "en.wikipedia.org",
        "zh.wikipedia.org", "npmjs.com", "pypi.org", "crates.io",
        "paperswithcode.com", "semanticscholar.org", "huggingface.co",
        "dl.acm.org", "ieeexplore.ieee.org", "nature.com", "science.org",
        "springer.com", "sciencedirect.com",
    }
    # Tier 2: good trust (tech blogs, Q&A, knowledge)
    TIER2_DOMAINS = {
        "medium.com", "dev.to", "reddit.com", "news.ycombinator.com",
        "zhihu.com", "csdn.net", "juejin.cn", "segmentfault.com",
        "stackexchange.com", "superuser.com", "askubuntu.com",
        "docs.rs", "doc.rust-lang.org", "go.dev", "rust-lang.org",
        "typescriptlang.org", "vuejs.org", "react.dev", "angular.io",
        "baike.baidu.com", "wikiwand.com",
    }
    # Tier 3: moderate trust (general web)
    TIER3_DOMAINS = {
        "bing.com", "google.com", "duckduckgo.com", "brave.com",
        "youtube.com", "twitter.com", "x.com",
    }

    # Freshness decay parameters
    # Half-life in days: content loses half its freshness value over this period
    _FRESHNESS_HALFLIFE = 30.0  # 30 days

    # Query stop words (for better keyword matching)
    _STOP_WORDS = {
        "en": {"the", "a", "an", "is", "are", "was", "were", "be", "been",
               "being", "have", "has", "had", "do", "does", "did", "will",
               "would", "could", "should", "may", "might", "shall", "can",
               "to", "of", "in", "for", "on", "with", "at", "by", "from",
               "how", "what", "why", "when", "where", "who", "which"},
        "zh": {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
               "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
               "你", "会", "着", "没有", "看", "好", "自己", "这"},
    }

    @classmethod
    def score(
        cls,
        result: SearchResult,
        query: str = "",
        intent_type: str = "general",
    ) -> tuple[float, dict[str, float]]:
        """Score a search result across all dimensions.

        Returns (total_score, breakdown_dict).
        """
        breakdown = {
            "relevance": cls._score_relevance(result, query),
            "authority": cls._score_authority(result),
            "freshness": cls._score_freshness(result, intent_type),
            "completeness": cls._score_completeness(result),
        }

        total = sum(
            breakdown[dim] * weight
            for dim, weight in cls.DIMENSION_WEIGHTS.items()
        )

        return round(total, 4), {k: round(v, 4) for k, v in breakdown.items()}

    @classmethod
    def score_batch(
        cls,
        results: list[SearchResult],
        query: str = "",
        intent_type: str = "general",
    ) -> list[tuple[SearchResult, float, dict]]:
        """Score a batch of results. Returns list of (result, score, breakdown)."""
        scored = []
        for r in results:
            s, b = cls.score(r, query, intent_type)
            scored.append((r, s, b))
        # Sort by quality score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    @classmethod
    def _score_relevance(cls, result: SearchResult, query: str) -> float:
        """Score relevance based on query-title/snippet similarity.

        Uses 3 signals:
        1. Exact keyword hit ratio (40%)
        2. SequenceMatcher similarity (40%)
        3. Existing relevance score from module (20%)
        """
        if not query:
            return result.relevance

        query_lower = query.lower().strip()
        query_words = cls._extract_keywords(query_lower)

        # Signal 1: Keyword hit ratio in title
        title_score = 0.0
        if result.title and query_words:
            title_lower = result.title.lower()
            hits = sum(1 for w in query_words if w in title_lower)
            title_score = hits / max(len(query_words), 1)

        # Signal 1b: Keyword hit ratio in snippet
        snippet_score = 0.0
        if result.snippet and query_words:
            snippet_lower = result.snippet.lower()
            snippet_hits = sum(1 for w in query_words if w in snippet_lower)
            snippet_score = snippet_hits / max(len(query_words), 1) * 0.5

        # Signal 2: SequenceMatcher similarity
        seq_score = 0.0
        if result.title and query:
            seq_score = SequenceMatcher(
                None, query_lower[:80], result.title.lower()[:80]
            ).ratio()

        # Signal 3: Module-provided relevance
        module_relevance = result.relevance

        # Weighted combination
        relevance = (
            title_score * 0.35
            + snippet_score * 0.15
            + seq_score * 0.30
            + module_relevance * 0.20
        )

        return min(relevance, 1.0)

    @classmethod
    def _score_authority(cls, result: SearchResult) -> float:
        """Score authority based on domain trustworthiness.

        Tier 1 = 0.95, Tier 2 = 0.80, Tier 3 = 0.60, Other = 0.50
        """
        if not result.url:
            return 0.30  # No URL = low authority

        domain = cls._extract_domain(result.url)
        if not domain:
            return 0.30

        # Check tiers
        if domain in cls.TIER1_DOMAINS:
            return 0.95
        # Check subdomain match (e.g., docs.github.com -> github.com)
        for tier_domain in cls.TIER1_DOMAINS:
            if domain.endswith("." + tier_domain):
                return 0.90
        if domain in cls.TIER2_DOMAINS:
            return 0.80
        for tier_domain in cls.TIER2_DOMAINS:
            if domain.endswith("." + tier_domain):
                return 0.75
        if domain in cls.TIER3_DOMAINS:
            return 0.60

        # Default: moderate authority for unknown domains
        return 0.50

    @classmethod
    def _score_freshness(cls, result: SearchResult, intent_type: str) -> float:
        """Score freshness based on timestamp and domain timeliness.

        Uses exponential decay: score = exp(-ln(2) * age_days / halflife)
        """
        base_score = 0.50  # Default for unknown freshness

        # If we have a timestamp, use it
        if result.timestamp:
            age_days = (time.time() - result.timestamp.timestamp()) / 86400
            decay = math.exp(-0.693 * age_days / cls._FRESHNESS_HALFLIFE)
            base_score = max(0.1, min(decay, 1.0))

        # Domain-level freshness boost for news/social queries
        if result.url and intent_type == "news":
            domain = cls._extract_domain(result.url)
            fresh_domains = {
                "news.ycombinator.com", "reddit.com", "twitter.com", "x.com",
                "weibo.com", "zhihu.com", "reuters.com", "bloomberg.com",
                "techcrunch.com", "theverge.com", "arstechnica.com",
            }
            if domain in fresh_domains:
                base_score = min(base_score + 0.2, 1.0)

        return base_score

    @classmethod
    def _score_completeness(cls, result: SearchResult) -> float:
        """Score completeness based on available information.

        Has title (20%) + has snippet (30%) + has content (50%)
        """
        score = 0.0

        if result.title and len(result.title.strip()) > 3:
            score += 0.20

        if result.snippet and len(result.snippet.strip()) > 20:
            snippet_score = min(len(result.snippet) / 200.0, 1.0)
            score += 0.30 * snippet_score

        if result.content and len(result.content.strip()) > 50:
            content_score = min(len(result.content) / 1000.0, 1.0)
            score += 0.50 * content_score

        return min(score, 1.0)

    @classmethod
    def _extract_keywords(cls, query: str) -> list[str]:
        """Extract meaningful keywords from query (remove stop words)."""
        words = re.findall(r"\w+", query.lower())
        stop = cls._STOP_WORDS.get("en", set()) | cls._STOP_WORDS.get("zh", set())
        return [w for w in words if w not in stop and len(w) > 1]

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            # Remove port
            if ":" in domain:
                domain = domain.split(":")[0]
            return domain
        except Exception:
            return ""
