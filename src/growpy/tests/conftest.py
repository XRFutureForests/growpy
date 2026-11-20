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

import pytest

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
# Skip just those modules instead, so the 734 tests that need no Grove still
# run. Note this only covers import-time failures: a module that reaches Grove
# code lazily (as test_yield_tables did via growpy.utils.analysis) collects
# fine and fails at run time instead; the report hook below skips those.
_GROVE_DEPENDENT = [
    "test_analysis.py",
    "test_assembly_export.py",
    "test_forest_exports.py",
    "test_forest_stages.py",
    "test_generate_forest.py",
    "test_milestone_ceiling.py",
    "test_obj_export.py",
    "test_obj_export_direct.py",
    "test_skeleton.py",
    "test_tree.py",
    "test_tree_export.py",
    "test_twig.py",
]


def _grove_available() -> bool:
    try:
        return importlib.util.find_spec("the_grove_23_core") is not None
    except Exception:  # pragma: no cover - broken/partial install
        return False


_HAVE_GROVE = _grove_available()
collect_ignore = [] if _HAVE_GROVE else list(_GROVE_DEPENDENT)


# Tests that reach Grove code lazily (at run time, not import time) would fail without it;
# report them as skipped instead. Only active when the Grove is absent, so local runs are unchanged.
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    exc = call.excinfo
    if (not _HAVE_GROVE and rep.failed and exc is not None
            and exc.errisinstance(ModuleNotFoundError) and "the_grove_23_core" in str(exc.value)):
        rep.outcome = "skipped"
        rep.longrepr = (str(item.path), item.location[1] or 0, "Skipped: needs The Grove (the_grove_23_core)")
