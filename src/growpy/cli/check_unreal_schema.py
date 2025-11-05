import os
import sys
from pathlib import Path


def _expose_pxr_if_bundled() -> None:
    try:
        import bpy  # type: ignore

        try:
            bpy.utils.expose_bundled_modules()  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception:
        pass


def check_unreal_schema() -> int:
    env_path = os.environ.get("PXR_PLUGINPATH_NAME")
    print(f"PXR_PLUGINPATH_NAME={env_path}")

    _expose_pxr_if_bundled()

    try:
        from pxr import Plug  # type: ignore
    except Exception as e:
        print("pxr not available:", repr(e))
        print("Ensure conda env is active and bpy/usd are installed.")
        return 2

    reg = Plug.Registry()
    plugin = reg.GetPluginWithName("unreal")

    # If not found via env var, try manual registration with absolute path
    if not plugin and env_path:
        abs_path = os.path.abspath(env_path)
        print(
            f"Plugin not auto-discovered; attempting manual registration from: {abs_path}"
        )
        if os.path.exists(abs_path):
            reg.RegisterPlugins(abs_path)
            plugin = reg.GetPluginWithName("unreal")
        else:
            print(f"ERROR: Path does not exist: {abs_path}")
            return 1

    if not plugin:
        print("Unreal USD schema plugin not found in Plug registry.")
        print(
            "Ensure PXR_PLUGINPATH_NAME points to a valid directory with plugInfo.json."
        )
        return 1

    print("Unreal plugin found:")
    print("  path:", plugin.path)
    print("  resourcePath:", plugin.resourcePath)
    print("  loaded:", plugin.isLoaded)

    # Check that schema types are accessible via Usd.SchemaRegistry
    try:
        from pxr import Tf, Usd  # type: ignore

        schema_reg = Usd.SchemaRegistry()
        expected = [
            "NaniteAssemblyRootAPI",
            "NaniteAssemblySkelBindingAPI",
            "NaniteAssemblyExternalRefAPI",
        ]

        found = []
        missing = []
        for schema_name in expected:
            schema_type = schema_reg.GetTypeFromName(schema_name)
            # Check if type is valid (not Unknown type)
            if schema_type and schema_type != Tf.Type.Unknown:
                found.append(schema_name)
            else:
                missing.append(schema_name)

        print(f"  schemas found: {len(found)}/{len(expected)}")
        if found:
            print(f"    ✓ {', '.join(found)}")
        if missing:
            print(f"    ✗ Missing: {', '.join(missing)}")
            return 3
    except Exception as e:
        print(f"  Schema registry check failed: {e}")
        return 3

    # Optional: quick scan of a recently generated assembly to confirm authored tokens
    try:
        base = Path("data/output")
        assembly = next(base.rglob("*_nanite_assembly.usda"))
        txt = assembly.read_text(encoding="utf-8", errors="ignore")
        has_root = "NaniteAssemblyRootAPI" in txt
        has_bind = "NaniteAssemblySkelBindingAPI" in txt
        has_elem = "elementSize = 1" in txt
        has_skel_rel = "unreal:naniteAssembly:skeleton" in txt
        print("Assembly check (first match under data/output):")
        print("  file:", assembly)
        print("  api RootAPI:", has_root, " SkelBindingAPI:", has_bind)
        print("  elementSize=1:", has_elem, " skeleton rel:", has_skel_rel)
    except StopIteration:
        pass
    except Exception as e:
        print("Assembly scan error:", repr(e))

    return 0


if __name__ == "__main__":
    sys.exit(check_unreal_schema())
