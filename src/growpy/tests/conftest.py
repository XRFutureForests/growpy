"""Pytest session bootstrap.

Import bpy before pytest collection pulls in other native extensions
(numpy/scipy/Pillow/etc.). bpy ships its own bundled DLLs (USD/pxr, TBB, ...);
when a conflicting version of one of those shared libraries is loaded into the
process first, ``import bpy`` intermittently aborts with a native
entry-point fault (Windows 0xC0000139). Loading bpy first makes its bundled
DLLs win the load race, which makes the suite import-stable.

bpy is only present in the growpy conda env, so its absence is tolerated.
"""

import importlib.util

try:
    import bpy  # noqa: F401
except Exception:  # pragma: no cover - bpy missing (e.g. CI without Blender)
    pass


# The Grove is commercial and not distributed with this repository (see
# README "Add The Grove 2.3"), so `the_grove_23_core` is absent for anyone
# without a licence, and in CI. ``growpy.core.__init__`` eagerly re-exports
# from ``forest.py``, which imports it unguarded -- so without it, collection
# of every module that touches growpy.core raised ImportError and pytest
# aborted the *entire* run with 0 tests executed.
#
# Skip just those modules instead, so the ~750 tests that need no Grove still
# run. If a new test module starts importing growpy.core it will fail loudly
# here rather than silently; add it to the list below.
_GROVE_DEPENDENT = [
    "test_analysis.py",
    "test_assembly_export.py",
    "test_forest_exports.py",
    "test_forest_stages.py",
    "test_skeleton.py",
    "test_tree.py",
    "test_twig.py",
]


def _grove_available() -> bool:
    try:
        return importlib.util.find_spec("the_grove_23_core") is not None
    except Exception:  # pragma: no cover - broken/partial install
        return False


collect_ignore = [] if _grove_available() else list(_GROVE_DEPENDENT)
