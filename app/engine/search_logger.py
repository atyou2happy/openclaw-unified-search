"""Search query logger — lightweight search analytics (v2.1).

Records query, modules used, results count, elapsed, errors, and quality metrics.
Persists to data/search_log.jsonl (append-only, rotated at 10MB).
"""

import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB rotation


class SearchLogger:
    """Lightweight append-only search log for analytics."""

    def __init__(self, log_dir: str | Path | None = None):
        self._log_dir = Path(log_dir) if log_dir else _DEFAULT_LOG_DIR
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / "search_log.jsonl"
        self._write_count = 0

    def log_search(
        self,
        query: str,
        sources_used: list[str],
        total_results: int,
        elapsed: float,
        errors: dict | None = None,
        intent: dict | None = None,
        query_analysis: dict | None = None,
    ) -> None:
        """Log a single search request."""
        entry = {
            "ts": time.time(),
            "query": query[:200],  # Truncate long queries
            "sources": sources_used,
            "n_results": total_results,
            "elapsed": round(elapsed, 3),
            "errors": bool(errors),
            "n_errors": len(errors) if errors else 0,
        }
        if intent:
            entry["intent"] = {
                "types": list(intent.get("types", []))[:5],
                "confidence": intent.get("confidence", 0.5),
            }
        if query_analysis:
            entry["qa"] = {
                "lang": query_analysis.get("language", ""),
                "type": query_analysis.get("primary_type", ""),
                "corrected": query_analysis.get("spell_corrected", False),
            }

        self._append(entry)

    def _append(self, entry: dict) -> None:
        """Append entry to JSONL log, with rotation."""
        try:
            # Rotate if needed
            if (
                self._log_path.exists()
                and self._log_path.stat().st_size > _MAX_LOG_SIZE
            ):
                self._rotate()

            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._write_count += 1
        except Exception as e:
            logger.debug("SearchLogger write failed: %s", e)

    def _rotate(self) -> None:
        """Rotate log file: search_log.jsonl → search_log.1.jsonl."""
        rotated = self._log_path.with_suffix(".1.jsonl")
        try:
            if rotated.exists():
                rotated.unlink()
            self._log_path.rename(rotated)
        except Exception as e:
            logger.debug("SearchLogger rotation failed: %s", e)

    def get_stats(self, last_n: int = 100) -> dict:
        """Compute basic stats from recent log entries."""
        entries = self._read_recent(last_n)
        if not entries:
            return {"total_queries": 0}

        total = len(entries)
        avg_elapsed = sum(e.get("elapsed", 0) for e in entries) / total
        avg_results = sum(e.get("n_results", 0) for e in entries) / total
        error_rate = sum(1 for e in entries if e.get("errors")) / total

        # Query frequency
        query_counts: dict[str, int] = {}
        for e in entries:
            q = e.get("query", "")
            if q:
                query_counts[q] = query_counts.get(q, 0) + 1

        # Source frequency
        source_counts: dict[str, int] = {}
        for e in entries:
            for s in e.get("sources", []):
                source_counts[s] = source_counts.get(s, 0) + 1

        return {
            "total_queries": total,
            "avg_elapsed": round(avg_elapsed, 3),
            "avg_results": round(avg_results, 1),
            "error_rate": round(error_rate, 3),
            "top_queries": sorted(query_counts.items(), key=lambda x: -x[1])[:10],
            "top_sources": sorted(source_counts.items(), key=lambda x: -x[1])[:10],
        }

    def _read_recent(self, n: int) -> list[dict]:
        """Read last N entries from log file."""
        entries = []
        if not self._log_path.exists():
            return entries
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[-n:]:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass
        return entries


# Global instance
search_logger = SearchLogger()
