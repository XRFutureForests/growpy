"""Tests for growpy.utils.profiling module."""

import time

import pytest

from growpy.utils.profiling import ProfileTimer, TimingEntry


class TestTimingEntry:
    """Tests for TimingEntry dataclass."""

    def test_initial_values(self):
        entry = TimingEntry(name="test")
        assert entry.total_time == 0.0
        assert entry.call_count == 0
        assert entry.min_time == float("inf")
        assert entry.max_time == 0.0

    def test_add_timing(self):
        entry = TimingEntry(name="test")
        entry.add_timing(1.0)
        assert entry.total_time == 1.0
        assert entry.call_count == 1
        assert entry.min_time == 1.0
        assert entry.max_time == 1.0

    def test_multiple_timings(self):
        entry = TimingEntry(name="test")
        entry.add_timing(1.0)
        entry.add_timing(3.0)
        entry.add_timing(2.0)
        assert entry.total_time == pytest.approx(6.0)
        assert entry.call_count == 3
        assert entry.min_time == 1.0
        assert entry.max_time == 3.0

    def test_avg_time(self):
        entry = TimingEntry(name="test")
        entry.add_timing(1.0)
        entry.add_timing(3.0)
        assert entry.avg_time == pytest.approx(2.0)

    def test_avg_time_zero_calls(self):
        entry = TimingEntry(name="test")
        assert entry.avg_time == 0.0


class TestProfileTimer:
    """Tests for ProfileTimer context manager and tracking."""

    def test_track_records_entry(self):
        timer = ProfileTimer(enabled=True)
        with timer.track("test_step"):
            pass
        assert "test_step" in timer.entries
        assert timer.entries["test_step"].call_count == 1

    def test_track_measures_duration(self):
        timer = ProfileTimer(enabled=True)
        with timer.track("sleep_step"):
            time.sleep(0.05)
        assert timer.entries["sleep_step"].total_time >= 0.04

    def test_disabled_timer_skips(self):
        timer = ProfileTimer(enabled=False)
        with timer.track("skipped"):
            pass
        assert len(timer.entries) == 0

    def test_nested_tracking(self):
        timer = ProfileTimer(enabled=True)
        with timer.track("parent"):
            with timer.track("child"):
                pass
        assert "parent" in timer.entries
        assert "child" in timer.entries
        assert timer.entries["child"].parent == "parent"

    def test_multiple_calls_accumulate(self):
        timer = ProfileTimer(enabled=True)
        for _ in range(3):
            with timer.track("repeated"):
                pass
        assert timer.entries["repeated"].call_count == 3

    def test_start_stop(self):
        timer = ProfileTimer(enabled=True)
        timer.start("manual")
        time.sleep(0.01)
        duration = timer.stop("manual")
        assert duration >= 0.005
        assert timer.entries["manual"].call_count == 1

    def test_stop_unknown_returns_zero(self):
        timer = ProfileTimer(enabled=True)
        assert timer.stop("unknown") == 0.0

    def test_reset_clears_all(self):
        timer = ProfileTimer(enabled=True)
        with timer.track("step"):
            pass
        timer.reset()
        assert len(timer.entries) == 0

    def test_get_total_time_top_level_only(self):
        timer = ProfileTimer(enabled=True)
        with timer.track("parent"):
            time.sleep(0.02)
            with timer.track("child"):
                time.sleep(0.01)
        # Total should only count parent (top-level), not double-count child
        total = timer.get_total_time()
        parent_time = timer.entries["parent"].total_time
        assert total == pytest.approx(parent_time)

    def test_report_empty(self):
        timer = ProfileTimer(enabled=True)
        assert timer.report() == ""

    def test_report_disabled(self):
        timer = ProfileTimer(enabled=False)
        assert timer.report() == ""

    def test_report_has_content(self):
        timer = ProfileTimer(enabled=True)
        with timer.track("test"):
            pass
        report = timer.report()
        assert "test" in report
        assert "PROFILING REPORT" in report

    def test_explicit_parent(self):
        timer = ProfileTimer(enabled=True)
        with timer.track("root"):
            pass
        with timer.track("leaf", parent="root"):
            pass
        assert timer.entries["leaf"].parent == "root"

    def test_track_records_timing_when_body_raises(self):
        timer = ProfileTimer(enabled=True)
        with pytest.raises(ValueError):
            with timer.track("failing_step"):
                raise ValueError("boom")
        assert "failing_step" in timer.entries
        assert timer.entries["failing_step"].call_count == 1

    def test_track_cleans_stack_when_body_raises(self):
        timer = ProfileTimer(enabled=True)
        with pytest.raises(RuntimeError):
            with timer.track("error_step"):
                raise RuntimeError("oops")
        assert timer._active_stack == []

    def test_nested_track_exception_in_child_preserves_parent(self):
        timer = ProfileTimer(enabled=True)
        with pytest.raises(ZeroDivisionError):
            with timer.track("outer"):
                with timer.track("inner"):
                    1 / 0
        assert "outer" in timer.entries
        assert "inner" in timer.entries
        assert timer._active_stack == []

    def test_track_exception_does_not_corrupt_subsequent_tracking(self):
        timer = ProfileTimer(enabled=True)
        with pytest.raises(ValueError):
            with timer.track("bad"):
                raise ValueError("fail")
        with timer.track("good"):
            pass
        assert timer.entries["good"].call_count == 1
        assert timer.entries["good"].parent is None
