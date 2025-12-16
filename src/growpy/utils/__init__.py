"""Utilities for GrowPy.

Provides growth analysis, plotting, and profiling.
"""

try:
    from .analysis import SpeciesGrowthAnalyzer
except ImportError:
    SpeciesGrowthAnalyzer = None

try:
    from .plotting import plot_growth_curves
except ImportError:
    plot_growth_curves = None

from .profiling import ProfileTimer, get_timer, init_profiler

__all__ = [
    "SpeciesGrowthAnalyzer",
    "plot_growth_curves",
    "ProfileTimer",
    "get_timer",
    "init_profiler",
]
