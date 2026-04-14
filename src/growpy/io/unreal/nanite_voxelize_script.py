"""
Generate UE Python script that batch-sets Nanite shape preservation to Voxelize.

Separated from the import batch scripts because voxelization is memory-intensive
and benefits from a fresh UE session (restart between import and voxelize).

The generated script scans the Content Browser for all ``*_assembly``
SkeletalMeshes under the import path and applies Nanite Voxelize shape
preservation, then triggers a Nanite rebuild per mesh.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


_VOXELIZE_SCRIPT_BODY = '''"""
GrowPy Nanite Voxelize - Auto-generated.

Sets Nanite shape preservation to Voxelize on all assembly SkeletalMeshes
under IMPORT_PATH.  Run this AFTER importing all batches (ideally after
restarting UE to reclaim VRAM).

Execute in Unreal Engine:
1. Right-click > "Execute Python File in Unreal"
2. Or: exec(open(r"{script_path}").read())
"""

import gc
import os
import time
import unreal


IMPORT_PATH = "{import_path}"

# Resume support: track completed meshes to allow crash recovery.
_PROGRESS_FILE = os.path.join(
    os.path.dirname(r"{script_path}"),
    "growpy_nanite_voxelize_done.txt",
)


def _set_nanite_shape_voxelize(mesh, label):
    """Set Nanite shape preservation to Voxelize using multiple strategies.

    ENaniteShapePreservation: None=0, PreserveArea=1, Voxelize=2
    The exact Python API varies by UE version, so we try several approaches.
    """
    strategies = []

    # Strategy A: Enum without E prefix (UE 5.4+ Python reflection)
    try:
        ns = mesh.get_editor_property("nanite_settings")
        ns.set_editor_property(
            "shape_preservation",
            unreal.NaniteShapePreservation.VOXELIZE,
        )
        mesh.set_editor_property("nanite_settings", ns)
        return True
    except Exception as e:
        strategies.append(f"enum_no_e: {{e}}")

    # Strategy B: Enum with E prefix
    try:
        ns = mesh.get_editor_property("nanite_settings")
        ns.set_editor_property(
            "shape_preservation",
            unreal.ENaniteShapePreservation.VOXELIZE,
        )
        mesh.set_editor_property("nanite_settings", ns)
        return True
    except Exception as e:
        strategies.append(f"enum: {{e}}")

    # Strategy C: Type introspection -- read current value, construct enum(2)
    try:
        ns = mesh.get_editor_property("nanite_settings")
        cur = ns.get_editor_property("shape_preservation")
        enum_cls = type(cur)
        ns.set_editor_property("shape_preservation", enum_cls(2))
        mesh.set_editor_property("nanite_settings", ns)
        return True
    except Exception as e:
        strategies.append(f"introspect: {{e}}")

    # Strategy D: Qualified enum path string
    try:
        ns = mesh.get_editor_property("nanite_settings")
        ns.set_editor_property(
            "shape_preservation", "NaniteShapePreservation::Voxelize",
        )
        mesh.set_editor_property("nanite_settings", ns)
        return True
    except Exception as e:
        strategies.append(f"qualified: {{e}}")

    # Strategy E: Integer via set_editor_property
    try:
        ns = mesh.get_editor_property("nanite_settings")
        ns.set_editor_property("shape_preservation", 2)
        mesh.set_editor_property("nanite_settings", ns)
        return True
    except Exception as e:
        strategies.append(f"int: {{e}}")

    # Strategy F: Direct attribute assignment on struct copy
    try:
        ns = mesh.get_editor_property("nanite_settings")
        ns.shape_preservation = 2
        mesh.set_editor_property("nanite_settings", ns)
        return True
    except Exception as e:
        strategies.append(f"attr: {{e}}")

    # Strategy G: C++ getter/setter methods (StaticMesh only)
    try:
        ns = mesh.get_nanite_settings()
        ns.shape_preservation = 2
        mesh.set_nanite_settings(ns)
        mesh.notify_nanite_settings_changed()
        return True
    except Exception as e:
        strategies.append(f"methods: {{e}}")

    unreal.log_warning(f"Could not set shape preservation for {{label}}")
    for s in strategies:
        unreal.log_warning(f"    {{s}}")
    return False


def _rebuild_nanite(mesh, label):
    """Trigger a Nanite rebuild after changing settings.

    This is necessary because shape preservation changes only take effect
    after a rebuild. Uses modify(True) which queues a deferred build.
    """
    try:
        mesh.modify(True)
        return True
    except Exception as e:
        unreal.log_warning(f"[Voxelize] {{label}}: modify(True) failed: {{e}}")
    return False


def main():
    print("=" * 60)
    print("GrowPy Nanite Voxelize")
    print("=" * 60)

    # Find all assembly SkeletalMeshes
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    all_assets = registry.get_assets_by_path(IMPORT_PATH, recursive=True)

    assemblies = []
    for asset_data in all_assets:
        asset_name = str(asset_data.asset_name)
        asset_class = ""
        try:
            asset_class = str(asset_data.asset_class_path.asset_name)
        except Exception:
            try:
                asset_class = str(asset_data.asset_class)
            except Exception:
                pass
        if "SkeletalMesh" not in asset_class:
            continue
        if "assembly" not in asset_name.lower():
            continue
        pkg = str(asset_data.package_name)
        if "/Instances/" in pkg:
            continue
        assemblies.append((asset_name, pkg))

    assemblies.sort(key=lambda x: x[1])
    print(f"Found {{len(assemblies)}} assembly SkeletalMeshes")

    if not assemblies:
        print("Nothing to voxelize.")
        return

    # Load resume progress
    completed = set()
    if os.path.isfile(_PROGRESS_FILE):
        with open(_PROGRESS_FILE, "r") as f:
            completed = set(line.strip() for line in f if line.strip())
        if completed:
            print(f"Resuming: {{len(completed)}} already voxelized")
            print(f"Delete growpy_nanite_voxelize_done.txt to redo all\\n")

    applied = 0
    failed = 0
    skipped = 0

    for asset_name, pkg_path in assemblies:
        label = f"{{pkg_path}}.{{asset_name}}"

        if label in completed:
            skipped += 1
            continue

        mesh = unreal.EditorAssetLibrary.load_asset(pkg_path)
        if mesh is None or not isinstance(mesh, unreal.SkeletalMesh):
            unreal.log_warning(f"[Voxelize] Could not load: {{label}}")
            failed += 1
            continue

        ok = _set_nanite_shape_voxelize(mesh, asset_name)
        if ok:
            _rebuild_nanite(mesh, asset_name)
            try:
                unreal.EditorAssetLibrary.save_loaded_asset(mesh)
            except Exception:
                pass
            applied += 1
            # Record progress
            with open(_PROGRESS_FILE, "a") as f:
                f.write(label + "\\n")
            print(f"  [{{applied + skipped}}/{{len(assemblies)}}] {{asset_name}}: Voxelize set")
        else:
            failed += 1

        # Periodic GC to keep memory in check
        if (applied + failed) % 5 == 0:
            gc.collect()
            time.sleep(0.5)

    print("")
    print("=" * 60)
    print(
        f"Voxelize complete: {{applied}} applied, {{skipped}} skipped, "
        f"{{failed}} failed out of {{len(assemblies)}} total"
    )
    print("=" * 60)


main()
'''


def generate_nanite_voxelize_script(
    output_dir: Path,
    import_path: str = "/Game/Assets/TheGrove",
) -> Path:
    """Write a UE Python script that batch-sets Nanite Voxelize shape preservation.

    Args:
        output_dir: Where to write the .py script (typically ``unreal_scripts/``).
        import_path: UE Content Browser base path for tree assets.

    Returns:
        Path to the written script.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / "growpy_nanite_voxelize.py"

    body = _VOXELIZE_SCRIPT_BODY.format(
        script_path=str(script_path.resolve()).replace("\\", "/"),
        import_path=import_path,
    )

    script_path.write_text(body, encoding="utf-8")
    logger.info("Generated Nanite voxelize script: %s", script_path)
    return script_path
