"""Utilities for GrowPy.

Provides growth analysis and plotting.
"""

try:
    from .analysis import SpeciesGrowthAnalyzer
except ImportError:
    SpeciesGrowthAnalyzer = None

try:
    from .plotting import plot_growth_curves
except ImportError:
    plot_growth_curves = None

__all__ = [
    "SpeciesGrowthAnalyzer",
    "plot_growth_curves",
]