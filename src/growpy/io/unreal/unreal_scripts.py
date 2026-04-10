"""Unreal Engine import/cleanup script generation for exported forests.

Generates standalone Python scripts that can be executed inside Unreal Engine
to import USD tree assemblies and clean up previously imported assets.

Imports are split into per-species batch scripts to avoid video memory crashes.
Use ``python -m growpy.tools.ue_exec`` to run batches sequentially.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Snippet injected into batch scripts for GPU VRAM monitoring via nvidia-smi.
# Returns (used_mb, total_mb, percent) or None if nvidia-smi unavailable.
_VRAM_MONITOR_PREAMBLE = '''
import subprocess

# VRAM threshold: pause import when usage exceeds this percentage
# Set high (95%) because the orchestrator handles cleanup between batches at a lower threshold.
VRAM_LIMIT_PERCENT = 95

# Maximum time (seconds) to wait for VRAM to drop below threshold before giving up
VRAM_WAIT_TIMEOUT = 300

# Polling interval (seconds) when waiting for VRAM to settle
VRAM_POLL_INTERVAL = 15

def _get_gpu_vram():
    """Query GPU VRAM usage via nvidia-smi. Returns (used_mb, total_mb, pct) or None."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits", "--id=0"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            used = int(parts[0].strip())
            total = int(parts[1].strip())
            pct = round(used / total * 100, 1) if total > 0 else 0
            return (used, total, pct)
    except Exception:
        pass
    return None

def _vram_bar(pct):
    bar_len = 20
    filled = int(bar_len * pct / 100)
    return "#" * filled + "-" * (bar_len - filled)

def _check_vram(context=""):
    """Print VRAM usage and return True if over limit."""
    info = _get_gpu_vram()
    if info is None:
        return False
    used, total, pct = info
    status = f"  [VRAM] {used}/{total} MB ({pct}%) [{_vram_bar(pct)}]"
    if context:
        status += f"  ({context})"
    print(status)
    if VRAM_LIMIT_PERCENT > 0 and pct >= VRAM_LIMIT_PERCENT:
        return True
    return False

def _wait_for_vram(context="", min_delay=5.0):
    """Wait for VRAM to drop below threshold before continuing.

    Always waits at least min_delay seconds. If VRAM is over the limit,
    polls every VRAM_POLL_INTERVAL seconds until it drops below threshold
    or VRAM_WAIT_TIMEOUT is reached.

    Returns True if VRAM settled below threshold, False if timed out.
    """
    time.sleep(min_delay)
    info = _get_gpu_vram()
    if info is None:
        return True
    used, total, pct = info
    if VRAM_LIMIT_PERCENT <= 0 or pct < VRAM_LIMIT_PERCENT:
        print(f"  [VRAM] {used}/{total} MB ({pct}%) [{_vram_bar(pct)}]  ({context})")
        return True

    print(f"  [VRAM] {used}/{total} MB ({pct}%) [{_vram_bar(pct)}]  ({context})")
    print(f"  -- VRAM {pct}% >= {VRAM_LIMIT_PERCENT}% threshold, pausing until it settles...")
    waited = 0.0
    while waited < VRAM_WAIT_TIMEOUT:
        time.sleep(VRAM_POLL_INTERVAL)
        waited += VRAM_POLL_INTERVAL
        info = _get_gpu_vram()
        if info is None:
            return True
        used, total, pct = info
        mins = int(waited // 60)
        secs = int(waited % 60)
        print(f"  [VRAM] {used}/{total} MB ({pct}%) [{_vram_bar(pct)}]  (waited {mins}m{secs:02d}s)")
        if pct < VRAM_LIMIT_PERCENT:
            print(f"  -- VRAM settled below {VRAM_LIMIT_PERCENT}%, continuing")
            return True

    print(f"  ** VRAM still {pct}% after {int(VRAM_WAIT_TIMEOUT)}s timeout -- proceeding anyway **")
    print(f"  ** Per-file tracking ensures progress is safe even if UE crashes **")
    return True
'''


def _build_import_block(
    file_path: str,
    dest_path: str,
    label: str,
    wind_json_path: str = "",
    configure_nanite: bool = False,
    nanite_cfg: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a single USD import try/except block.

    When configure_nanite is True (for assembly imports), the block also
    configures the imported nanite assembly: Nanite shape preservation is set
    to Voxelize and fallback mesh VRAM is reduced. DynamicWind data is
    delivered via separate wind JSON files for post-import application.
    """
    config_block = ""
    if configure_nanite:
        cfg_repr = repr(nanite_cfg or {})
        config_block = f"""
            # Post-import: configure nanite assembly
            for _obj_path in (import_task.imported_object_paths or []):
                _obj_path_str = str(_obj_path)
                if "nanite_assembly" not in _obj_path_str.lower():
                    continue
                _mesh = unreal.EditorAssetLibrary.load_asset(_obj_path_str)
                if not _mesh:
                    continue
                _configure_nanite_assembly(_mesh, "{label}", {cfg_repr})
                # Save the configured asset to disk before unloading
                unreal.EditorAssetLibrary.save_asset(_obj_path_str)
                break
"""

    return f"""
if "{label}" in _completed_files:
    skipped_count += 1
    print(f"  Skipped (already imported): {label}")
else:
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
            _record_file_done("{label}")
            print(f"  Imported: {label}")
{config_block}
        else:
            failed_count += 1
            unreal.log_warning("Failed to import: {label}")

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

        # Save all dirty packages to disk so editor can release them
        try:
            unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)
        except Exception:
            pass

        # Flush GPU rendering commands and release pooled VRAM
        _w = _get_ue_world()
        if _w:
            for _cmd in (
                "FlushRenderingCommands",
                "r.Streaming.FlushAll",
                # Nuclear Nanite VRAM reclaim: release ALL pages temporarily
                "r.Nanite.MaxAllocatedPages 0",
                "r.Nanite.Streaming.MaxPendingPages 0",
                "r.Nanite.CoarseMeshStreaming.ForceFlush 1",
                "r.RHI.GPUDefrag",
                "r.D3D12.ResidencyManagement.DenyBudgetUpdates 1",
                "r.D3D12.FreeAllPooledTextures",
                "r.D3D12.FreeUnusedResources",
            ):
                try:
                    unreal.KismetSystemLibrary.execute_console_command(_w, _cmd)
                except Exception:
                    pass
            # Re-enable Nanite pool and streaming at reduced caps
            for _re_cmd in (
                "r.D3D12.ResidencyManagement.DenyBudgetUpdates 0",
                "r.Nanite.MaxAllocatedPages 512",
                "r.Nanite.Streaming.MaxPendingPages 32",
            ):
                try:
                    unreal.KismetSystemLibrary.execute_console_command(_w, _re_cmd)
                except Exception:
                    pass

        gc.collect()
        try:
            unreal.SystemLibrary.collect_garbage(full_purge=True)
        except Exception:
            unreal.SystemLibrary.collect_garbage()

        # Adaptive wait: pause until VRAM settles below threshold
        _wait_for_vram("{label}", min_delay=IMPORT_DELAY)

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
    return f"""
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
"""


def _build_datatable_script(
    project_path: str, scripts_dir: str, db_path: str = "/Game/Assets/TheGrove"
) -> str:
    """Build Unreal Python code that creates a DataTable cataloguing all imported trees.

    Scans the import path for nanite assembly skeletal meshes, parses metadata
    (species, height, DBH, competition) from the asset name convention, creates
    a DataTable via DataTableFactory, and populates it from CSV data.

    Requires a ST_TreeRecord struct to exist at db_path (one-time manual
    creation). The struct needs: SkeletalMesh (SoftObjectReference),
    Species (String), Height (Float), DBH (Float), Competition (Bool).

    Asset name convention: {Species}_{comp|open}_h{HH}m_d{DD}cm_{density}_assembly
    """
    scripts_dir_fwd = scripts_dir.replace("\\", "/")
    return f"""
import unreal
import re
import gc
import os
import json

print("")
print("=" * 60)
print("GrowPy Post-Import: Create Tree DataTable")
print("=" * 60)

IMPORT_PATH = "{project_path}"
DB_PATH = "{db_path}"
STRUCT_NAME = "ST_TreeRecord"
DATATABLE_NAME = "DT_TreeDatabase"
STRUCT_PATH = DB_PATH + "/" + STRUCT_NAME
DATATABLE_PATH = DB_PATH + "/" + DATATABLE_NAME

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_lib = unreal.EditorAssetLibrary

# Step 1: Find all nanite assembly skeletal meshes
all_assets = asset_registry.get_assets_by_path(IMPORT_PATH, recursive=True)
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
    # Skip assets in Instances/ (shared twigs, not tree assemblies)
    if "/Instances/" in pkg:
        continue
    assemblies.append((asset_name, pkg))

print(f"Found {{len(assemblies)}} nanite assembly skeletal meshes")

if not assemblies:
    print("No assemblies found -- skipping DataTable creation")
else:
    # Step 2: Parse metadata from package path
    # Folder convention: Species_Name_comp_h05m_d15cm_full_assembly
    # Asset name is SK_species_nanite_assembly (no height/dbh info)
    _PATTERN = re.compile(
        r"(.+?)_(comp|open)_h(\\d+)m_d(\\d+)cm_(.+?)_assembly",
        re.IGNORECASE,
    )
    # Known species folder names for fallback matching
    _SPECIES_FOLDERS = {{
        "austrian_pine", "black_alder", "common_ash", "douglas_fir",
        "european_beech", "european_larch", "european_oak", "field_maple",
        "grand_fir", "hornbeam", "japanese_larch", "norway_spruce",
        "scots_pine", "silver_birch", "silver_fir", "sitka_spruce",
        "small_leaved_linden", "sycamore_maple", "western_redcedar",
        "wild_cherry",
    }}
    rows = []
    for asset_name, pkg_path in assemblies:
        # Search all path parts for the height/dbh pattern (folder name)
        parts = pkg_path.split("/")
        m = None
        folder_name = ""
        for p in parts:
            m = _PATTERN.search(p)
            if m:
                folder_name = p
                break
        species = ""
        height_m = 0.0
        dbh_cm = 0.0
        competition = False
        if m:
            species = m.group(1).replace("_", " ")
            competition = m.group(2).lower() == "comp"
            height_m = float(m.group(3))
            dbh_cm = float(m.group(4))
        else:
            # Fallback: find species folder name in path
            for p in parts:
                if p.lower() in _SPECIES_FOLDERS:
                    species = p.replace("_", " ").title()
                    break
            if not species:
                species = asset_name
            if "competition" in pkg_path.lower() or "/comp" in pkg_path.lower():
                competition = True

        # Use assembly folder name as row name (unique per tree)
        # e.g. "Hornbeam_comp_h05m_d04cm_full_assembly" not "SK_hornbeam_nanite_assembly"
        # Full object path: PackageName.ObjectName (required for Soft Object References)
        rows.append({{
            "name": folder_name or asset_name,
            "pkg": f"{{pkg_path}}.{{asset_name}}",
            "species": species,
            "height": height_m,
            "dbh": dbh_cm,
            "competition": competition,
        }})

    print(f"Parsed metadata for {{len(rows)}} assemblies")

    # Step 3: Save tree inventory as JSON + CSV to disk (always succeeds)
    _scripts_dir = r"{scripts_dir_fwd}"
    _json_path = os.path.join(_scripts_dir, "tree_inventory.json")
    _csv_path = os.path.join(_scripts_dir, "tree_inventory.csv")

    json_rows = []
    csv_lines = ["Name,SkeletalMesh,Species,Height,DBH,Competition"]
    for row in rows:
        json_rows.append({{
            "Name": row["name"],
            "SkeletalMesh": row["pkg"],
            "Species": row["species"],
            "Height": row["height"],
            "DBH": row["dbh"],
            "Competition": row["competition"],
        }})
        comp_str = "true" if row["competition"] else "false"
        csv_lines.append(
            f'{{row["name"]}},{{row["pkg"]}},{{row["species"]}},'
            f'{{row["height"]}},{{row["dbh"]}},{{comp_str}}'
        )

    with open(_json_path, "w") as _jf:
        json.dump(json_rows, _jf, indent=2)
    with open(_csv_path, "w") as _cf:
        _cf.write("\\n".join(csv_lines))
    print(f"Saved tree_inventory.json and tree_inventory.csv ({{len(rows)}} trees)")

    # Step 4: Create DataTable programmatically
    # Requires a ST_TreeRecord struct to already exist (one-time manual setup).
    # The struct needs fields: SkeletalMesh (SoftObjectReference to SkeletalMesh),
    # Species (String), Height (Float), DBH (Float), Competition (Bool).
    tree_struct = None
    data_table = None

    if not editor_asset_lib.does_asset_exist(STRUCT_PATH):
        print("")
        print(f"Struct not found: {{STRUCT_PATH}}")
        print("Create it once manually (Miscellaneous > Structure) with fields:")
        print("  - SkeletalMesh (Soft Object Reference to SkeletalMesh)")
        print("  - Species (String)")
        print("  - Height (Float)")
        print("  - DBH (Float)")
        print("  - Competition (Bool)")
        print(f"Save it as: {{STRUCT_PATH}}")
        print("Then re-run this script to populate the DataTable.")
        print("")
        print("Tree inventory saved to disk for manual import if preferred:")
        print(f"  CSV: {{_csv_path}}")
        print(f"  JSON: {{_json_path}}")
    else:
        tree_struct = editor_asset_lib.load_asset(STRUCT_PATH)
        print(f"Using struct: {{STRUCT_PATH}}")

        # Delete existing DataTable if present (recreate with fresh data)
        if editor_asset_lib.does_asset_exist(DATATABLE_PATH):
            editor_asset_lib.delete_asset(DATATABLE_PATH)
            print(f"Deleted existing DataTable: {{DATATABLE_PATH}}")

        # Create DataTable with the struct as row type
        try:
            dt_factory = unreal.DataTableFactory()
            dt_factory.set_editor_property("struct", tree_struct)
            data_table = asset_tools.create_asset(
                DATATABLE_NAME, DB_PATH, unreal.DataTable, dt_factory
            )
        except Exception as e:
            unreal.log_warning(f"Could not create DataTable: {{e}}")

        if data_table is not None:
            print(f"Created DataTable: {{DATATABLE_PATH}}")

            # Build CSV with UE DataTable format (--- as row-name header)
            csv_header = "---,SkeletalMesh,Species,Height,DBH,Competition"
            csv_str = csv_header + "\\n" + "\\n".join(csv_lines[1:])
            populated = False

            # Try CSV fill first (most reliable for UE DataTables)
            try:
                populated = unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(
                    data_table, csv_str
                )
            except Exception:
                pass

            # Fallback: JSON fill
            if not populated:
                try:
                    json_str = json.dumps(json_rows, indent=2)
                    populated = unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(
                        data_table, json_str
                    )
                except Exception:
                    pass

            if populated:
                print(f"Populated {{len(rows)}} rows in DataTable")
            else:
                unreal.log_warning("Could not populate DataTable via CSV or JSON")
                print(f"Import manually: right-click DataTable > Reimport > {{_csv_path}}")

            editor_asset_lib.save_asset(DATATABLE_PATH)

    gc.collect()
    try:
        unreal.SystemLibrary.collect_garbage(full_purge=True)
    except Exception:
        unreal.SystemLibrary.collect_garbage()

print("")
print("=" * 60)
print("DataTable creation complete")
print("=" * 60)
"""


# Unreal Python preamble for configuring nanite assemblies after import.
# Included in species batch scripts to set shape preservation, wind data, etc.
_NANITE_CONFIG_PREAMBLE = '''

# ---------------------------------------------------------------------------
# Nanite assembly post-import configuration.
# DynamicWind data is delivered via separate wind JSON files.
# UE has no DynamicWindSkeletonAPI USD schema -- wind must be applied
# post-import (not via USD attributes).
# ---------------------------------------------------------------------------

def _set_nanite_shape_voxelize(mesh, label):
    """Set Nanite shape preservation to Voxelize using multiple strategies.

    ENaniteShapePreservation: None=0, PreserveArea=1, Voxelize=2
    The exact Python API varies by UE version, so we try several approaches.
    """
    _strategies = []

    # Strategy A: Enum without E prefix (UE 5.4+ Python reflection)
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property(
            "shape_preservation",
            unreal.NaniteShapePreservation.VOXELIZE,
        )
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"enum_no_e: {_e}")

    # Strategy B: Enum with E prefix
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property(
            "shape_preservation",
            unreal.ENaniteShapePreservation.VOXELIZE,
        )
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"enum: {_e}")

    # Strategy C: Type introspection -- read current value, construct enum(2)
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _cur = _ns.get_editor_property("shape_preservation")
        _enum_cls = type(_cur)
        _ns.set_editor_property("shape_preservation", _enum_cls(2))
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"introspect: {_e}")

    # Strategy D: Qualified enum path string
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property(
            "shape_preservation", "NaniteShapePreservation::Voxelize",
        )
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"qualified: {_e}")

    # Strategy E: Integer via set_editor_property
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property("shape_preservation", 2)
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"int: {_e}")

    # Strategy F: Direct attribute assignment on struct copy
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.shape_preservation = 2
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"attr: {_e}")

    # Strategy G: C++ getter/setter methods (StaticMesh only)
    try:
        _ns = mesh.get_nanite_settings()
        _ns.shape_preservation = 2
        mesh.set_nanite_settings(_ns)
        mesh.notify_nanite_settings_changed()
        return True
    except Exception as _e:
        _strategies.append(f"methods: {_e}")

    unreal.log_warning(f"Could not set shape preservation for {label}")
    for _s in _strategies:
        unreal.log_warning(f"    {_s}")
    return False


def _reduce_nanite_fallback(mesh, label, percent=1.0):
    """Reduce Nanite fallback mesh triangle percentage to save VRAM."""
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property("fallback_percent_triangles", percent)
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception:
        pass
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.fallback_percent_triangles = percent
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        unreal.log_warning(f"Could not set fallback triangle % for {label}: {_e}")
    return False


def _set_nanite_property(mesh, label, prop_name, value):
    """Set a single property on the mesh nanite_settings struct.

    Tries set_editor_property first, then direct attribute assignment.
    Returns True on success.
    """
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property(prop_name, value)
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception:
        pass
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        setattr(_ns, prop_name, value)
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        unreal.log_warning(f"Could not set {prop_name} for {label}: {_e}")
    return False


def _set_nanite_fallback_target(mesh, label, target_name):
    """Set Nanite fallback_target enum (PercentTriangles / RelativeError / Auto).

    Without this, UE may default to a heuristic that ignores
    fallback_percent_triangles entirely. Tries enum then int fallback.
    """
    _name_map = {
        "percent_triangles": ("PERCENT_TRIANGLES", 0),
        "relative_error": ("RELATIVE_ERROR", 1),
        "auto": ("AUTO", 2),
    }
    _enum_name, _enum_int = _name_map.get(
        (target_name or "percent_triangles").lower(),
        ("PERCENT_TRIANGLES", 0),
    )
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _enum_cls = getattr(unreal, "NaniteFallbackTarget", None)
        if _enum_cls is not None and hasattr(_enum_cls, _enum_name):
            _ns.set_editor_property(
                "fallback_target", getattr(_enum_cls, _enum_name)
            )
            mesh.set_editor_property("nanite_settings", _ns)
            return True
    except Exception:
        pass
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property("fallback_target", _enum_int)
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        unreal.log_warning(
            f"Could not set fallback_target for {label}: {_e}"
        )
    return False


def _configure_nanite_assembly(mesh, label, nanite_cfg=None):
    """Configure a nanite assembly after USD import.

    Sets Nanite shape preservation to Voxelize, reduces fallback mesh VRAM,
    and applies additional Nanite build settings from nanite_cfg dict.
    """
    if nanite_cfg is None:
        nanite_cfg = {}

    _set_nanite_shape_voxelize(mesh, label)

    # CRITICAL: set fallback_target BEFORE fallback_percent_triangles, else
    # UE may interpret the percent under the wrong heuristic.
    _set_nanite_fallback_target(
        mesh, label,
        nanite_cfg.get("fallback_target", "percent_triangles"),
    )

    _reduce_nanite_fallback(
        mesh, label, percent=nanite_cfg.get("fallback_percent", 0.01),
    )

    _fallback_rel = nanite_cfg.get("fallback_relative_error", 1.0)
    _set_nanite_property(
        mesh, label, "fallback_relative_error", _fallback_rel,
    )

    _trim_err = nanite_cfg.get("trim_relative_error", 0.0)
    if _trim_err > 0.0:
        _set_nanite_property(mesh, label, "trim_relative_error", _trim_err)

    _residency = nanite_cfg.get("target_residency_kb", 0)
    _set_nanite_property(
        mesh, label, "target_minimum_residency_in_kb", _residency,
    )

    if nanite_cfg.get("lerp_uvs", True):
        _set_nanite_property(mesh, label, "lerp_u_vs", True)

    _max_edge = nanite_cfg.get("max_edge_length_factor", 0.0)
    if _max_edge > 0.0:
        _set_nanite_property(mesh, label, "max_edge_length_factor", _max_edge)

    # Implicit tangents save build time + storage; only set true if asset
    # actually depends on baked tangents (rare for vegetation).
    _set_nanite_property(
        mesh, label, "explicit_tangents",
        bool(nanite_cfg.get("explicit_tangents", False)),
    )

    _pos_prec = nanite_cfg.get("position_precision", -1)
    if _pos_prec is not None and _pos_prec >= 0:
        _set_nanite_property(mesh, label, "position_precision", int(_pos_prec))

    _norm_prec = nanite_cfg.get("normal_precision", -1)
    if _norm_prec is not None and _norm_prec >= 0:
        _set_nanite_property(mesh, label, "normal_precision", int(_norm_prec))

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
    script_path_str = str(script_path.resolve()).replace("\\", "/")
    preamble = _NANITE_CONFIG_PREAMBLE if include_nanite_config else ""

    batch_progress_name = script_path.stem + "_done.txt"

    content = f'''"""
GrowPy batch import: {batch_label} ({file_count} files) - Auto-generated

Execute in Unreal Engine:
1. Right-click > "Execute Python File in Unreal"
2. Or: exec(open(r'{script_path_str}').read())

Per-file resume: successfully imported files are tracked in
  {batch_progress_name}
Delete that file to re-import everything in this batch.
"""

import unreal
import gc
import os
import time

def _get_ue_world():
    """Get editor world via UnrealEditorSubsystem (UE 5.4+), with legacy fallback."""
    try:
        return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    except Exception:
        pass
    try:
        return unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        return None

print("=" * 60)
print("GrowPy Batch Import: {batch_label}")
print("=" * 60)

IMPORT_PATH = "{project_path}"
IMPORT_DELAY = 5.0
_BATCH_PROGRESS = os.path.join(os.path.dirname(r'{script_path_str}'), "{batch_progress_name}")

# --- VRAM management: safe to run standalone ---
_world = _get_ue_world()
_VRAM_SAVED = {{}}
if _world:
    # Drop all quality to Medium for reduced VRAM during import
    try:
        unreal.KismetSystemLibrary.execute_console_command(_world, "scalability 1")
    except Exception:
        pass
    for _vk, _vv in (
        ("r.Lumen.DiffuseIndirect.Allow", "0"),
        ("r.Lumen.Reflections.Allow", "0"),
        ("r.Shadow.Virtual.Enable", "0"),
        ("r.Streaming.PoolSize", "128"),
        ("r.Streaming.PoolSizeVRAMPercentage", "0"),
        ("r.Streaming.FullyLoadUsedTextures", "0"),
        ("r.Nanite.MaxAllocatedPages", "512"),
        ("r.Nanite.Streaming.MaxPendingPages", "32"),
        ("r.Nanite.ProxyRenderMode", "1"),
        # Disable Nanite ray tracing buffers (duplicate VRAM for RT)
        ("r.RayTracing.Nanite.Mode", "0"),
        ("r.AllowCachedUniformExpressions", "0"),
    ):
        try:
            unreal.KismetSystemLibrary.execute_console_command(_world, f"{{_vk}} {{_vv}}")
        except Exception:
            pass
    print("VRAM management active (Lumen/VSM off, Nanite capped, RT Nanite off)")

# Load per-file progress for crash recovery
_completed_files = set()
if os.path.isfile(_BATCH_PROGRESS):
    with open(_BATCH_PROGRESS, "r") as _pf:
        _completed_files = set(line.strip() for line in _pf if line.strip())
    if _completed_files:
        print(f"Resuming: {{len(_completed_files)}} files already imported")
        print(f"Delete {batch_progress_name} to re-import all\\n")

def _record_file_done(label):
    """Append a completed file label to the batch progress file."""
    with open(_BATCH_PROGRESS, "a") as _pf:
        _pf.write(label + "\\n")
    _completed_files.add(label)

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
imported_count = 0
failed_count = 0
skipped_count = 0
'''
    # Insert VRAM monitor + nanite config preambles
    content += _VRAM_MONITOR_PREAMBLE
    content += preamble
    content += f"""
{import_blocks}

# --- Restore rendering settings ---
if _world:
    try:
        unreal.KismetSystemLibrary.execute_console_command(_world, "scalability 3")
    except Exception:
        pass
    for _rk, _rv in (
        ("r.Lumen.DiffuseIndirect.Allow", "1"),
        ("r.Lumen.Reflections.Allow", "1"),
        ("r.Shadow.Virtual.Enable", "1"),
        ("r.Streaming.PoolSize", "0"),
        ("r.Streaming.PoolSizeVRAMPercentage", "75"),
        ("r.Streaming.FullyLoadUsedTextures", "0"),
        ("r.Nanite.MaxAllocatedPages", "0"),
        ("r.Nanite.Streaming.MaxPendingPages", "128"),
        ("r.Nanite.ProxyRenderMode", "0"),
        ("r.RayTracing.Nanite.Mode", "1"),
        ("r.AllowCachedUniformExpressions", "1"),
    ):
        try:
            unreal.KismetSystemLibrary.execute_console_command(_world, f"{{_rk}} {{_rv}}")
        except Exception:
            pass
    print("Rendering settings restored")

print("")
print("=" * 60)
print(f"Batch '{batch_label}' complete: {{imported_count}} imported, {{skipped_count}} skipped, {{failed_count}} failed")
print("=" * 60)
"""

    script_path.write_text(content, encoding="utf-8")


def generate_unreal_import_script(
    output_dir: Path,
    project_path: str = "/Game/GrowPy/Trees",
    include_static: bool = False,
    voxelization: bool = True,
    nanite_cfg: Optional[Dict[str, Any]] = None,
    db_path: str = "/Game/Assets/TheGrove",
) -> Path:
    """Generate Unreal Python scripts for importing forest USD files.

    Produces one script per species (plus one for shared instances).
    Each file import is monitored with adaptive VRAM waiting that pauses
    automatically when GPU memory is high. Use ue_exec to run the batch
    scripts sequentially with resource monitoring between batches.

    Args:
        output_dir: Directory containing exported USD files.
        project_path: Unreal project Content path.
        include_static: If True, include static twig variants and static assemblies.
            Mirrors [export] static setting from growpy.toml.
        voxelization: If True, set Nanite shape preservation to Voxelize
            on imported assemblies. Mirrors [unreal] voxelization from growpy.toml.
        nanite_cfg: Optional dict of Nanite build parameters passed through to
            _configure_nanite_assembly in generated scripts. Keys:
            fallback_percent, fallback_target, fallback_relative_error,
            trim_relative_error, target_residency_kb, lerp_uvs,
            max_edge_length_factor, explicit_tangents, position_precision,
            normal_precision.

    Returns:
        Path to generated scripts directory.
    """
    script_dir = output_dir / "unreal_scripts"
    script_dir.mkdir(exist_ok=True)

    # Remove stale batch scripts from previous runs
    for old_script in script_dir.glob("import_batch_*.py"):
        old_script.unlink()

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
        f for f in nanite_files if f.relative_to(output_dir).parts[0] not in skip_dirs
    ]
    nanite_files = []
    for f in nanite_files_raw:
        if f.stat().st_size < MIN_ASSEMBLY_BYTES:
            logger.warning(
                "Skipping empty/stub assembly %s (%d bytes)",
                f.name,
                f.stat().st_size,
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

    # Track batch scripts: (filename, label)
    batch_scripts: List[Tuple[str, str]] = []

    # Batch 0: Shared instances (single batch -- per-file VRAM monitoring
    # handles memory pressure so sub-batching is unnecessary)
    if instance_files:
        sorted_instances = sorted(instance_files)
        blocks = ""
        blocks += 'print("Importing shared twig/foliage instances...")\n'
        for inst_file in sorted_instances:
            inst_path = str(inst_file.resolve()).replace("\\", "/")
            blocks += _build_import_block(inst_path, "Instances", inst_file.stem)

        batch_name = "import_batch_00_instances.py"
        batch_label = f"Shared instances ({len(sorted_instances)} files)"
        _write_batch_script(
            script_dir / batch_name,
            project_path,
            batch_label,
            blocks,
            len(sorted_instances),
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
                    # Match wind JSON to this specific tree by prefix
                    tree_prefix = usd_file.stem.replace("_assembly", "")
                    wind_files = sorted(
                        usd_file.parent.glob(f"{tree_prefix}_stems_unreal_wind.json")
                    )
                    if not wind_files:
                        wind_files = sorted(
                            usd_file.parent.glob("*_stems_unreal_wind.json")
                        )
                    if wind_files:
                        wind_json = str(wind_files[0].resolve()).replace("\\", "/")

                blocks += _build_import_block(
                    usd_path,
                    dest_subpath,
                    usd_file.stem,
                    wind_json_path=wind_json,
                    configure_nanite=is_assembly and voxelization,
                    nanite_cfg=nanite_cfg,
                )

        batch_name = f"import_batch_{idx:02d}_{species_folder}.py"
        batch_label = f"{species_folder} ({species_tree_count} trees)"
        _write_batch_script(
            script_dir / batch_name,
            project_path,
            batch_label,
            blocks,
            species_tree_count,
            include_nanite_config=has_assemblies and voxelization,
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

    # DataTable batch: catalogue all imported assemblies
    datatable_code = _build_datatable_script(
        project_path, str(script_dir.resolve()), db_path
    )
    datatable_name = "import_batch_100_datatable.py"
    datatable_label = "Create tree inventory DataTable"
    datatable_path = script_dir / datatable_name
    datatable_path.write_text(datatable_code, encoding="utf-8")
    batch_scripts.append((datatable_name, datatable_label))

    # Remove stale master script from previous runs
    stale_master = script_dir / "import_forest.py"
    if stale_master.exists():
        stale_master.unlink()

    logger.info(
        "Generated %d batch import scripts in %s",
        len(batch_scripts),
        script_dir,
    )
    return script_dir


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


def generate_wind_reimport_script(
    output_dir: Path,
    project_path: str = "/Game/GrowPy/Trees",
) -> Path:
    """Generate a UE Python script that re-imports wind data for all assemblies.

    .. deprecated::
        Wind data is delivered via separate JSON files alongside USD exports.
        UE has no DynamicWindSkeletonAPI USD schema, so wind must be applied
        post-import. This function currently generates a no-op stub.

    Args:
        output_dir: Directory containing exported USD files (parent of unreal_scripts/).
        project_path: Unreal project Content path.

    Returns:
        Path to generated informational script.
    """
    script_dir = output_dir / "unreal_scripts"
    script_dir.mkdir(exist_ok=True)

    script_path = script_dir / "import_batch_97_wind_reimport.py"
    script_path_str = str(script_path.resolve()).replace("\\", "/")

    content = f'''"""
GrowPy wind data - Auto-generated (informational only)

Wind data is exported as separate JSON files (*_unreal_wind.json) alongside
the USD files. UE has no DynamicWindSkeletonAPI USD schema, so wind must be
applied post-import via DynamicWind::ImportSkeletalData or equivalent.

This script is a no-op placeholder for future wind import automation.

Execute in Unreal Engine (optional):
  exec(open(r'{script_path_str}').read())
"""

import unreal

print("=" * 60)
print("GrowPy DynamicWind - Wind JSON files exported alongside USD")
print("Wind must be applied post-import (no USD schema exists).")
print("See *_unreal_wind.json files for per-joint classification.")
print("=" * 60)
'''

    script_path.write_text(content, encoding="utf-8")
    logger.info(
        "Generated wind info script (no-op): %s",
        script_path,
    )
    return script_path
