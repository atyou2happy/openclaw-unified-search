"""Result clustering — n-gram overlap single-pass clustering.

Inspired by:
- SearXNG: category facet aggregation
- Google News: topic clustering for search results

Design:
- N-gram overlap + single-pass clustering (online algorithm)
- No external dependencies
- Clusters annotated in result metadata
"""

import re
from collections import Counter
from typing import Any


class ResultCluster:
    """A cluster of related search results."""

    def __init__(self, cluster_id: int, centroid_ngrams: set[str]):
        self.id = cluster_id
        self.centroid_ngrams = centroid_ngrams
        self.member_count = 1
        self.label: str = ""  # extracted keyword label

    def add(self, ngrams: set[str]) -> None:
        """Add a result to this cluster, updating centroid."""
        self.centroid_ngrams |= ngrams
        self.member_count += 1

    def overlap(self, ngrams: set[str]) -> float:
        """Compute n-gram overlap ratio with this cluster's centroid."""
        if not self.centroid_ngrams:
            return 0.0
        intersection = len(self.centroid_ngrams & ngrams)
        union = len(self.centroid_ngrams | ngrams)
        return intersection / union if union > 0 else 0.0


class ResultClustering:
    """N-gram single-pass clustering for search results.

    Clusters up to 15-20 results in < 5ms.

    Usage:
        clusters = ResultClustering.cluster(results, threshold=0.25)
        for r, cluster_id, cluster_label in clusters:
            r.metadata["cluster_id"] = cluster_id
            r.metadata["cluster_label"] = cluster_label
    """

    # Stop words for label extraction (Chinese + English)
    _STOP_WORDS = {
        # English
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "how", "what", "why", "when", "where", "who", "which",
        "and", "or", "not", "but", "if", "then", "else", "this",
        "that", "it", "its", "they", "them", "their", "we", "our",
        "you", "your", "he", "she", "his", "her",
        # Chinese
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
        "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
        "你", "会", "着", "没有", "看", "好", "自己", "这", "那",
        "他", "她", "它", "们", "这个", "那个", "什么", "怎么",
        "因为", "所以", "但是", "如果", "可以", "还是", "已经",
    }

    # CJK ranges
    _CJK_RANGES = [
        (0x4E00, 0x9FFF),
        (0x3400, 0x4DBF),
        (0xF900, 0xFAFF),
    ]

    @classmethod
    def _is_cjk(cls, ch: str) -> bool:
        cp = ord(ch)
        return any(lo <= cp <= hi for lo, hi in cls._CJK_RANGES)

    @classmethod
    def _extract_text(cls, result: Any) -> str:
        """Extract text for clustering from a search result object."""
        parts = []
        if hasattr(result, 'title') and result.title:
            parts.append(result.title)
        if hasattr(result, 'snippet') and result.snippet:
            parts.append(result.snippet)
        return " ".join(parts)

    @classmethod
    def _extract_ngrams(cls, text: str, n: int = 2) -> set[str]:
        """Extract n-grams from text for overlap comparison.

        Uses bigrams (n=2) as default. Filters out stop words.
        """
        if not text:
            return set()

        ngrams: set[str] = set()

        # Split into CJK and non-CJK segments
        # For CJK: character bigrams
        # For English: word bigrams

        words: list[str] = []
        cjk_buf: list[str] = []
        word_buf: list[str] = []

        for ch in text.lower():
            if cls._is_cjk(ch):
                if word_buf:
                    w = "".join(word_buf).strip()
                    if w and w not in cls._STOP_WORDS and len(w) >= 2:
                        words.append(w)
                    word_buf = []
                cjk_buf.append(ch)
            elif ch.isalnum():
                cjk_buf.append(ch) if cls._is_cjk(ch) else word_buf.append(ch)
            else:
                if cjk_buf:
                    # CJK chars as individual tokens
                    s = "".join(cjk_buf)
                    for c in s:
                        if not c.isspace():
                            words.append(c)
                    # Also add bigrams
                    for i in range(len(s) - 1):
                        bg = s[i:i+2]
                        if not bg[0].isspace() and not bg[1].isspace():
                            words.append(bg)
                    cjk_buf = []
                if word_buf:
                    w = "".join(word_buf).strip().lower()
                    if w and w not in cls._STOP_WORDS and len(w) >= 2:
                        words.append(w)
                    word_buf = []

        # Flush remaining
        if cjk_buf:
            s = "".join(cjk_buf)
            for c in s:
                if not c.isspace():
                    words.append(c)
            for i in range(len(s) - 1):
                bg = s[i:i+2]
                if not bg[0].isspace() and not bg[1].isspace():
                    words.append(bg)
        if word_buf:
            w = "".join(word_buf).strip().lower()
            if w and w not in cls._STOP_WORDS and len(w) >= 2:
                words.append(w)

        # Generate word bigrams
        for i in range(len(words) - 1):
            ngrams.add(f"{words[i]} {words[i+1]}")

        # Also add unigrams as fallback
        ngrams.update(words)

        return ngrams

    @classmethod
    def _extract_label(cls, ngrams: set[str], max_words: int = 3) -> str:
        """Extract a human-readable label from cluster n-grams.

        Picks the most discriminative n-grams (longer = more specific).
        """
        # Sort by length (longer n-grams are more specific), then alphabetically
        sorted_ngrams = sorted(ngrams, key=lambda x: (-len(x), x))

        # Pick non-stop-word n-grams
        label_parts: list[str] = []
        for ng in sorted_ngrams:
            parts = ng.split()
            # Filter out stop words
            meaningful = [p for p in parts if p.lower() not in cls._STOP_WORDS]
            if meaningful:
                label_parts.append(" ".join(meaningful))
            if len(label_parts) >= max_words:
                break

        return ", ".join(label_parts[:max_words]) if label_parts else "general"

    @classmethod
    def cluster(
        cls,
        results: list[Any],
        threshold: float = 0.25,
        max_clusters: int = 5,
        min_cluster_size: int = 1,
    ) -> list[tuple[Any, int, str]]:
        """Cluster search results by n-gram overlap.

        Args:
            results: list of search result objects (with .title and .snippet)
            threshold: minimum n-gram overlap ratio to join a cluster (default 0.25)
            max_clusters: maximum number of clusters (default 5)
            min_cluster_size: minimum results per cluster (default 1)

        Returns:
            List of (result, cluster_id, cluster_label) tuples.
            cluster_id=-1 means unclustered (singleton).
        """
        if not results:
            return []

        result_count = len(results)
        # Adaptive max clusters: min(result_count/3, max_clusters)
        effective_max = min(max(result_count // 3, 1), max_clusters)

        clusters: list[ResultCluster] = []
        assignments: list[tuple[Any, int, str]] = []

        for r in results:
            text = cls._extract_text(r)
            ngrams = cls._extract_ngrams(text)

            if not ngrams:
                assignments.append((r, -1, ""))
                continue

            # Find best matching cluster
            best_cluster: ResultCluster | None = None
            best_overlap = 0.0

            for c in clusters:
                overlap = c.overlap(ngrams)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_cluster = c

            if best_cluster is not None and best_overlap >= threshold:
                best_cluster.add(ngrams)
                assignments.append((r, best_cluster.id, ""))
            elif len(clusters) < effective_max:
                # Create new cluster
                new_id = len(clusters)
                new_cluster = ResultCluster(new_id, ngrams)
                clusters.append(new_cluster)
                assignments.append((r, new_id, ""))
            else:
                # No room for new cluster, assign to closest existing
                if best_cluster is not None:
                    best_cluster.add(ngrams)
                    assignments.append((r, best_cluster.id, ""))
                else:
                    assignments.append((r, -1, ""))

        # Extract labels for all clusters
        for c in clusters:
            c.label = cls._extract_label(c.centroid_ngrams)

        # Update assignments with labels
        final: list[tuple[Any, int, str]] = []
        for r, cid, _ in assignments:
            if cid >= 0 and cid < len(clusters):
                label = clusters[cid].label
            else:
                label = ""
            final.append((r, cid, label))

        return final

    @classmethod
    def annotate(
        cls,
        results: list[Any],
        threshold: float = 0.25,
        max_clusters: int = 5,
    ) -> list[Any]:
        """Cluster results and annotate metadata in-place.

        Adds to result.metadata:
        - cluster_id: int (0-based)
        - cluster_label: str
        """
        assignments = cls.cluster(results, threshold, max_clusters)
        for r, cid, label in assignments:
            if not hasattr(r, 'metadata') or r.metadata is None:
                if hasattr(r, '__dict__'):
                    r.__dict__.setdefault('metadata', {})
                else:
                    continue
            r.metadata["cluster_id"] = cid
            r.metadata["cluster_label"] = label
        return results
