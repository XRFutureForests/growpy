"""PXR initialization utilities with Unreal schema support.

Ensures bundled pxr modules are exposed and Unreal USD schemas are registered.
"""

import os


def ensure_pxr_with_unreal_schema() -> None:
    """Expose bundled pxr modules and register Unreal USD schema plugin.

    This should be called before importing pxr in any module that needs
    access to Unreal Nanite Assembly schemas.

    Performs:
    1. Exposes bundled modules if using bpy's bundled USD
    2. Registers Unreal schema plugin from PXR_PLUGINPATH_NAME if set
    """
    # Expose bundled modules if using bpy
    try:
        import bpy  # type: ignore

        if hasattr(bpy.utils, "expose_bundled_modules"):
            bpy.utils.expose_bundled_modules()  # type: ignore[attr-defined]
    except ImportError:
        pass

    # Register Unreal schema plugin if PXR_PLUGINPATH_NAME is set
    env_path = os.environ.get("PXR_PLUGINPATH_NAME")
    if env_path:
        try:
            from pxr import Plug  # type: ignore

            abs_path = os.path.abspath(env_path)
            if os.path.exists(abs_path):
                reg = Plug.Registry()
                # Only register if not already registered
                if not reg.GetPluginWithName("unreal"):
                    reg.RegisterPlugins(abs_path)
        except ImportError:
            pass
