"""Pytest session bootstrap.

Import bpy before pytest collection pulls in other native extensions
(numpy/scipy/Pillow/etc.). bpy ships its own bundled DLLs (USD/pxr, TBB, ...);
when a conflicting version of one of those shared libraries is loaded into the
process first, ``import bpy`` intermittently aborts with a native
entry-point fault (Windows 0xC0000139). Loading bpy first makes its bundled
DLLs win the load race, which makes the suite import-stable.

bpy is only present in the growpy conda env, so its absence is tolerated.
"""

try:
    import bpy  # noqa: F401
except Exception:  # pragma: no cover - bpy missing (e.g. CI without Blender)
    pass
