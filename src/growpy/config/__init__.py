"""Configuration management for GrowPy.

Provides project configuration and asset path resolution.
"""

from .core import GrowPyConfig, get_config

__all__ = [
    "GrowPyConfig",
    "get_config",
]
