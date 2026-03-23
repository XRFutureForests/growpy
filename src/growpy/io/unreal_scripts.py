"""Unreal Engine import/cleanup script generation for exported forests.

Generates standalone Python scripts that can be executed inside Unreal Engine
to import USD tree assemblies and clean up previously imported assets.

Imports are split into per-species batch scripts to avoid video memory crashes.
A master script orchestrates running batches sequentially.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def _build_import_block(file_path: str, dest_path: str, label: str) -> str:
    """Build a single USD import try/except block."""
    return f"""
try:
    import_task = unreal.AssetImportTask()
    import_task.filename = "{file_path}"
    import_task.destination_path = IMPORT_PATH + "/{dest_path}"
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
        print(f"  Imported: {label}")
    else:
        failed_count += 1
        unreal.log_warning("Failed to import: {label}")

    gc.collect()
    unreal.SystemLibrary.collect_garbage()
    time.sleep(IMPORT_DELAY)

except Exception as e:
    failed_count += 1
    unreal.log_error(f"Error importing {label}: {{e}}")
"""


def _write_batch_script(
    script_path: Path,
    project_path: str,
    batch_label: str,
    import_blocks: str,
    file_count: int,
) -> None:
    """Write a single batch import script."""
    script_path_str = str(script_path).replace("\\", "/")

    content = f'''"""
GrowPy batch import: {batch_label} ({file_count} files) - Auto-generated

Execute in Unreal Engine:
1. Right-click > "Execute Python File in Unreal"
2. Or: exec(open(r'{script_path_str}').read())
"""

import unreal
import gc
import time

print("=" * 60)
print("GrowPy Batch Import: {batch_label}")
print("=" * 60)

IMPORT_PATH = "{project_path}"
IMPORT_DELAY = 0.5

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
imported_count = 0
failed_count = 0

{import_blocks}

print("")
print("=" * 60)
print(f"Batch '{batch_label}' complete: {{imported_count}} imported, {{failed_count}} failed")
print("=" * 60)
'''

    script_path.write_text(content, encoding="utf-8")


def generate_unreal_import_script(
    output_dir: Path,
    project_path: str = "/Game/GrowPy/Trees",
    forest_data: Optional[pd.DataFrame] = None,
    export_tree_ids: Optional[set] = None,
    include_static: bool = False,
) -> Path:
    """Generate batched Unreal Python scripts for importing forest USD files.

    Produces one batch script per species (plus one for shared instances) to
    avoid video memory exhaustion. A master script runs each batch sequentially.

    Args:
        output_dir: Directory containing exported USD files.
        project_path: Unreal project Content path.
        forest_data: Optional DataFrame with tree positions (fid, x, y, z columns).
        export_tree_ids: Optional set of tree IDs to include (if None, includes all).
        include_static: If True, include static twig variants and static assemblies.
            Mirrors [export] static setting from growpy.toml.

    Returns:
        Path to generated master script file.
    """
    script_dir = output_dir / "unreal_scripts"
    script_dir.mkdir(exist_ok=True)

    # Find all tree assemblies in species subdirectories
    nanite_files = list(output_dir.glob("*/*/*_assembly*.usda")) + list(
        output_dir.glob("*/*/*_assembly*.usd")
    )
    skip_dirs = {"Instances", "unreal_scripts"}
    nanite_files = [
        f
        for f in nanite_files
        if f.relative_to(output_dir).parts[0] not in skip_dirs
    ]

    # Find shared twig instances — prefer combined per-species wrappers
    instances_dir = output_dir / "Instances"
    if instances_dir.exists():
        combined_files = sorted(
            instances_dir.glob("*_twigs_combined_*.usda")
        )
        # Extract species names covered by combined wrappers
        combined_species = set()
        for f in combined_files:
            # "{species}_twigs_combined_{skeletal|static}.usda"
            name = f.stem
            idx = name.find("_twigs_combined_")
            if idx > 0:
                combined_species.add(name[:idx])

        # Filter: skip static unless configured, skip files covered by combined
        individual_files = []
        for f in sorted(instances_dir.glob("*.usda")) + sorted(
            instances_dir.glob("*.usd")
        ):
            if "_twigs_combined_" in f.stem:
                continue
            if "_static" in f.stem and not include_static:
                continue
            # Extract species from individual twig filename
            stem = f.stem.replace("_skeletal", "").replace("_static", "")
            if "_foliage_" in stem:
                species_prefix = stem.split("_foliage_")[0]
            elif "_foliage" in stem:
                species_prefix = stem.split("_foliage")[0]
            else:
                species_prefix = None
            if species_prefix and species_prefix in combined_species:
                continue
            individual_files.append(f)

        instance_files = combined_files + individual_files
    else:
        instance_files = []

    # Group trees by species/variant
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

    # Build TREE_POSITIONS from forest_data
    tree_positions_dict: Dict[str, Tuple[float, float, float]] = {}
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

    # Track batch scripts: (filename, label)
    batch_scripts: List[Tuple[str, str]] = []

    # Batch 0: Shared instances
    if instance_files:
        blocks = ""
        blocks += 'print("Importing shared twig/foliage instances...")\n'
        for inst_file in sorted(instance_files):
            inst_path = str(inst_file.resolve()).replace("\\", "/")
            blocks += _build_import_block(inst_path, "Instances", inst_file.stem)

        batch_name = "import_batch_00_instances.py"
        batch_label = f"Shared instances ({num_instances} files)"
        _write_batch_script(
            script_dir / batch_name,
            project_path,
            batch_label,
            blocks,
            num_instances,
        )
        batch_scripts.append((batch_name, batch_label))

    # Batch per species
    for idx, (species_folder, variants) in enumerate(
        sorted(trees_by_species.items()), start=1
    ):
        species_tree_count = sum(len(v) for v in variants.values())
        blocks = ""
        blocks += f'print("Importing {species_folder}...")\n'

        for variant_name, variant_trees in sorted(variants.items()):
            for usd_file in sorted(variant_trees):
                usd_path = str(usd_file.resolve()).replace("\\", "/")
                dest_subpath = (
                    f"{species_folder}/{variant_name}"
                    if variant_name
                    else species_folder
                )
                blocks += _build_import_block(
                    usd_path, dest_subpath, usd_file.stem
                )

        batch_name = f"import_batch_{idx:02d}_{species_folder}.py"
        batch_label = f"{species_folder} ({species_tree_count} trees)"
        _write_batch_script(
            script_dir / batch_name,
            project_path,
            batch_label,
            blocks,
            species_tree_count,
        )
        batch_scripts.append((batch_name, batch_label))

    # Master script
    master_path = script_dir / "import_forest.py"
    master_path_str = str(master_path).replace("\\", "/")
    scripts_dir_str = str(script_dir.resolve()).replace("\\", "/")

    # Format tree positions
    tree_positions_code = "TREE_POSITIONS = {\n"
    for tree_key, (x, y, z) in sorted(tree_positions_dict.items()):
        tree_positions_code += f"    '{tree_key}': ({x}, {y}, {z}),\n"
    tree_positions_code += "}\n"

    # Build batch list for the master script
    batch_list_code = "BATCH_SCRIPTS = [\n"
    for batch_name, batch_label in batch_scripts:
        batch_list_code += f'    ("{batch_name}", "{batch_label}"),\n'
    batch_list_code += "]\n"

    master_content = f'''"""
GrowPy Forest Import to Unreal Engine - Auto-generated master script

Imports are split into {len(batch_scripts)} batches (1 per species + shared instances)
to avoid video memory exhaustion. Each batch triggers garbage collection
before moving to the next.

Execute this script in Unreal Engine:
1. Right-click this file in VSCode > "Execute Python File in Unreal"
2. Or from Unreal Python console: exec(open(r'{master_path_str}').read())

To import a single species, run the individual batch script instead:
  e.g. exec(open(r'{scripts_dir_str}/import_batch_01_species.py').read())
"""

import unreal
import os
import gc
import time

print("=" * 60)
print("GrowPy Forest Import to Unreal Engine")
print("=" * 60)

IMPORT_PATH = "{project_path}"
SCRIPTS_DIR = r"{scripts_dir_str}"

# Delay between batches (seconds) - increase if you still get VRAM crashes
BATCH_DELAY = 3.0

# Tree positions from CSV (in meters, multiply by 100 for Unreal units)
{tree_positions_code}

{batch_list_code}

print(f"Destination: {{IMPORT_PATH}}")
print(f"Found {num_species} species with {total_trees} trees, {num_instances} shared instances")
print(f"Split into {{len(BATCH_SCRIPTS)}} batches\\n")

total_imported = 0
total_failed = 0
batches_completed = 0

for batch_file, batch_label in BATCH_SCRIPTS:
    batch_path = os.path.join(SCRIPTS_DIR, batch_file).replace("\\\\", "/")
    print(f"\\n>>> Running batch {{batches_completed + 1}}/{{len(BATCH_SCRIPTS)}}: {{batch_label}}")

    try:
        exec(open(batch_path).read())
        batches_completed += 1
    except Exception as e:
        unreal.log_error(f"Batch '{{batch_label}}' failed: {{e}}")
        total_failed += 1

    # Aggressive cleanup between batches
    gc.collect()
    unreal.SystemLibrary.collect_garbage()
    time.sleep(BATCH_DELAY)

print("")
print("=" * 60)
print(f"All batches complete: {{batches_completed}}/{{len(BATCH_SCRIPTS)}} succeeded")
print("=" * 60)
print(f"\\nAssets imported to Content Browser: {{IMPORT_PATH}}")
print("Structure: Instances/ (shared twigs) + species/variant/ (tree assemblies)")
print("")
print("=" * 60)
print("TREE PLACEMENT")
print("=" * 60)
print("Trees are exported at origin (0,0,0)")
print("Use TREE_POSITIONS dictionary to place trees at their CSV coordinates")
print("")
print("Example placement code:")
print("  tree_asset = unreal.EditorAssetLibrary.load_asset(IMPORT_PATH + '/species/tree_0001/SK_species_stems')")
print("  pos = TREE_POSITIONS.get('species_0001', (0,0,0))")
print("  actor = unreal.EditorLevelLibrary.spawn_actor_from_object(tree_asset, unreal.Vector(pos[0]*100, pos[1]*100, pos[2]*100))")
print("")
print(f"Available tree positions: {{len(TREE_POSITIONS)}}")
'''

    master_path.write_text(master_content, encoding="utf-8")

    logger.info(
        "Generated %d batch import scripts + master script in %s",
        len(batch_scripts),
        script_dir,
    )
    return master_path


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
