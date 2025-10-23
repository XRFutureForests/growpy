"""Utilities for GrowPy.

Provides file operations, string utilities, growth analysis, and plotting.
"""

from .strings import sanitize_species_name, sanitize_filename
from .paths import ensure_dir, ensure_parent_dir

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
    "sanitize_species_name",
    "sanitize_filename",
    "ensure_dir",
    "ensure_parent_dir",
]