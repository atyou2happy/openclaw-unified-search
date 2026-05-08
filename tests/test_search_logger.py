"""Tests for SearchLogger — search analytics logging."""

import json
import tempfile
from pathlib import Path

import pytest

from app.engine.search_logger import SearchLogger


@pytest.fixture
def logger(tmp_path):
    """Create a SearchLogger with a temp directory."""
    return SearchLogger(log_dir=tmp_path)


class TestSearchLogger:
    """SearchLogger unit tests."""

    def test_log_creates_file(self, logger, tmp_path):
        logger.log_search("test query", ["ddg", "brave"], 5, 0.5)
        log_path = tmp_path / "search_log.jsonl"
        assert log_path.exists()

    def test_log_entry_format(self, logger, tmp_path):
        logger.log_search(
            query="python async",
            sources_used=["ddg", "stackoverflow"],
            total_results=8,
            elapsed=1.23,
            errors={"ddg": "timeout"},
            intent={"types": ["code"], "confidence": 0.8},
            query_analysis={"language": "en", "primary_type": "code", "spell_corrected": False},
        )
        log_path = tmp_path / "search_log.jsonl"
        with open(log_path) as f:
            entry = json.loads(f.readline())

        assert entry["query"] == "python async"
        assert entry["sources"] == ["ddg", "stackoverflow"]
        assert entry["n_results"] == 8
        assert entry["elapsed"] == 1.23
        assert entry["errors"] is True
        assert entry["n_errors"] == 1
        assert entry["intent"]["types"] == ["code"]
        assert entry["qa"]["lang"] == "en"

    def test_log_truncates_long_query(self, logger, tmp_path):
        long_query = "x" * 500
        logger.log_search(long_query, [], 0, 0.1)
        with open(tmp_path / "search_log.jsonl") as f:
            entry = json.loads(f.readline())
        assert len(entry["query"]) == 200

    def test_log_no_errors(self, logger, tmp_path):
        logger.log_search("test", ["ddg"], 3, 0.5)
        with open(tmp_path / "search_log.jsonl") as f:
            entry = json.loads(f.readline())
        assert entry["errors"] is False
        assert entry["n_errors"] == 0

    def test_log_no_intent(self, logger, tmp_path):
        logger.log_search("test", ["ddg"], 1, 0.3)
        with open(tmp_path / "search_log.jsonl") as f:
            entry = json.loads(f.readline())
        assert "intent" not in entry
        assert "qa" not in entry

    def test_multiple_entries(self, logger, tmp_path):
        for i in range(5):
            logger.log_search(f"query {i}", ["ddg"], i, 0.1 * i)
        with open(tmp_path / "search_log.jsonl") as f:
            lines = f.readlines()
        assert len(lines) == 5

    def test_get_stats_empty(self, logger):
        stats = logger.get_stats()
        assert stats["total_queries"] == 0

    def test_get_stats_basic(self, logger):
        logger.log_search("python", ["ddg", "github"], 10, 0.5)
        logger.log_search("rust", ["ddg"], 5, 0.3)
        logger.log_search("python", ["brave"], 8, 0.4, errors={"brave": "fail"})

        stats = logger.get_stats(last_n=10)
        assert stats["total_queries"] == 3
        assert stats["avg_elapsed"] > 0
        assert stats["avg_results"] > 0
        assert stats["error_rate"] == pytest.approx(1/3, abs=0.05)
        assert len(stats["top_queries"]) >= 1
        assert stats["top_queries"][0][0] == "python"  # most frequent
        assert stats["top_queries"][0][1] == 2

    def test_get_stats_source_frequency(self, logger):
        logger.log_search("q1", ["ddg", "github"], 3, 0.1)
        logger.log_search("q2", ["ddg", "brave"], 2, 0.2)
        logger.log_search("q3", ["ddg"], 1, 0.1)

        stats = logger.get_stats()
        sources = dict(stats["top_sources"])
        assert sources["ddg"] == 3
        assert sources["github"] == 1

    def test_rotation(self, tmp_path):
        sl = SearchLogger(log_dir=tmp_path)
        # Write a lot to trigger rotation (set small limit for testing)
        sl._log_path = tmp_path / "search_log.jsonl"
        # Manually create a large file to trigger rotation
        with open(sl._log_path, "w") as f:
            f.write("x" * (10 * 1024 * 1024 + 1))  # >10MB

        sl.log_search("after rotation", ["ddg"], 1, 0.1)

        # Rotated file should exist
        assert (tmp_path / "search_log.1.jsonl").exists()
        # New log should have our entry
        with open(sl._log_path) as f:
            entry = json.loads(f.readline())
        assert entry["query"] == "after rotation"
