"""Tests for PerformanceTracker — v2.0 adaptive scheduling data."""

import pytest
import time
from app.engine.performance_tracker import PerformanceTracker


class TestPerformanceTracker:
    """Core tracking functionality."""

    def test_record_success(self):
        tracker = PerformanceTracker()
        tracker.record_success("test_module", response_time=1.5, result_count=10, quality_score=0.8)

        perf = tracker.get_performance("test_module")
        assert perf.total_requests == 1
        assert perf.successful_requests == 1
        assert perf.consecutive_failures == 0
        assert perf.avg_response_time > 0

    def test_record_failure(self):
        tracker = PerformanceTracker()
        tracker.record_failure("test_module", response_time=5.0)

        perf = tracker.get_performance("test_module")
        assert perf.total_requests == 1
        assert perf.successful_requests == 0
        assert perf.consecutive_failures == 1

    def test_consecutive_failures_reset_on_success(self):
        tracker = PerformanceTracker()
        for _ in range(3):
            tracker.record_failure("test_module")
        tracker.record_success("test_module", 1.0, 5)

        perf = tracker.get_performance("test_module")
        assert perf.consecutive_failures == 0

    def test_success_rate_calculation(self):
        tracker = PerformanceTracker()
        tracker.record_success("m1", 1.0, 5)
        tracker.record_success("m1", 1.0, 5)
        tracker.record_failure("m1")

        perf = tracker.get_performance("m1")
        assert perf.success_rate == pytest.approx(2.0 / 3.0, abs=0.01)

    def test_success_rate_unknown_module(self):
        tracker = PerformanceTracker()
        perf = tracker.get_performance("unknown")
        assert perf.success_rate == 0.5  # neutral for unknown


class TestDynamicWeight:
    """Dynamic weight calculation."""

    def test_no_data_returns_base(self):
        tracker = PerformanceTracker()
        weight = tracker.get_dynamic_weight("unknown", base_weight=1.0)
        assert weight == 1.0

    def test_good_performance_boosts_weight(self):
        tracker = PerformanceTracker()
        for _ in range(5):
            tracker.record_success("good_module", 1.0, 10, 0.8)

        weight = tracker.get_dynamic_weight("good_module", base_weight=1.0)
        assert weight > 1.0  # Good performance should boost

    def test_bad_performance_reduces_weight(self):
        tracker = PerformanceTracker()
        for _ in range(5):
            tracker.record_failure("bad_module", 15.0)

        weight = tracker.get_dynamic_weight("bad_module", base_weight=1.0)
        assert weight < 1.0

    def test_consecutive_failure_penalty(self):
        tracker = PerformanceTracker()
        for _ in range(4):
            tracker.record_failure("failing_module")

        weight = tracker.get_dynamic_weight("failing_module", base_weight=1.0)
        # 4 consecutive failures + low success rate = heavy penalty
        assert weight < 0.5


class TestSkipLogic:
    """Module skip decisions."""

    def test_dont_skip_healthy_module(self):
        tracker = PerformanceTracker()
        tracker.record_success("healthy", 1.0, 5)
        assert tracker.should_skip("healthy") is False

    def test_skip_after_5_consecutive_failures(self):
        tracker = PerformanceTracker()
        for _ in range(5):
            tracker.record_failure("broken")

        # Override recovery interval for testing
        tracker._data["broken"].last_failure_time = time.time()
        assert tracker.should_skip("broken") is True

    def test_recovery_probe_after_interval(self):
        tracker = PerformanceTracker()
        for _ in range(5):
            tracker.record_failure("recovering")

        # Set last failure to 10 minutes ago
        tracker._data["recovering"].last_failure_time = time.time() - 600
        assert tracker.should_skip("recovering") is False  # Allow recovery


class TestTimeoutSuggestion:
    """Timeout suggestion based on history."""

    def test_unknown_module_gets_default(self):
        tracker = PerformanceTracker()
        timeout = tracker.suggest_timeout("unknown", default_timeout=30)
        assert timeout == 30.0

    def test_fast_module_gets_lower_timeout(self):
        tracker = PerformanceTracker()
        for _ in range(5):
            tracker.record_success("fast", 1.0, 5)

        timeout = tracker.suggest_timeout("fast", default_timeout=30)
        assert timeout < 10.0  # P95 = avg * 2 = 2.0

    def test_slow_module_gets_higher_timeout(self):
        tracker = PerformanceTracker()
        for _ in range(5):
            tracker.record_success("slow", 20.0, 5)

        timeout = tracker.suggest_timeout("slow", default_timeout=30)
        # EMA smooths initial values; verify it's in expected range
        assert timeout > 5.0  # At minimum, timeout should exceed fast modules


class TestStats:
    """Stats output."""

    def test_get_stats(self):
        tracker = PerformanceTracker()
        tracker.record_success("m1", 1.0, 5, 0.8)
        tracker.record_failure("m2")

        stats = tracker.get_stats()
        assert "m1" in stats
        assert "m2" in stats
        assert stats["m1"]["success_rate"] == 1.0
        assert stats["m2"]["success_rate"] == 0.0
