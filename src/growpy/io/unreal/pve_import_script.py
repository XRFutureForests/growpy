"""
Generate UE Python scripts that create ProceduralVegetationPreset DataAssets
from growpy-emitted PVE JSON recipes.

EXPERIMENTAL — UE 5.7+ Procedural Vegetation Editor (PVE) plugin only.

The current production path exports skeletal-mesh USD assemblies that UE
imports directly. This module enables a complementary path: hand growpy's
PVE JSON recipes to PVE itself, which re-grows the tree inside UE using its
own simulation. Useful when you want PVE Graph nodes (Carve, Gravity,
Foliage Distributor, Bone Reduction) to act on growpy parameters.

Both paths can run from the same growpy export — they are not mutually
exclusive.

The runtime UE script walks the forest output directory recursively
because growpy writes per-tree PVE recipes at:

    data/output/forest/<species>/<scene>/<tree>/<file_prefix>_stems_unreal_pve.json

(see ``forest_stages.py``). One ``ProceduralVegetationPreset`` DataAsset is
created per recipe, named after the file basename with the
``_stems_unreal_pve.json`` suffix stripped.

UE Python API used (UE 5.7+, Experimental):
- unreal.ProceduralVegetationFactory   - DataAsset factory
- unreal.ProceduralVegetationPreset    - DataAsset holding JSON path + folders
- unreal.AssetToolsHelpers             - asset creation entry point
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


PVE_RECIPE_SUFFIX = "_stems_unreal_pve.json"


_PVE_PREAMBLE = '''"""
GrowPy PVE preset import - Auto-generated.

Walks FOREST_ROOT recursively for ``*{suffix}`` recipe files
and creates one ProceduralVegetationPreset DataAsset per recipe under
PVE_PACKAGE_PATH. Each preset's json_directory_path is set to the recipe's
own parent directory so PVE picks up the right per-tree parameters.

Execute in Unreal Engine:
1. Right-click > "Execute Python File in Unreal"
2. Or: exec(open(r"{script_path}").read())

Requires the Procedural Vegetation Editor plugin to be enabled.
"""

import json
import os
import unreal


PVE_RECIPE_SUFFIX = "{suffix}"


def _have_pve_classes():
    return all(
        hasattr(unreal, _name) for _name in (
            "ProceduralVegetationFactory",
            "ProceduralVegetationPreset",
        )
    )


def _make_directory_path(path_str):
    """Build an unreal.DirectoryPath struct, tolerating constructor variants."""
    try:
        _dp = unreal.DirectoryPath()
        _dp.path = path_str
        return _dp
    except Exception:
        pass
    try:
        return unreal.DirectoryPath(path=path_str)
    except Exception as _e:
        unreal.log_warning(
            "[PVE] DirectoryPath construction failed for %s: %s" % (path_str, _e)
        )
        return None


def _ensure_foliage_data(json_dir):
    """Create minimal FoliageData.json if absent (required by UpdateDataAsset)."""
    foliage_path = os.path.join(json_dir, "FoliageData.json")
    if not os.path.exists(foliage_path):
        with open(foliage_path, "w") as f:
            json.dump({{"Variations": []}}, f)
        unreal.log("[PVE] Created FoliageData.json in %s" % json_dir)


def _create_pve_preset(asset_name, package_path, json_dir,
                       plant_profile_name, foliage_folder, materials_folder,
                       trunk_material_name=""):
    """Create one ProceduralVegetationPreset DataAsset.

    Returns the created asset or None on failure.
    """
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

    # If asset already exists, re-trigger data loading.
    full_path = "%s/%s" % (package_path, asset_name)
    if unreal.EditorAssetLibrary.does_asset_exist(full_path):
        unreal.log("[PVE] Refreshing existing asset: %s" % full_path)
        asset = unreal.EditorAssetLibrary.load_asset(full_path)
        if asset is not None:
            try:
                asset.call_method('UpdateDataAsset')
                unreal.EditorAssetLibrary.save_loaded_asset(asset)
            except Exception as _e:
                unreal.log_warning(
                    "[PVE] UpdateDataAsset failed on existing %s: %s"
                    % (full_path, _e)
                )
        return asset

    try:
        # factory=None lets UE auto-select the correct factory.
        # ProceduralVegetationFactory.supported_class is ProceduralVegetation
        # (the graph), not ProceduralVegetationPreset (the DataAsset).
        asset = asset_tools.create_asset(
            asset_name=asset_name,
            package_path=package_path,
            asset_class=unreal.ProceduralVegetationPreset,
            factory=None,
        )
    except Exception as _e:
        unreal.log_warning(
            "[PVE] create_asset failed for %s: %s" % (asset_name, _e)
        )
        return None

    if asset is None:
        unreal.log_warning("[PVE] create_asset returned None for %s" % asset_name)
        return None

    _dp = _make_directory_path(json_dir)
    if _dp is not None:
        try:
            asset.set_editor_property("json_directory_path", _dp)
        except Exception as _e:
            unreal.log_warning("[PVE] json_directory_path set failed: %s" % _e)

    try:
        asset.set_editor_property("override_folder_paths", True)
        _ff = _make_directory_path(foliage_folder)
        if _ff is not None:
            asset.set_editor_property("foliage_folder", _ff)
        _mf = _make_directory_path(materials_folder)
        if _mf is not None:
            asset.set_editor_property("materials_folder", _mf)
    except Exception as _e:
        unreal.log_warning("[PVE] folder path set failed: %s" % _e)

    try:
        asset.set_editor_property("plant_profile_name", plant_profile_name)
        if trunk_material_name:
            asset.set_editor_property(
                "trunk_material_name", trunk_material_name
            )
        asset.set_editor_property("create_profile_data_asset", True)
    except Exception as _e:
        unreal.log_warning("[PVE] profile property set failed: %s" % _e)

    unreal.EditorAssetLibrary.save_loaded_asset(asset)

    # Load JSON data into the Variants TMap.
    try:
        asset.call_method('UpdateDataAsset')
        unreal.EditorAssetLibrary.save_loaded_asset(asset)
        unreal.log("[PVE] Loaded variant data for %s" % asset_name)
    except Exception as _e:
        unreal.log_warning(
            "[PVE] UpdateDataAsset failed for %s: %s" % (asset_name, _e)
        )

    return asset


def main():
    if not _have_pve_classes():
        unreal.log_error(
            "[PVE] Procedural Vegetation Editor plugin not enabled or "
            "UE version < 5.7. Aborting."
        )
        return

    if not os.path.isdir(FOREST_ROOT):
        unreal.log_error("[PVE] Forest root does not exist: %s" % FOREST_ROOT)
        return

    recipes = []
    for dirpath, _dirnames, filenames in os.walk(FOREST_ROOT):
        for fname in filenames:
            if fname.endswith(PVE_RECIPE_SUFFIX):
                recipes.append(os.path.join(dirpath, fname))
    recipes.sort()

    if not recipes:
        unreal.log_warning(
            "[PVE] No *%s files found under %s" % (PVE_RECIPE_SUFFIX, FOREST_ROOT)
        )
        return

    unreal.log("[PVE] Found %d PVE recipe(s) under %s" % (len(recipes), FOREST_ROOT))
    # Ensure FoliageData.json in each unique recipe directory.
    seen_dirs = set()
    for recipe_path in recipes:
        d = os.path.dirname(recipe_path).replace("\\\\", "/")
        if d not in seen_dirs:
            _ensure_foliage_data(d)
            seen_dirs.add(d)
    created = 0
    for recipe_path in recipes:
        json_dir = os.path.dirname(recipe_path).replace("\\\\", "/")
        basename = os.path.basename(recipe_path)
        stem = basename[: -len(PVE_RECIPE_SUFFIX)]
        asset_name = "PVE_" + stem
        unreal.log("[PVE] Creating %s from %s" % (asset_name, recipe_path))
        _create_pve_preset(
            asset_name=asset_name,
            package_path=PVE_PACKAGE_PATH,
            json_dir=json_dir,
            plant_profile_name=stem,
            foliage_folder=FOLIAGE_FOLDER,
            materials_folder=MATERIALS_FOLDER,
            trunk_material_name=TRUNK_MATERIAL_NAME,
        )
        created += 1

    unreal.log(
        "[PVE] Created/refreshed %d preset(s) under %s"
        % (created, PVE_PACKAGE_PATH)
    )


main()
'''


def generate_pve_preset_import_script(
    output_dir: Path,
    forest_root: Path,
    package_path: str = "/Game/Assets/TheGrove/PVE",
    foliage_folder: str = "/Game/Assets/TheGrove/PVE/Foliage",
    materials_folder: str = "/Game/Assets/TheGrove/PVE/Materials",
    trunk_material_name: str = "",
) -> Path:
    """Write a UE Python script that creates ProceduralVegetationPreset assets.

    The generated script walks ``forest_root`` recursively at runtime
    (inside UE) for ``*_stems_unreal_pve.json`` recipe files written by
    growpy's per-tree exports, so the same script works for any forest
    output without regenerating it.

    Args:
        output_dir: Where to write the .py script (typically the same
            ``unreal_scripts/`` folder as ``unreal_import_trees.py``).
        forest_root: Root of the growpy forest export. Must be an absolute
            path that UE can read; the script walks this folder recursively
            for per-tree PVE recipes.
        package_path: UE Content Browser path for new preset assets.
        foliage_folder: UE Content Browser path for PVE-generated foliage.
        materials_folder: UE Content Browser path for PVE-generated materials.
        trunk_material_name: Optional trunk material override.

    Returns:
        Path to the written script.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / "growpy_pve_preset_import.py"

    # Resolve to absolute, forward-slash path for UE consumption.
    forest_root_str = str(forest_root.resolve()).replace("\\", "/")

    header = (
        f'FOREST_ROOT = r"{forest_root_str}"\n'
        f'PVE_PACKAGE_PATH = "{package_path}"\n'
        f'FOLIAGE_FOLDER = "{foliage_folder}"\n'
        f'MATERIALS_FOLDER = "{materials_folder}"\n'
        f'TRUNK_MATERIAL_NAME = "{trunk_material_name}"\n\n'
    )

    body = _PVE_PREAMBLE.format(
        script_path=str(script_path).replace("\\", "/"),
        suffix=PVE_RECIPE_SUFFIX,
    )

    script_path.write_text(header + body, encoding="utf-8")
    logger.info("Generated PVE preset import script: %s", script_path)
    return script_path


def generate_pve_import_for_species(
    output_dir: Path,
    pve_json_paths: Iterable[Path],
    package_path: str = "/Game/Assets/TheGrove/PVE",
    foliage_folder: Optional[str] = None,
    materials_folder: Optional[str] = None,
) -> Optional[Path]:
    """Convenience: derive forest_root from a list of per-tree JSON paths.

    Picks the common ancestor directory of the supplied paths and forwards
    it to ``generate_pve_preset_import_script``. Useful when callers already
    have the recipe list materialised; otherwise call the main helper with
    the forest output directory directly.
    """
    paths = list(pve_json_paths)
    if not paths:
        return None
    abs_paths = [p.resolve() for p in paths]
    common = Path(os.path.commonpath([str(p) for p in abs_paths]))
    return generate_pve_preset_import_script(
        output_dir=output_dir,
        forest_root=common,
        package_path=package_path,
        foliage_folder=foliage_folder or f"{package_path}/Foliage",
        materials_folder=materials_folder or f"{package_path}/Materials",
    )
