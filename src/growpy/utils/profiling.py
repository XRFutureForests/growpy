"""
Profiling utilities for tracking execution time of forest generation steps.

Provides a ProfileTimer class for tracking and reporting execution times
across different processing steps, with support for nested timing blocks.

Usage:
    from growpy.utils.profiling import ProfileTimer

    timer = ProfileTimer(enabled=True)

    with timer.track("grove_simulation"):
        # Simulation code here
        pass

    with timer.track("export", parent="grove_simulation"):
        # Nested timing
        pass

    timer.report()
"""

import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimingEntry:
    """Single timing entry with accumulated statistics."""

    name: str
    total_time: float = 0.0
    call_count: int = 0
    min_time: float = float("inf")
    max_time: float = 0.0
    parent: Optional[str] = None

    def add_timing(self, duration: float) -> None:
        self.total_time += duration
        self.call_count += 1
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)

    @property
    def avg_time(self) -> float:
        return self.total_time / self.call_count if self.call_count > 0 else 0.0


@dataclass
class ProfileTimer:
    """
    Profiling timer for tracking execution times across processing steps.

    Tracks cumulative time, call counts, and min/max times for each named block.
    Supports nested timing blocks for hierarchical profiling.
    """

    enabled: bool = True
    entries: dict = field(default_factory=dict)
    _start_times: dict = field(default_factory=dict)
    _active_stack: list = field(default_factory=list)

    @contextmanager
    def track(self, name: str, parent: Optional[str] = None):
        """
        Context manager to track execution time of a code block.

        Args:
            name: Identifier for this timing block
            parent: Optional parent block name for hierarchical display
        """
        if not self.enabled:
            yield
            return

        # Auto-detect parent from stack if not specified
        if parent is None and self._active_stack:
            parent = self._active_stack[-1]

        self._active_stack.append(name)
        start = time.perf_counter()

        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self._active_stack.pop()

            if name not in self.entries:
                self.entries[name] = TimingEntry(name=name, parent=parent)

            self.entries[name].add_timing(duration)

    def start(self, name: str, parent: Optional[str] = None) -> None:
        """Start timing a named block (for non-context-manager usage)."""
        if not self.enabled:
            return

        if parent is None and self._active_stack:
            parent = self._active_stack[-1]

        self._start_times[name] = time.perf_counter()
        self._active_stack.append(name)

        if name not in self.entries:
            self.entries[name] = TimingEntry(name=name, parent=parent)

    def stop(self, name: str) -> float:
        """Stop timing a named block and return duration."""
        if not self.enabled or name not in self._start_times:
            return 0.0

        duration = time.perf_counter() - self._start_times[name]
        del self._start_times[name]

        if name in self._active_stack:
            self._active_stack.remove(name)

        self.entries[name].add_timing(duration)
        return duration

    def reset(self) -> None:
        """Clear all timing data."""
        self.entries.clear()
        self._start_times.clear()
        self._active_stack.clear()

    def get_total_time(self) -> float:
        """Get total tracked time (top-level entries only to avoid double-counting)."""
        return sum(e.total_time for e in self.entries.values() if e.parent is None)

    def report(self, show_hierarchy: bool = True) -> str:
        """
        Generate a formatted profiling report.

        Args:
            show_hierarchy: If True, indent child entries under parents

        Returns:
            Formatted string report
        """
        if not self.enabled or not self.entries:
            return ""

        lines = []
        lines.append("")
        lines.append("=" * 80)
        lines.append("PROFILING REPORT")
        lines.append("=" * 80)

        total = self.get_total_time()
        lines.append(f"Total tracked time: {total:.2f}s")
        lines.append("")

        # Header
        lines.append(f"{'Step':<40} {'Total':>10} {'Calls':>7} {'Avg':>10} {'%':>7}")
        lines.append("-" * 80)

        # Build hierarchy
        if show_hierarchy:
            # Group by parent
            root_entries = [e for e in self.entries.values() if e.parent is None]
            child_map = defaultdict(list)
            for e in self.entries.values():
                if e.parent:
                    child_map[e.parent].append(e)

            def format_entry(entry: TimingEntry, indent: int = 0) -> list:
                prefix = "  " * indent
                name = f"{prefix}{entry.name}"
                if len(name) > 38:
                    name = name[:35] + "..."

                pct = (entry.total_time / total * 100) if total > 0 else 0

                result = [
                    f"{name:<40} {entry.total_time:>9.2f}s {entry.call_count:>7} "
                    f"{entry.avg_time:>9.3f}s {pct:>6.1f}%"
                ]

                # Add children
                for child in sorted(
                    child_map.get(entry.name, []),
                    key=lambda x: x.total_time,
                    reverse=True,
                ):
                    result.extend(format_entry(child, indent + 1))

                return result

            # Sort root entries by time
            for entry in sorted(root_entries, key=lambda x: x.total_time, reverse=True):
                lines.extend(format_entry(entry))
        else:
            # Flat list sorted by time
            for entry in sorted(
                self.entries.values(), key=lambda x: x.total_time, reverse=True
            ):
                pct = (entry.total_time / total * 100) if total > 0 else 0
                name = entry.name[:38] + "..." if len(entry.name) > 40 else entry.name
                lines.append(
                    f"{name:<40} {entry.total_time:>9.2f}s {entry.call_count:>7} "
                    f"{entry.avg_time:>9.3f}s {pct:>6.1f}%"
                )

        lines.append("-" * 80)
        lines.append("")

        # Performance insights
        lines.extend(self._generate_insights())

        return "\n".join(lines)

    def _generate_insights(self) -> list:
        """Generate performance insights based on timing data."""
        insights = []

        if not self.entries:
            return insights

        total = self.get_total_time()
        if total == 0:
            return insights

        # Find bottlenecks (>30% of total time)
        bottlenecks = [
            e
            for e in self.entries.values()
            if e.total_time / total > 0.30 and e.parent is None
        ]

        if bottlenecks:
            insights.append("BOTTLENECKS (>30% of total time):")
            for b in bottlenecks:
                pct = b.total_time / total * 100
                insights.append(f"  - {b.name}: {b.total_time:.2f}s ({pct:.1f}%)")
            insights.append("")

        # Find frequently called functions
        frequent = [e for e in self.entries.values() if e.call_count > 10]
        if frequent:
            insights.append("FREQUENTLY CALLED (>10 calls):")
            for f in sorted(frequent, key=lambda x: x.call_count, reverse=True)[:5]:
                insights.append(
                    f"  - {f.name}: {f.call_count} calls, avg {f.avg_time:.3f}s each"
                )
            insights.append("")

        # Find high-variance operations
        high_variance = [
            e
            for e in self.entries.values()
            if e.call_count > 1 and e.max_time > e.min_time * 3
        ]
        if high_variance:
            insights.append("HIGH VARIANCE (max > 3x min):")
            for h in high_variance[:3]:
                insights.append(
                    f"  - {h.name}: min={h.min_time:.3f}s, max={h.max_time:.3f}s"
                )
            insights.append("")

        return insights

    def print_report(self, show_hierarchy: bool = True) -> None:
        """Print the profiling report to stderr."""
        import sys

        report = self.report(show_hierarchy)
        if report:
            print(report, file=sys.stderr)


# Global timer instance for convenience
_global_timer: Optional[ProfileTimer] = None


def get_timer() -> ProfileTimer:
    """Get the global profiler instance."""
    global _global_timer
    if _global_timer is None:
        _global_timer = ProfileTimer(enabled=False)
    return _global_timer


def init_profiler(enabled: bool = True) -> ProfileTimer:
    """Initialize and return the global profiler."""
    global _global_timer
    _global_timer = ProfileTimer(enabled=enabled)
    return _global_timer
