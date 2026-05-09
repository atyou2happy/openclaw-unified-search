"""Tests for result clustering engine."""

import pytest
from app.engine.result_clustering import ResultClustering, ResultCluster


class FakeResult:
    def __init__(self, title="", snippet="", metadata=None):
        self.title = title
        self.snippet = snippet
        self.metadata = metadata if metadata is not None else {}

    def __repr__(self):
        return f"FakeResult({self.title[:30]})"


class TestNgramExtraction:
    """N-gram extraction from text."""

    def test_english_bigrams(self):
        ngrams = ResultClustering._extract_ngrams("python web framework")
        assert len(ngrams) > 0
        # Should have bigrams like "python web", "web framework"
        assert "python web" in ngrams or "web framework" in ngrams

    def test_chinese_bigrams(self):
        ngrams = ResultClustering._extract_ngrams("机器学习深度学习")
        assert len(ngrams) > 0

    def test_stop_word_filtering(self):
        ngrams = ResultClustering._extract_ngrams("the is a and the")
        # All stop words should be filtered
        assert len(ngrams) <= 1  # might have "the the" or similar

    def test_empty_text(self):
        assert ResultClustering._extract_ngrams("") == set()
        assert ResultClustering._extract_ngrams(None) == set()


class TestResultCluster:
    """ResultCluster operations."""

    def test_overlap_identical(self):
        c = ResultCluster(0, {"a b", "b c", "c d"})
        overlap = c.overlap({"a b", "b c", "c d"})
        assert overlap == 1.0

    def test_overlap_none(self):
        c = ResultCluster(0, {"a b", "b c"})
        overlap = c.overlap({"x y", "y z"})
        assert overlap == 0.0

    def test_overlap_partial(self):
        c = ResultCluster(0, {"a b", "b c", "c d"})
        overlap = c.overlap({"a b", "x y"})
        assert 0.0 < overlap < 1.0

    def test_add_updates_centroid(self):
        c = ResultCluster(0, {"a b"})
        assert c.member_count == 1
        c.add({"c d"})
        assert c.member_count == 2
        assert "c d" in c.centroid_ngrams

    def test_empty_centroid_overlap(self):
        c = ResultCluster(0, set())
        assert c.overlap({"a b"}) == 0.0


class TestClustering:
    """Clustering of search results."""

    def test_empty_results(self):
        results = ResultClustering.cluster([])
        assert results == []

    def test_single_result(self):
        r = FakeResult(title="Python Programming", snippet="Learn Python")
        results = ResultClustering.cluster([r])
        assert len(results) == 1
        assert results[0][1] == 0  # cluster_id

    def test_similar_results_clustered(self):
        # Results with significant overlap should cluster
        results = [
            FakeResult("Python FastAPI async web framework", "FastAPI Python tutorial"),
            FakeResult("Python FastAPI tutorial guide", "FastAPI Python beginner guide"),
            FakeResult("Java Spring Boot enterprise", "Java Spring development"),
        ]
        clusters = ResultClustering.cluster(results, threshold=0.25)
        cids = [c[1] for c in clusters]
        # First two share multiple terms (FastAPI, Python, tutorial/guide), should cluster
        assert cids[0] == cids[1]
        # Java result should be in different cluster
        assert cids[0] != cids[2]

    def test_diverse_results_multiple_clusters(self):
        # Results with clear topic clusters
        results = [
            FakeResult("Python python python python", "python python python"),
            FakeResult("Python python programming", "python tutorial"),
            FakeResult("Rust rust rust rust", "rust systems rust"),
            FakeResult("Rust rust programming", "rust tutorial"),
            FakeResult("JavaScript js js react", "react useState js"),
            FakeResult("JavaScript js js async", "react Promise js"),
        ]
        clusters = ResultClustering.cluster(results, threshold=0.25, max_clusters=5)
        cids = [c[1] for c in clusters]
        assert cids[0] == cids[1]  # Python pair
        assert cids[2] == cids[3]  # Rust pair
        assert cids[4] == cids[5]  # JavaScript pair

    def test_cluster_label_generation(self):
        results = [
            FakeResult("Python FastAPI async web framework", "Build modern APIs"),
            FakeResult("Python FastAPI tutorial for beginners", "Learn FastAPI"),
        ]
        clusters = ResultClustering.cluster(results, threshold=0.2)
        assert clusters[0][2] != ""  # should have a label

    def test_max_clusters_limit(self):
        results = [
            FakeResult(f"Topic {i}", f"Description {i}") for i in range(20)
        ]
        clusters = ResultClustering.cluster(results, threshold=0.01, max_clusters=3)
        unique_cids = set(c[1] for c in clusters if c[1] >= 0)
        assert len(unique_cids) <= 3

    def test_low_threshold_merges_all(self):
        results = [
            FakeResult("Python", "Programming"),
            FakeResult("Java", "Programming"),
            FakeResult("Rust", "Programming"),
        ]
        clusters = ResultClustering.cluster(results, threshold=0.01)
        cids = [c[1] for c in clusters]
        # Very low threshold should put everything in one cluster
        unique_cids = set(cids)
        assert len(unique_cids) == 1


class TestAnnotate:
    """Annotate method for in-place metadata injection."""

    def test_annotate_adds_metadata(self):
        results = [
            FakeResult("Python async", "asyncio guide"),
            FakeResult("Python sync", "threading guide"),
            FakeResult("Java spring", "spring boot"),
        ]
        ResultClustering.annotate(results, threshold=0.2)
        for r in results:
            assert "cluster_id" in r.metadata
            assert "cluster_label" in r.metadata

    def test_annotate_with_existing_metadata(self):
        r = FakeResult("Test", "Test", metadata={"existing": True})
        ResultClustering.annotate([r])
        assert r.metadata["existing"] is True
        assert "cluster_id" in r.metadata
