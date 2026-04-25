"""Search engine package — re-exports for backward compatibility.

All public APIs remain identical to the old monolithic engine.py:
  from app.engine import engine, QueryIntent, ResultMerger, avail_cache
"""

from app.engine.availability import AvailabilityCache, avail_cache
from app.engine.intent import QueryIntent
from app.engine.merger import ResultMerger
from app.engine.scheduler import SearchEngine

# Global engine instance (same as before)
engine = SearchEngine()

__all__ = [
    "engine",
    "QueryIntent",
    "ResultMerger",
    "AvailabilityCache",
    "avail_cache",
]
