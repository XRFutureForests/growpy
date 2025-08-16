"""
Common imports and utilities for the growpy package.
Centralizes frequently used imports and grove core access.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Common scientific computing imports
import math
import numpy as np
import pandas as pd

# Grove core import with fallback
try:
    import the_grove_22_core as gc
    GROVE_CORE_AVAILABLE = True
except ImportError:
    gc = None
    GROVE_CORE_AVAILABLE = False

# USD imports with fallback
try:
    from pxr import Gf, Usd, UsdGeom, UsdShade, Vt, Sdf
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    Gf = Usd = UsdGeom = UsdShade = Vt = Sdf = None


def ensure_grove_available():
    """Ensure Grove core is available, raise ImportError if not."""
    if not GROVE_CORE_AVAILABLE:
        raise ImportError("Grove core (the_grove_22_core) not available")


def ensure_usd_available():
    """Ensure USD Python bindings are available, raise ImportError if not."""
    if not USD_AVAILABLE:
        raise ImportError("USD Python bindings not available")


def add_src_to_path():
    """Add src directory to Python path for Grove imports (used in utils)."""
    current_file = Path(__file__)
    src_path = current_file.parents[2]  # Go up from growpy -> src -> project_root
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))