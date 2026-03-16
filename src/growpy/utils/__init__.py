"""Utilities for GrowPy.

Provides growth analysis, plotting, and profiling.
"""

try:
    from .analysis import SpeciesGrowthAnalyzer, compare_smoothing_effect
except ImportError:
    SpeciesGrowthAnalyzer = None
    compare_smoothing_effect = None

try:
    from .plotting import plot_growth_curves
except ImportError:
    plot_growth_curves = None

from .diagnostics import dump_grove_data
from .naming import camel_to_snake, standardize_species_name, standardize_twig_name
from .profiling import ProfileTimer, get_timer, init_profiler

__all__ = [
    "SpeciesGrowthAnalyzer",
    "compare_smoothing_effect",
    "plot_growth_curves",
    "dump_grove_data",
    "camel_to_snake",
    "standardize_species_name",
    "standardize_twig_name",
    "ProfileTimer",
    "get_timer",
    "init_profiler",
]
