"""BM25-lite text matching engine for search result ranking.

Inspired by:
- Meilisearch: BM25 as core ranking algorithm
- Elasticsearch: Okapi BM25 implementation
- rank_bm25 (DorianBrown): lightweight Python BM25 implementation

Design principles:
- Zero external dependencies (pure Python stdlib)
- Chinese + English tokenization
- O(n) per-document scoring
"""

import math
import re
from collections import Counter


class BM25Scorer:
    """Okapi BM25 scoring for search result ranking.

    BM25(q, d) = Σ IDF(qi) × (TF(qi,d) × (k1+1)) / (TF(qi,d) + k1×(1-b+b×|d|/avgdl))

    Parameters follow standard IR conventions:
    - k1=1.2: term frequency saturation
    - b=0.75: length normalization
    """

    K1 = 1.2
    B = 0.75
    DEFAULT_AVGDL = 100.0  # fallback when result set is empty

    # ── Tokenization ──────────────────────────────────────────

    # CJK Unicode ranges (simplified)
    _CJK_RANGES = [
        (0x4E00, 0x9FFF),   # CJK Unified Ideographs
        (0x3400, 0x4DBF),   # CJK Extension A
        (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    ]

    @classmethod
    def _is_cjk(cls, ch: str) -> bool:
        cp = ord(ch)
        return any(lo <= cp <= hi for lo, hi in cls._CJK_RANGES)

    @classmethod
    def _tokenize(cls, text: str) -> list[str]:
        """Tokenize text into terms (Chinese bigram + unigram, English word).

        Strategy:
        - Chinese characters: generate bigrams + unigrams
        - English/ASCII: split on whitespace + punctuation, lowercase
        - Mixed text: both strategies applied to respective segments
        """
        if not text:
            return []

        tokens: list[str] = []

        # Phase 1: extract CJK segments for bigram/unigram tokenization
        cjk_chars: list[str] = []
        non_cjk_buffer: list[str] = []

        def _flush_cjk():
            nonlocal cjk_chars
            if cjk_chars:
                s = "".join(cjk_chars)
                # Unigrams
                tokens.extend(c for c in s if not c.isspace())
                # Bigrams
                for i in range(len(s) - 1):
                    bg = s[i:i+2]
                    if not bg[0].isspace() and not bg[1].isspace():
                        tokens.append(bg)
                cjk_chars = []

        def _flush_non_cjk():
            nonlocal non_cjk_buffer
            if non_cjk_buffer:
                word = "".join(non_cjk_buffer).strip().lower()
                if word and len(word) >= 2:
                    tokens.append(word)
                non_cjk_buffer = []

        for ch in text:
            if cls._is_cjk(ch):
                _flush_non_cjk()
                cjk_chars.append(ch)
            elif ch.isalnum():
                cjk_chars.append(ch) if cls._is_cjk(ch) else non_cjk_buffer.append(ch)
            else:
                _flush_cjk()
                non_cjk_buffer.append(" ")

        _flush_cjk()
        _flush_non_cjk()

        # Phase 2: split non-CJK tokens on whitespace
        final_tokens: list[str] = []
        for t in tokens:
            if any(cls._is_cjk(c) for c in t):
                final_tokens.append(t.lower())
            else:
                # English word: split on whitespace, keep words >= 2 chars
                for w in t.split():
                    w = w.strip().lower()
                    if w and len(w) >= 2:
                        final_tokens.append(w)

        return final_tokens

    # ── BM25 Core ─────────────────────────────────────────────

    @classmethod
    def compute_tf(cls, term: str, doc_tokens: list[str]) -> float:
        """Raw term frequency in document."""
        if not doc_tokens:
            return 0.0
        return sum(1 for t in doc_tokens if t == term)

    @classmethod
    def compute_idf(
        cls, term: str, doc_token_lists: list[list[str]]
    ) -> float:
        """Inverse document frequency: log((N - n + 0.5) / (n + 0.5) + 1).

        Smooth IDF variant (Robertson-Sparck Jones) for better handling of
        terms that appear in all or no documents.
        """
        N = len(doc_token_lists)
        if N == 0:
            return 0.0
        n = sum(1 for tokens in doc_token_lists if term in tokens)
        return math.log((N - n + 0.5) / (n + 0.5) + 1.0)

    @classmethod
    def bm25_score(
        cls,
        query: str,
        doc_text: str,
        corpus_tokens: list[list[str]] | None = None,
        avgdl: float | None = None,
        k1: float | None = None,
        b: float | None = None,
    ) -> float:
        """Compute BM25 score for a single document against a query.

        Args:
            query: search query string
            doc_text: document text (title + snippet)
            corpus_tokens: pre-tokenized corpus for IDF computation (optional)
            avgdl: average document length (computed from corpus if None)
            k1: term frequency saturation (default 1.2)
            b: length normalization (default 0.75)
        """
        k1_val = k1 if k1 is not None else cls.K1
        b_val = b if b is not None else cls.B

        query_tokens = cls._tokenize(query)
        doc_tokens = cls._tokenize(doc_text)

        if not query_tokens or not doc_tokens:
            return 0.0

        doc_len = len(doc_tokens)

        # Compute IDF if corpus provided, otherwise use default IDF=1.0
        if corpus_tokens is not None:
            idf_map: dict[str, float] = {}
        else:
            idf_map = {}

        # Compute avgdl
        if avgdl is None and corpus_tokens is not None and corpus_tokens:
            avgdl_val = sum(len(t) for t in corpus_tokens) / len(corpus_tokens)
        elif avgdl is None:
            avgdl_val = cls.DEFAULT_AVGDL
        else:
            avgdl_val = avgdl

        score = 0.0
        for qt in query_tokens:
            tf = cls.compute_tf(qt, doc_tokens)
            if tf == 0:
                continue

            # Get IDF (compute on-demand or use default)
            if corpus_tokens is not None and qt not in idf_map:
                idf_map[qt] = cls.compute_idf(qt, corpus_tokens)
            idf = idf_map.get(qt, 1.0)

            numerator = tf * (k1_val + 1.0)
            denominator = tf + k1_val * (1.0 - b_val + b_val * doc_len / max(avgdl_val, 1.0))
            score += idf * numerator / denominator

        return score

    @classmethod
    def rank(
        cls,
        query: str,
        documents: list[str],
        corpus_tokens: list[list[str]] | None = None,
    ) -> list[float]:
        """Compute BM25 scores for a batch of documents.

        Returns list of scores in same order as documents.
        """
        # Build corpus tokens if not provided
        if corpus_tokens is None:
            corpus_tokens = [cls._tokenize(d) for d in documents]

        avgdl = sum(len(t) for t in corpus_tokens) / max(len(corpus_tokens), 1)

        scores: list[float] = []
        for doc_text, doc_tokens in zip(documents, corpus_tokens):
            s = cls.bm25_score(
                query, doc_text, corpus_tokens=corpus_tokens, avgdl=avgdl
            )
            scores.append(s)

        # Normalize to [0, 1] for consistency with relevance scores
        max_score = max(scores) if scores else 1.0
        if max_score > 0:
            scores = [s / max_score for s in scores]

        return scores

    @classmethod
    def rank_results(
        cls,
        query: str,
        results: list,
        text_extractor=None,
    ) -> list[float]:
        """Convenience: rank a list of SearchResult objects.

        Args:
            query: search query
            results: list of SearchResult objects
            text_extractor: callable to extract text from result
                           (default: lambda r: f"{r.title} {r.snippet}")
        """
        if text_extractor is None:
            def _extract(r):
                parts = []
                if hasattr(r, 'title') and r.title:
                    parts.append(r.title)
                if hasattr(r, 'snippet') and r.snippet:
                    parts.append(r.snippet)
                return " ".join(parts)
            text_extractor = _extract

        documents = [text_extractor(r) for r in results]
        return cls.rank(query, documents)


# Singleton convenience
bm25 = BM25Scorer()
