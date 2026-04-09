"""GrowPy Nanite Export - Blender addon for exporting Grove trees as UE Nanite assemblies.

Self-contained Blender addon that reads The Grove 2.3 tree data from the active
Blender scene and exports it as Unreal Engine 5.7+ Nanite Assembly USD files
with full skeletal mesh support.

Requires:
- The Grove 2.3 Blender addon (provides the_grove_23_core API)
- Blender 4.2+ (bundled USD/pxr modules)
"""

bl_info = {
    "name": "GrowPy Nanite Export",
    "author": "GrowPy",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > GrowPy",
    "description": "Export Grove trees as Unreal Engine Nanite Assembly USD files",
    "category": "Import-Export",
}

import importlib

_MODULE_NAMES = [
    "preferences",
    "grove_extract",
    "skeleton_builder",
    "twig_converter",
    "usd_export",
    "operators",
    "panels",
]
_loaded_modules = []


def register():
    global _loaded_modules
    _loaded_modules = []
    for name in _MODULE_NAMES:
        mod = importlib.import_module(f".{name}", __name__)
        importlib.reload(mod)
        _loaded_modules.append(mod)

    for mod in _loaded_modules:
        if hasattr(mod, "register"):
            mod.register()


def unregister():
    for mod in reversed(_loaded_modules):
        if hasattr(mod, "unregister"):
            mod.unregister()
