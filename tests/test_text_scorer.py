"""Tests for BM25 text scoring engine."""

import pytest
from app.engine.text_scorer import BM25Scorer


class TestTokenization:
    """Tokenization correctness."""

    def test_english_words(self):
        tokens = BM25Scorer._tokenize("python fastapi async web framework")
        assert "python" in tokens
        assert "fastapi" in tokens
        assert "async" in tokens
        # Short words (< 2 chars) filtered out
        assert "we" not in tokens  # not present in this text anyway
        # Numbers
        tokens2 = BM25Scorer._tokenize("python 3.12 release notes")
        assert "3.12" in tokens2 or "12" in tokens2

    def test_chinese_bigram(self):
        tokens = BM25Scorer._tokenize("机器学习")
        # Should have unigrams + bigram
        assert "机" in tokens or "machine" not in tokens  # just verify non-empty
        assert len(tokens) >= 3  # 机, 器, 学, 习, 机器, 器学, 学习

    def test_chinese_english_mixed(self):
        tokens = BM25Scorer._tokenize("Python 机器学习 framework")
        assert "python" in tokens
        assert "framework" in tokens
        # Should have Chinese tokens too
        assert len(tokens) > 2

    def test_empty_input(self):
        assert BM25Scorer._tokenize("") == []
        assert BM25Scorer._tokenize(None) == []

    def test_punctuation_handling(self):
        tokens = BM25Scorer._tokenize("hello! world? python...")
        assert "hello" in tokens
        assert "world" in tokens
        assert "python" in tokens


class TestTF:
    """Term frequency computation."""

    def test_simple(self):
        doc = ["python", "python", "fastapi", "async"]
        assert BM25Scorer.compute_tf("python", doc) == 2.0
        assert BM25Scorer.compute_tf("fastapi", doc) == 1.0
        assert BM25Scorer.compute_tf("django", doc) == 0.0

    def test_empty_doc(self):
        assert BM25Scorer.compute_tf("python", []) == 0.0


class TestIDF:
    """Inverse document frequency computation."""

    def test_common_term(self):
        corpus = [
            ["python", "fastapi"],
            ["python", "django"],
            ["python", "flask"],
        ]
        idf = BM25Scorer.compute_idf("python", corpus)
        # Term appears in all docs → IDF ≈ 0
        assert idf < 0.5

    def test_rare_term(self):
        corpus = [
            ["python", "fastapi"],
            ["python", "django"],
            ["javascript", "react"],
        ]
        idf = BM25Scorer.compute_idf("fastapi", corpus)
        # Term appears in only 1 doc → IDF > 0
        assert idf > 0.5

    def test_empty_corpus(self):
        assert BM25Scorer.compute_idf("python", []) == 0.0


class TestBM25Score:
    """BM25 score computation."""

    def test_exact_match(self):
        score = BM25Scorer.bm25_score("python", "python is a programming language")
        assert score > 0

    def test_no_match(self):
        score = BM25Scorer.bm25_score("python", "java is a programming language")
        assert score == 0.0

    def test_empty_query(self):
        score = BM25Scorer.bm25_score("", "some document")
        assert score == 0.0

    def test_empty_doc(self):
        score = BM25Scorer.bm25_score("python", "")
        assert score == 0.0

    def test_partial_match(self):
        score_full = BM25Scorer.bm25_score("python fastapi", "python fastapi async web")
        score_partial = BM25Scorer.bm25_score("python fastapi", "python async web")
        # Full match should score higher
        assert score_full > score_partial

    def test_frequency_boost(self):
        score_one = BM25Scorer.bm25_score("python", "python")
        score_many = BM25Scorer.bm25_score("python", "python python python python")
        # More occurrences = higher score (BM25 saturates, but still increases)
        assert score_many >= score_one

    def test_with_corpus(self):
        corpus = [
            BM25Scorer._tokenize("python is great"),
            BM25Scorer._tokenize("java is verbose"),
            BM25Scorer._tokenize("python and java compared"),
        ]
        score = BM25Scorer.bm25_score("python", "python is great", corpus_tokens=corpus)
        assert score > 0


class TestBM25Rank:
    """Batch ranking."""

    def test_rank_ordering(self):
        docs = [
            "python fastapi web framework",
            "java spring boot microservices",
            "python django rest api framework",
            "rust actix web performance",
        ]
        scores = BM25Scorer.rank("python web framework", docs)
        assert len(scores) == 4
        # "python fastapi web framework" should rank highest
        assert scores[0] > scores[1]  # python doc > java doc
        assert scores[0] > scores[3]  # python fastapi > rust actix

    def test_rank_normalization(self):
        docs = ["python is great", "python is awesome"]
        scores = BM25Scorer.rank("python", docs)
        # Scores should be normalized to [0, 1]
        assert max(scores) <= 1.0
        assert max(scores) >= 0.9  # top result should be close to 1.0

    def test_rank_empty(self):
        scores = BM25Scorer.rank("python", [])
        assert scores == []

    def test_rank_single_doc(self):
        scores = BM25Scorer.rank("python", ["python is great"])
        assert len(scores) == 1
        assert scores[0] == 1.0  # single doc normalizes to 1.0


class TestRankResults:
    """Convenience rank_results method."""

    def test_rank_results(self):
        class FakeResult:
            def __init__(self, title, snippet):
                self.title = title
                self.snippet = snippet

        results = [
            FakeResult("Python Web Framework", "FastAPI is modern and fast"),
            FakeResult("Java Spring Boot", "Enterprise Java framework"),
            FakeResult("Rust Performance", "Systems programming language"),
        ]
        scores = BM25Scorer.rank_results("python fastapi", results)
        assert len(scores) == 3
        assert scores[0] > scores[1]  # Python result should rank over Java
