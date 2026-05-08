"""Module performance tracker — v2.0 adaptive scheduling data.

Tracks per-module success rate, response time, result quality over time.
Provides dynamic weights for scheduler to make data-driven decisions.

Inspired by:
- SearXNG: engine timeout/retry configuration
- Circuit Breaker pattern: consecutive failure tracking + auto-recovery
"""

import json
import logging
import time
from pathlib import Path
from threading import Lock

from app.models import ModulePerformance

logger = logging.getLogger(__name__)

# Persistence path (relative to project root)
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_PERF_FILE = _DATA_DIR / "module_performance.json"

# Exponential moving average alpha (0.1 = slow adaptation)
_EMA_ALPHA = 0.1

# How many seconds before a module is considered for recovery probe
_RECOVERY_INTERVAL = 300  # 5 minutes


class PerformanceTracker:
    """Thread-safe module performance tracker with EMA smoothing."""

    def __init__(self):
        self._lock = Lock()
        self._data: dict[str, ModulePerformance] = {}
        self._load()

    def record_success(
        self,
        module_name: str,
        response_time: float,
        result_count: int,
        quality_score: float = 0.5,
    ) -> None:
        """Record a successful search for a module."""
        with self._lock:
            perf = self._get_or_create(module_name)

            perf.total_requests += 1
            perf.successful_requests += 1
            perf.consecutive_failures = 0
            perf.last_success_time = time.time()

            # EMA update for smooth adaptation
            perf.avg_response_time = self._ema_update(
                perf.avg_response_time, response_time
            )
            perf.avg_result_count = self._ema_update(
                perf.avg_result_count, float(result_count)
            )
            perf.avg_quality_score = self._ema_update(
                perf.avg_quality_score, quality_score
            )

            # Update 7-day success rate (simplified: use last 100 requests)
            if perf.total_requests > 0:
                perf.success_rate_7d = perf.successful_requests / perf.total_requests

    def record_failure(self, module_name: str, response_time: float = 0.0) -> None:
        """Record a failed search for a module."""
        with self._lock:
            perf = self._get_or_create(module_name)

            perf.total_requests += 1
            perf.consecutive_failures += 1
            perf.last_failure_time = time.time()

            # Update response time even on failure (for timeout estimation)
            if response_time > 0:
                perf.avg_response_time = self._ema_update(
                    perf.avg_response_time, response_time
                )

            if perf.total_requests > 0:
                perf.success_rate_7d = perf.successful_requests / perf.total_requests

    def get_performance(self, module_name: str) -> ModulePerformance:
        """Get performance data for a module."""
        with self._lock:
            return self._get_or_create(module_name)

    def get_dynamic_weight(self, module_name: str, base_weight: float = 1.0) -> float:
        """Calculate dynamic weight based on performance.

        Weight = base_weight * success_rate_multiplier * quality_multiplier * speed_multiplier

        Returns a value that adjusts base_weight up or down.
        """
        with self._lock:
            perf = self._get_or_create(module_name)

            # No data -> return base weight
            if perf.total_requests < 3:
                return base_weight

            # Success rate multiplier: 0.5x (50% SR) to 1.2x (95%+ SR)
            sr = perf.success_rate
            sr_mult = 0.5 + sr * 0.7

            # Quality multiplier: 0.7x to 1.3x based on avg_quality_score
            quality_mult = 0.7 + perf.avg_quality_score * 0.6

            # Speed multiplier: faster modules get slight boost
            if perf.avg_response_time > 0:
                # <2s = fast (1.1x), 2-10s = normal (1.0x), >10s = slow (0.9x)
                if perf.avg_response_time < 2.0:
                    speed_mult = 1.1
                elif perf.avg_response_time < 10.0:
                    speed_mult = 1.0
                else:
                    speed_mult = 0.9
            else:
                speed_mult = 1.0

            # Consecutive failure penalty
            if perf.consecutive_failures >= 3:
                sr_mult *= 0.5  # Heavy penalty for repeated failures

            return base_weight * sr_mult * quality_mult * speed_mult

    def should_skip(self, module_name: str) -> bool:
        """Check if a module should be skipped due to poor performance.

        A module is skipped if:
        - 5+ consecutive failures AND last failure < RECOVERY_INTERVAL seconds ago
        """
        with self._lock:
            perf = self._get_or_create(module_name)

            if perf.consecutive_failures >= 5:
                # Allow recovery probe after interval
                if perf.last_failure_time > 0:
                    elapsed = time.time() - perf.last_failure_time
                    if elapsed < _RECOVERY_INTERVAL:
                        return True
                    # Recovery probe: reset consecutive failures
                    logger.info(
                        "Module %s recovery probe after %.0fs",
                        module_name, elapsed,
                    )
                    perf.consecutive_failures = 0
            return False

    def suggest_timeout(self, module_name: str, default_timeout: int = 30) -> float:
        """Suggest timeout based on historical response time.

        Uses P95 estimation: avg * 2.0, clamped to [5, 60].
        """
        with self._lock:
            perf = self._get_or_create(module_name)

            if perf.total_requests < 3:
                return float(default_timeout)

            # P95 estimation
            suggested = perf.avg_response_time * 2.0
            return max(5.0, min(suggested, 60.0))

    def get_stats(self) -> dict[str, dict]:
        """Get all module performance stats."""
        with self._lock:
            return {
                name: {
                    "total": perf.total_requests,
                    "success_rate": round(perf.success_rate, 3),
                    "avg_time": round(perf.avg_response_time, 2),
                    "avg_quality": round(perf.avg_quality_score, 3),
                    "consecutive_failures": perf.consecutive_failures,
                    "healthy": perf.is_healthy,
                }
                for name, perf in self._data.items()
            }

    def save(self) -> None:
        """Persist performance data to disk."""
        with self._lock:
            try:
                _DATA_DIR.mkdir(parents=True, exist_ok=True)
                data = {
                    name: perf.model_dump()
                    for name, perf in self._data.items()
                }
                _PERF_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            except Exception as e:
                logger.warning("Failed to save performance data: %s", e)

    def _get_or_create(self, module_name: str) -> ModulePerformance:
        """Get existing or create new performance entry."""
        if module_name not in self._data:
            self._data[module_name] = ModulePerformance(name=module_name)
        return self._data[module_name]

    def _load(self) -> None:
        """Load performance data from disk."""
        try:
            if _PERF_FILE.exists():
                raw = json.loads(_PERF_FILE.read_text(encoding="utf-8"))
                for name, data in raw.items():
                    self._data[name] = ModulePerformance(**data)
                logger.info("Loaded performance data for %d modules", len(self._data))
        except Exception as e:
            logger.warning("Failed to load performance data: %s", e)

    @staticmethod
    def _ema_update(current: float, new_value: float) -> float:
        """Exponential Moving Average update."""
        return current * (1 - _EMA_ALPHA) + new_value * _EMA_ALPHA


# Global singleton
perf_tracker = PerformanceTracker()
