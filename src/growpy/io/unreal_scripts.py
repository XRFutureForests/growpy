"""Unreal Engine import/cleanup script generation for exported forests.

Generates standalone Python scripts that can be executed inside Unreal Engine
to import USD tree assemblies and clean up previously imported assets.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def generate_unreal_import_script(
    output_dir: Path,
    project_path: str = "/Game/GrowPy/Trees",
    forest_data: Optional[pd.DataFrame] = None,
    export_tree_ids: Optional[set] = None,
) -> Path:
    """Generate a standalone Unreal Python script for importing forest USD files.

    Trees are organized as species/{variant}/ where variant is competition/open_grown
    or tree_{id}. Assembly USDs reference shared twig instances in ../Instances/.

    This script can be executed directly in Unreal Engine using:
    - VSCode Unreal Python extension (right-click > Execute in Unreal)
    - Unreal Editor Python console
    - Command line

    Args:
        output_dir: Directory containing exported USD files.
        project_path: Unreal project Content path.
        forest_data: Optional DataFrame with tree positions (fid, x, y, z columns).
        export_tree_ids: Optional set of tree IDs to include (if None, includes all).

    Returns:
        Path to generated script file.
    """
    script_dir = output_dir / "unreal_scripts"
    script_dir.mkdir(exist_ok=True)

    script_path = script_dir / "import_forest.py"

    # Find all tree assemblies in species subdirectories
    # Matches both species/competition/ and species/tree_XXXX/ patterns
    nanite_files = list(output_dir.glob("*/*/*_assembly*.usda")) + list(
        output_dir.glob("*/*/*_assembly*.usd")
    )
    # Exclude Instances/ and unreal_scripts/ directories
    skip_dirs = {"Instances", "unreal_scripts"}
    nanite_files = [
        f
        for f in nanite_files
        if f.relative_to(output_dir).parts[0] not in skip_dirs
    ]

    # Find shared twig instances
    instances_dir = output_dir / "Instances"
    instance_files = (
        list(instances_dir.glob("*.usda")) + list(instances_dir.glob("*.usd"))
        if instances_dir.exists()
        else []
    )

    # Group trees by species/variant (species_name -> variant_name -> files)
    trees_by_species: Dict[str, Dict[str, list]] = {}
    for usd_file in nanite_files:
        rel_parts = usd_file.relative_to(output_dir).parts
        species_name = rel_parts[0]
        variant_name = rel_parts[1] if len(rel_parts) > 2 else ""

        if species_name not in trees_by_species:
            trees_by_species[species_name] = {}
        if variant_name not in trees_by_species[species_name]:
            trees_by_species[species_name][variant_name] = []
        trees_by_species[species_name][variant_name].append(usd_file)

    num_species = len(trees_by_species)
    total_trees = len(nanite_files)
    num_instances = len(instance_files)

    # Build TREE_POSITIONS dictionary from forest_data if provided
    tree_positions_dict = {}
    if forest_data is not None:
        for _, row in forest_data.iterrows():
            fid = int(row["fid"])
            if export_tree_ids is not None and fid not in export_tree_ids:
                continue
            x = float(row["x"])
            y = float(row["y"])
            z = float(row.get("z", 0.0))
            species = row["species"]
            tree_key = f"{species}_{fid:04d}"
            tree_positions_dict[tree_key] = (x, y, z)

    # Format dictionary as Python code for the script
    tree_positions_code = "TREE_POSITIONS = {\n"
    for tree_key, (x, y, z) in sorted(tree_positions_dict.items()):
        tree_positions_code += f"    '{tree_key}': ({x}, {y}, {z}),\n"
    tree_positions_code += "}\n"

    script_path_str = str(script_path).replace("\\", "/")

    script_content = f'''"""
Unreal Engine script to import GrowPy forest - Auto-generated

Shared twig/foliage instances are imported once to Instances/ folder.
Tree assemblies reference shared instances via relative USD paths.

Execute this script in Unreal Engine:
1. Right-click this file in VSCode > "Execute Python File in Unreal"
2. Or from Unreal Python console: exec(open(r'{script_path_str}').read())
"""

import unreal
import gc
import time

print("=" * 60)
print("GrowPy Forest Import to Unreal Engine")
print("=" * 60)

# Import configuration
IMPORT_PATH = "{project_path}"

# Delay between imports to prevent crashes (seconds)
# Increase if you experience crashes
IMPORT_DELAY = 0.5

# Tree positions from CSV (in meters, multiply by 100 for Unreal units)
{tree_positions_code}

print(f"Destination: {{IMPORT_PATH}}")
print(f"Found {num_species} species with {total_trees} trees, {num_instances} shared instances\\n")

# Get asset tools
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

imported_count = 0
failed_count = 0

'''

    # Generate import code for shared instances first
    if instance_files:
        script_content += f"""
# === SHARED INSTANCES ({len(instance_files)} twig/foliage files) ===
print("Importing shared twig/foliage instances...")
"""
        for inst_file in sorted(instance_files):
            inst_path = str(inst_file.resolve()).replace("\\", "/")
            inst_name = inst_file.stem

            script_content += f"""
try:
    import_task = unreal.AssetImportTask()
    import_task.filename = "{inst_path}"
    import_task.destination_path = IMPORT_PATH + "/Instances"
    import_task.automated = True
    import_task.save = True
    import_task.replace_existing = True

    options = unreal.UsdStageImportOptions()
    options.import_actors = False
    options.import_geometry = True
    options.import_materials = True
    options.set_editor_property('prim_path_folder_structure', False)
    options.set_editor_property('share_assets_for_identical_prims', True)
    options.set_editor_property('merge_identical_material_slots', True)
    import_task.options = options

    asset_tools.import_asset_tasks([import_task])

    if import_task.imported_object_paths:
        imported_count += 1
        print(f"  Imported instance: {inst_name}")
    else:
        failed_count += 1
        unreal.log_warning("Failed to import instance: {inst_name}")

    gc.collect()
    unreal.SystemLibrary.collect_garbage()
    time.sleep(IMPORT_DELAY)

except Exception as e:
    failed_count += 1
    unreal.log_error(f"Error importing instance {inst_name}: {{e}}")
"""

    # Generate import code for each species
    for species_folder, variants in sorted(trees_by_species.items()):
        total_species_trees = sum(len(v) for v in variants.values())
        script_content += f"""
# --- {species_folder} ({total_species_trees} trees) ---
print("Importing {species_folder}...")
"""

        for variant_name, variant_trees in sorted(variants.items()):
            for usd_file in sorted(variant_trees):
                usd_path = str(usd_file.resolve()).replace("\\", "/")
                file_label = usd_file.stem
                dest_subpath = f"{species_folder}/{variant_name}" if variant_name else species_folder

                script_content += f"""
try:
    import_task = unreal.AssetImportTask()
    import_task.filename = "{usd_path}"
    import_task.destination_path = IMPORT_PATH + "/{dest_subpath}"
    import_task.automated = True
    import_task.save = True
    import_task.replace_existing = True

    options = unreal.UsdStageImportOptions()
    options.import_actors = False
    options.import_geometry = True
    options.import_materials = True
    options.set_editor_property('prim_path_folder_structure', False)
    options.set_editor_property('share_assets_for_identical_prims', True)
    options.set_editor_property('merge_identical_material_slots', True)
    import_task.options = options

    asset_tools.import_asset_tasks([import_task])

    if import_task.imported_object_paths:
        imported_count += 1
        print(f"  Imported: {file_label}")
    else:
        failed_count += 1
        unreal.log_warning("Failed to import: {file_label}")

    gc.collect()
    unreal.SystemLibrary.collect_garbage()
    time.sleep(IMPORT_DELAY)

except Exception as e:
    failed_count += 1
    unreal.log_error(f"Error importing {file_label}: {{e}}")
"""

    script_content += """

print("")
print("=" * 60)
print(f"Import complete: {imported_count} imported, {failed_count} failed")
print("=" * 60)

if failed_count > 0:
    unreal.log_warning("Some imports failed. Check that USD Importer plugin is enabled.")
else:
    print(f"\\nAssets imported to Content Browser: {IMPORT_PATH}")
    print("Structure: Instances/ (shared twigs) + species/variant/ (tree assemblies)")
    print("")
    print("=" * 60)
    print("TREE PLACEMENT")
    print("=" * 60)
    print("Trees are exported at origin (0,0,0)")
    print("Use TREE_POSITIONS dictionary to place trees at their CSV coordinates")
    print("")
    print("Example placement code:")
    print("  # Get tree mesh from Content Browser")
    print("  tree_asset = unreal.EditorAssetLibrary.load_asset(IMPORT_PATH + '/species/tree_0001/SK_species_stems')")
    print("  # Get position for this tree")
    print("  pos = TREE_POSITIONS.get('species_0001', (0,0,0))")
    print("  # Place in level")
    print("  actor = unreal.EditorLevelLibrary.spawn_actor_from_object(tree_asset, unreal.Vector(pos[0]*100, pos[1]*100, pos[2]*100))")
    print("")
    print(f"Available tree positions: {len(TREE_POSITIONS)}")
"""

    script_path.write_text(script_content, encoding="utf-8")
    return script_path


def generate_unreal_cleanup_script(
    output_dir: Path,
    project_path: str = "/Game/GrowPy/Trees",
    dry_run: bool = True,
) -> Path:
    """Generate a standalone Unreal Python script for cleaning GrowPy assets.

    Args:
        output_dir: Directory to save cleanup script (same as import script).
        project_path: Unreal project Content path to clean.
        dry_run: If True, generates preview-only script.

    Returns:
        Path to generated script file.
    """
    script_dir = output_dir / "unreal_scripts"
    script_dir.mkdir(exist_ok=True)

    script_path = script_dir / "clean_assets.py"
    script_path_str = str(script_path).replace("\\", "/")

    script_content = f'''"""
Unreal Engine cleanup script for GrowPy assets - Auto-generated

Execute this script in Unreal Engine:
1. Right-click this file in VSCode > "Execute Python File in Unreal"
2. Or from Unreal Python console: exec(open(r'{script_path_str}').read())
"""

import unreal

print("=" * 60)
print("GrowPy Asset Cleanup")
print("=" * 60)

# Cleanup configuration
CLEANUP_PATH = "{project_path}"
DRY_RUN = {str(dry_run)}

print(f"Target path: {{CLEANUP_PATH}} (including all subfolders)")

if DRY_RUN:
    print("\\n*** DRY RUN MODE - No assets will be deleted ***\\n")
else:
    print("\\n*** LIVE MODE - Assets will be permanently deleted ***\\n")

# Get asset registry
asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()

# Find all assets in target path (recursive to include species subfolders)
assets = asset_registry.get_assets_by_path(CLEANUP_PATH, recursive=True)

if not assets:
    print(f"No assets found at {{CLEANUP_PATH}}")
else:
    print(f"Found {{len(assets)}} assets at {{CLEANUP_PATH}}\\n")

    if DRY_RUN:
        # Dry run - just list assets
        print("Assets that would be deleted:\\n")
        for asset in assets:
            asset_path = str(asset.package_name)
            asset_name = str(asset.asset_name)
            asset_class = str(asset.asset_class_path.asset_name)

            print(f"  {{asset_class}}: {{asset_name}}")
            print(f"    Path: {{asset_path}}")

        print("\\n" + "=" * 60)
        print("DRY RUN COMPLETE")
        print("=" * 60)
        print("Set DRY_RUN = False in script to perform actual deletion")

    else:
        # Real cleanup - delete assets
        print("Deleting assets...\\n")
        deleted_count = 0
        failed_count = 0

        for asset in assets:
            asset_path = str(asset.package_name)
            asset_name = str(asset.asset_name)

            try:
                if unreal.EditorAssetLibrary.delete_asset(asset_path):
                    deleted_count += 1
                    unreal.log(f"Deleted {{asset_name}}")
                else:
                    failed_count += 1
                    unreal.log_warning(f"Failed to delete: {{asset_name}}")
            except Exception as e:
                failed_count += 1
                unreal.log_error(f"Error deleting {{asset_name}}: {{e}}")

        print("")
        print("=" * 60)
        print(f"Cleanup complete: {{deleted_count}} deleted, {{failed_count}} failed")
        print("=" * 60)

        if failed_count > 0:
            unreal.log_warning("Some assets could not be deleted. They may be in use.")
        else:
            print(f"\\nAll assets removed from: {{CLEANUP_PATH}}")

            # Try to delete empty folder after assets are removed
            try:
                if unreal.EditorAssetLibrary.does_directory_exist(CLEANUP_PATH):
                    # Check if directory is empty
                    remaining = asset_registry.get_assets_by_path(CLEANUP_PATH, recursive=True)
                    if not remaining:
                        if unreal.EditorAssetLibrary.delete_directory(CLEANUP_PATH):
                            print(f"[OK] Removed empty directory: {{CLEANUP_PATH}}")
                        else:
                            unreal.log_warning(f"Could not remove directory: {{CLEANUP_PATH}}")
            except Exception as e:
                unreal.log_warning(f"Error removing directory: {{e}}")
'''

    script_path.write_text(script_content, encoding="utf-8")
    return script_path
