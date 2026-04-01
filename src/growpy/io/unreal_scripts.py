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


def _build_import_block(
    file_path: str,
    dest_path: str,
    label: str,
    wind_json_path: str = "",
    configure_nanite: bool = False,
) -> str:
    """Build a single USD import try/except block.

    When configure_nanite is True (for assembly imports), the block also
    configures the imported nanite assembly: Nanite shape preservation is set
    to Voxelize, DynamicWind data is imported from the JSON file (if present),
    and a default DynamicWindTransformProviderData is assigned.
    """
    config_block = ""
    if configure_nanite:
        wind_arg = f'r"{wind_json_path}"' if wind_json_path else '""'
        config_block = f"""
    # Post-import: configure nanite assembly
    for _obj_path in (import_task.imported_object_paths or []):
        _obj_path_str = str(_obj_path)
        if "nanite_assembly" not in _obj_path_str.lower():
            continue
        _mesh = unreal.EditorAssetLibrary.load_asset(_obj_path_str)
        if not _mesh:
            continue
        _configure_nanite_assembly(_mesh, {wind_arg}, "{label}")
        break
"""

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
{config_block}
    # Wait for async Nanite compilation to finish before unloading
    try:
        unreal.AssetCompilingManager.get_default().finish_all_compilation()
    except Exception:
        pass

    # Unload imported assets from editor memory (already saved to disk)
    for _unload_path in (import_task.imported_object_paths or []):
        try:
            unreal.EditorAssetLibrary.unload_asset(str(_unload_path))
        except Exception:
            pass

    del import_task

    # Flush pending async loads so GC can actually free everything
    try:
        unreal.SystemLibrary.flush_async_loading()
    except Exception:
        pass

    # Flush GPU rendering commands and release pooled VRAM
    try:
        _w = unreal.EditorLevelLibrary.get_editor_world()
        for _cmd in ("FlushRenderingCommands", "r.Streaming.FlushAll"):
            try:
                unreal.KismetSystemLibrary.execute_console_command(_w, _cmd)
            except Exception:
                pass
    except Exception:
        pass

    gc.collect()
    try:
        unreal.SystemLibrary.collect_garbage(full_purge=True)
    except Exception:
        unreal.SystemLibrary.collect_garbage()
    time.sleep(IMPORT_DELAY)

except Exception as e:
    failed_count += 1
    unreal.log_error(f"Error importing {label}: {{e}}")
"""


def _build_consolidation_script(project_path: str) -> str:
    """Build Unreal Python code that consolidates duplicate twig assets.

    When Unreal imports tree assembly USDAs, it follows external references to
    twig files and re-imports them into each tree's local folder — even though
    batch 0 already imported the shared copies into Instances/.  This script
    finds those local duplicates, redirects all references to the shared
    Instances version via consolidate_assets(), and deletes the leftovers.
    """
    return f'''
import unreal
import gc

print("")
print("=" * 60)
print("GrowPy Post-Import: Consolidate Duplicate Twig Assets")
print("=" * 60)

IMPORT_PATH = "{project_path}"
INSTANCES_PATH = IMPORT_PATH + "/Instances"

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

# Step 1: Build lookup of canonical foliage assets in Instances/
instances_assets = asset_registry.get_assets_by_path(INSTANCES_PATH, recursive=True)
canonical = {{}}  # asset_name -> asset_path
for asset in instances_assets:
    name = str(asset.asset_name)
    if "_foliage" in name.lower():
        canonical[name] = str(asset.package_name)

print(f"Found {{len(canonical)}} canonical foliage assets in Instances/")

if not canonical:
    print("No shared foliage assets found — skipping consolidation")
else:
    # Step 2: Find duplicates in tree subfolders
    all_assets = asset_registry.get_assets_by_path(IMPORT_PATH, recursive=True)
    duplicates = []  # (duplicate_path, canonical_path)
    for asset in all_assets:
        asset_path = str(asset.package_name)
        # Skip assets already in Instances/
        if asset_path.startswith(INSTANCES_PATH):
            continue
        name = str(asset.asset_name)
        if name in canonical:
            duplicates.append((asset_path, canonical[name]))

    print(f"Found {{len(duplicates)}} duplicate foliage assets in tree folders")

    # Step 3: Consolidate duplicates to canonical versions (one pair at a time)
    consolidated = 0
    failed = 0
    for _ci, (dup_path, canon_path) in enumerate(duplicates):
        try:
            dup_obj = unreal.EditorAssetLibrary.load_asset(dup_path)
            canon_obj = unreal.EditorAssetLibrary.load_asset(canon_path)
            if dup_obj and canon_obj:
                result = unreal.EditorAssetLibrary.consolidate_assets(
                    canon_obj, [dup_obj]
                )
                if result:
                    consolidated += 1
                else:
                    # consolidate_assets returns True on success
                    # If False, try direct delete (asset may not have references)
                    if unreal.EditorAssetLibrary.delete_asset(dup_path):
                        consolidated += 1
                    else:
                        failed += 1
            else:
                failed += 1
        except Exception as e:
            # Fallback: try direct deletion if consolidation not supported
            try:
                if unreal.EditorAssetLibrary.delete_asset(dup_path):
                    consolidated += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        # Unload both assets after each pair to prevent memory accumulation
        for _unload in (dup_path, canon_path):
            try:
                unreal.EditorAssetLibrary.unload_asset(_unload)
            except Exception:
                pass

        # Periodic full GC every 5 pairs
        if (_ci + 1) % 5 == 0:
            gc.collect()
            try:
                unreal.SystemLibrary.collect_garbage(full_purge=True)
            except Exception:
                unreal.SystemLibrary.collect_garbage()

    print(f"Consolidated {{consolidated}} assets, {{failed}} failures")

    gc.collect()
    try:
        unreal.SystemLibrary.collect_garbage(full_purge=True)
    except Exception:
        unreal.SystemLibrary.collect_garbage()

print("")
print("=" * 60)
print("Twig consolidation complete")
print("=" * 60)
'''


# Unreal Python preamble for configuring nanite assemblies after import.
# Included in species batch scripts to set shape preservation, wind data, etc.
_NANITE_CONFIG_PREAMBLE = '''
import os

def _configure_nanite_assembly(mesh, wind_json_path, label):
    """Configure a nanite assembly after USD import.

    Sets Nanite shape preservation to Voxelize, imports DynamicWind data,
    and assigns DynamicWindTransformProviderData.
    """
    # 1. Nanite Shape Preservation -> Voxelize
    #    Preserves foliage volume at distance (prevents thin-out)
    try:
        _nanite = mesh.get_editor_property("nanite_settings")
        # ENaniteShapePreservation: NONE=0, PRESERVE_AREA=1, VOXELIZE=2
        _nanite.set_editor_property(
            "shape_preservation",
            unreal.ENaniteShapePreservation.VOXELIZE,
        )
        mesh.set_editor_property("nanite_settings", _nanite)
        print(f"    [Nanite] Shape preservation -> Voxelize: {label}")
    except Exception as e:
        unreal.log_warning(f"Could not set shape preservation for {label}: {e}")

    # 2. Import DynamicWind JSON data
    #    Maps skeleton joints to wind simulation groups
    if wind_json_path and os.path.isfile(wind_json_path):
        try:
            # UE 5.5+ DynamicWind plugin function library
            unreal.DynamicWindSkeletalMeshFunctionLibrary.import_dynamic_wind_skeletal_data_from_file(
                mesh, wind_json_path
            )
            print(f"    [Wind] Imported wind data: {label}")
        except AttributeError:
            try:
                # Alternative API path (plugin version dependent)
                unreal.DynamicWindSkeletalMeshHelpers.import_dynamic_wind_skeletal_data_from_file(
                    mesh, wind_json_path
                )
                print(f"    [Wind] Imported wind data: {label}")
            except Exception as e2:
                unreal.log_warning(
                    f"Could not import wind data for {label}: {e2}\\n"
                    f"  Use right-click > Scripted Asset Actions > Import Dynamic Wind Data"
                )

    # 3. Assign default DynamicWindTransformProviderData
    #    Enables runtime wind transforms on the skeletal mesh
    #    See: https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-foliage
    try:
        _provider = unreal.DynamicWindTransformProviderData()
        mesh.set_editor_property(
            "default_dynamic_wind_transform_provider_data", _provider
        )
        print(f"    [Wind] Set transform provider data: {label}")
    except Exception as e:
        unreal.log_warning(
            f"Could not set wind transform provider for {label}: {e}\\n"
            f"  Set manually: Skeletal Mesh > Details > Dynamic Wind Transform Provider Data"
        )

    # Save the modified asset
    try:
        mesh.modify(True)
    except Exception:
        pass
'''


def _write_batch_script(
    script_path: Path,
    project_path: str,
    batch_label: str,
    import_blocks: str,
    file_count: int,
    include_nanite_config: bool = False,
) -> None:
    """Write a single batch import script."""
    script_path_str = str(script_path).replace("\\", "/")
    preamble = _NANITE_CONFIG_PREAMBLE if include_nanite_config else ""

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
IMPORT_DELAY = 3.0

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
imported_count = 0
failed_count = 0
{preamble}
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

    # Find all tree assemblies in species subdirectories (usda, usdc, or usd)
    nanite_files = (
        list(output_dir.glob("*/*/*_assembly*.usda"))
        + list(output_dir.glob("*/*/*_assembly*.usdc"))
        + list(output_dir.glob("*/*/*_assembly*.usd"))
    )
    skip_dirs = {"Instances", "unreal_scripts"}
    # Minimum file size for valid USDC with geometry (empty stubs are ~1 KB)
    MIN_ASSEMBLY_BYTES = 2048
    nanite_files_raw = [
        f
        for f in nanite_files
        if f.relative_to(output_dir).parts[0] not in skip_dirs
    ]
    nanite_files = []
    for f in nanite_files_raw:
        if f.stat().st_size < MIN_ASSEMBLY_BYTES:
            logger.warning(
                "Skipping empty/stub assembly %s (%d bytes)",
                f.name, f.stat().st_size,
            )
        else:
            nanite_files.append(f)

    # Find shared twig instances — prefer combined per-species wrappers
    instances_dir = output_dir / "Instances"
    if instances_dir.exists():
        combined_files = sorted(
            list(instances_dir.glob("*_twigs_combined_*.usda"))
            + list(instances_dir.glob("*_twigs_combined_*.usdc"))
        )
        # Extract species names covered by combined wrappers
        combined_species = set()
        for f in combined_files:
            # "{species}_twigs_combined_{skeletal|static}.{usda|usdc}"
            name = f.stem
            idx = name.find("_twigs_combined_")
            if idx > 0:
                combined_species.add(name[:idx])

        # Filter: skip static unless configured, skip files covered by combined
        individual_files = []
        for f in (
            sorted(instances_dir.glob("*.usda"))
            + sorted(instances_dir.glob("*.usdc"))
            + sorted(instances_dir.glob("*.usd"))
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

        has_assemblies = False
        for variant_name, variant_trees in sorted(variants.items()):
            for usd_file in sorted(variant_trees):
                usd_path = str(usd_file.resolve()).replace("\\", "/")
                dest_subpath = (
                    f"{species_folder}/{variant_name}"
                    if variant_name
                    else species_folder
                )

                is_assembly = "_assembly" in usd_file.stem
                wind_json = ""
                if is_assembly:
                    has_assemblies = True
                    wind_files = sorted(usd_file.parent.glob("*_stems_unreal_wind.json"))
                    if wind_files:
                        wind_json = str(wind_files[0].resolve()).replace("\\", "/")

                blocks += _build_import_block(
                    usd_path, dest_subpath, usd_file.stem,
                    wind_json_path=wind_json,
                    configure_nanite=is_assembly,
                )

        batch_name = f"import_batch_{idx:02d}_{species_folder}.py"
        batch_label = f"{species_folder} ({species_tree_count} trees)"
        _write_batch_script(
            script_dir / batch_name,
            project_path,
            batch_label,
            blocks,
            species_tree_count,
            include_nanite_config=has_assemblies,
        )
        batch_scripts.append((batch_name, batch_label))

    # Final batch: consolidate duplicate twig assets
    if instance_files:
        consolidation_code = _build_consolidation_script(project_path)
        consolidation_name = "import_batch_99_consolidate.py"
        consolidation_label = "Consolidate duplicate twig assets"
        consolidation_path = script_dir / consolidation_name
        consolidation_path.write_text(consolidation_code, encoding="utf-8")
        batch_scripts.append((consolidation_name, consolidation_label))

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
BATCH_DELAY = 5.0

# --- VRAM management: reduce GPU memory pressure during import ---
# Cap texture streaming pool to 256 MB (default ~1024 MB) to leave room for Nanite
_STREAMING_POOL_MB = 256
try:
    _world = unreal.EditorLevelLibrary.get_editor_world()
    unreal.KismetSystemLibrary.execute_console_command(
        _world, f"r.Streaming.PoolSize {{_STREAMING_POOL_MB}}"
    )
    print(f"Texture streaming pool capped to {{_STREAMING_POOL_MB}} MB")
except Exception:
    pass

print("")
print("VRAM tips -- if import still crashes:")
print("  1. Press Ctrl+R in viewport to disable Realtime rendering")
print("  2. Close the Content Browser (prevents thumbnail generation)")
print("  3. Close other GPU-heavy apps (browser tabs, etc.)")
print("  4. Increase BATCH_DELAY above (currently {{BATCH_DELAY}}s)")
print("")

# Tree positions from CSV (in meters, multiply by 100 for Unreal units)
{tree_positions_code}

{batch_list_code}

print(f"Destination: {{IMPORT_PATH}}")
print(f"Found {num_species} species with {total_trees} trees, {num_instances} shared instances")
print(f"Split into {{len(BATCH_SCRIPTS)}} batches\\n")

# Resume support: skip already-completed batches after a crash
PROGRESS_FILE = os.path.join(SCRIPTS_DIR, "_import_progress.txt")
_resume_from = 0
if os.path.isfile(PROGRESS_FILE):
    try:
        _resume_from = int(open(PROGRESS_FILE).read().strip()) + 1
        print(f"Resuming from batch {{_resume_from + 1}} ({{_resume_from}} already completed)")
        print("Delete _import_progress.txt to restart from scratch\\n")
    except Exception:
        _resume_from = 0

total_imported = 0
total_failed = 0
batches_completed = _resume_from

for _batch_idx, (batch_file, batch_label) in enumerate(BATCH_SCRIPTS):
    if _batch_idx < _resume_from:
        continue

    batch_path = os.path.join(SCRIPTS_DIR, batch_file).replace("\\\\", "/")
    print(f"\\n>>> Running batch {{_batch_idx + 1}}/{{len(BATCH_SCRIPTS)}}: {{batch_label}}")

    try:
        # Execute in isolated namespace so batch-local variables get freed
        _batch_ns = {{"__builtins__": __builtins__}}
        exec(open(batch_path).read(), _batch_ns)
        del _batch_ns
        batches_completed += 1

        # Record progress so we can resume after a crash
        with open(PROGRESS_FILE, "w") as _pf:
            _pf.write(str(_batch_idx))
    except Exception as e:
        unreal.log_error(f"Batch '{{batch_label}}' failed: {{e}}")
        total_failed += 1

    # Aggressive cleanup between batches (CPU + GPU)
    try:
        unreal.SystemLibrary.flush_async_loading()
    except Exception:
        pass
    try:
        unreal.AssetCompilingManager.get_default().finish_all_compilation()
    except Exception:
        pass
    try:
        _world = unreal.EditorLevelLibrary.get_editor_world()
        for _cmd in ("FlushRenderingCommands", "r.Streaming.FlushAll",
                      "r.Nanite.CoarseMeshStreaming.ForceFlush 1"):
            try:
                unreal.KismetSystemLibrary.execute_console_command(_world, _cmd)
            except Exception:
                pass
    except Exception:
        pass
    gc.collect()
    try:
        unreal.SystemLibrary.collect_garbage(full_purge=True)
    except Exception:
        unreal.SystemLibrary.collect_garbage()
    time.sleep(BATCH_DELAY)

# Clean up progress file on successful completion
if total_failed == 0 and os.path.isfile(PROGRESS_FILE):
    os.remove(PROGRESS_FILE)

# Restore default texture streaming pool
try:
    _world = unreal.EditorLevelLibrary.get_editor_world()
    unreal.KismetSystemLibrary.execute_console_command(_world, "r.Streaming.PoolSize 0")
except Exception:
    pass

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
