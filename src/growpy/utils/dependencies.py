"""Dependency management and common imports for the growpy package."""

from typing import Any, Dict, List, Optional, Tuple

import math
import numpy as np
import pandas as pd

try:
    import the_grove_22_core as gc
    GROVE_CORE_AVAILABLE = True
except ImportError:
    gc = None
    GROVE_CORE_AVAILABLE = False

try:
    from pxr import Gf, Usd, UsdGeom, UsdShade, Vt, Sdf
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    Gf = Usd = UsdGeom = UsdShade = Vt = Sdf = None


def ensure_grove_available():
    """Ensure Grove core is available."""
    if not GROVE_CORE_AVAILABLE:
        raise ImportError("Grove core (the_grove_22_core) not available")


def ensure_usd_available():
    """Ensure USD Python bindings are available."""
    if not USD_AVAILABLE:
        raise ImportError("USD Python bindings not available")