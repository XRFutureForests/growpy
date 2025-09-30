"""Configuration management for GrowPy.

This module handles configuration, species lookup, and asset path resolution.
"""

from .settings import (
    GrowPyConfig,
    get_config,
    get_global_config,
    set_global_config,
)

__all__ = [
    "GrowPyConfig",
    "get_config",
    "get_global_config",
    "set_global_config",
]