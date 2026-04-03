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

# Snippet injected into batch scripts for GPU VRAM monitoring via nvidia-smi.
# Returns (used_mb, total_mb, percent) or None if nvidia-smi unavailable.
_VRAM_MONITOR_PREAMBLE = '''
import subprocess

# Maximum VRAM usage percentage before auto-stopping import (0 = disabled)
VRAM_LIMIT_PERCENT = 85

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

def _check_vram(context=""):
    """Print VRAM usage and return True if over limit (should stop)."""
    info = _get_gpu_vram()
    if info is None:
        return False
    used, total, pct = info
    bar_len = 20
    filled = int(bar_len * pct / 100)
    bar = "#" * filled + "-" * (bar_len - filled)
    status = f"  [VRAM] {used}/{total} MB ({pct}%) [{bar}]"
    if context:
        status += f"  ({context})"
    print(status)
    if VRAM_LIMIT_PERCENT > 0 and pct >= VRAM_LIMIT_PERCENT:
        print(f"  ** VRAM usage {pct}% >= limit {VRAM_LIMIT_PERCENT}% -- stopping batch to prevent crash **")
        print(f"  ** Restart UE and re-run this script to continue (resume is automatic) **")
        return True
    return False

_vram_exceeded = False
'''


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
                # Save the configured asset to disk before unloading
                unreal.EditorAssetLibrary.save_asset(_obj_path_str)
                break
"""

    return f"""
if _vram_exceeded:
    pass  # skip remaining imports
elif "{label}" in _completed_files:
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
        try:
            _w = unreal.EditorLevelLibrary.get_editor_world()
            for _cmd in (
                "FlushRenderingCommands",
                "r.Streaming.FlushAll",
                "r.Nanite.CoarseMeshStreaming.ForceFlush 1",
                "r.Nanite.Streaming.MaxPendingPages 0",
                "r.RHI.GPUDefrag",
                "r.D3D12.ResidencyManagement.DenyBudgetUpdates 1",
                "r.D3D12.FreeAllPooledTextures",
                "r.D3D12.FreeUnusedResources",
            ):
                try:
                    unreal.KismetSystemLibrary.execute_console_command(_w, _cmd)
                except Exception:
                    pass
            # Re-enable budget updates and streaming
            for _re_cmd in (
                "r.D3D12.ResidencyManagement.DenyBudgetUpdates 0",
                "r.Nanite.Streaming.MaxPendingPages 128",
            ):
                try:
                    unreal.KismetSystemLibrary.execute_console_command(_w, _re_cmd)
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

        # Check VRAM after cleanup -- stop batch if over limit
        if _check_vram("{label}"):
            _vram_exceeded = True

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


def _build_datatable_script(project_path: str) -> str:
    """Build Unreal Python code that creates a DataTable cataloguing all imported trees.

    Scans the import path for nanite assembly skeletal meshes, parses metadata
    (species, height, DBH, competition) from the asset name convention, creates
    a DataTable, and populates it. Falls back to saving a CSV file if Python
    DataTable creation fails (common in UE 5.7+).

    Asset name convention: {Species}_{comp|open}_h{HH}m_d{DD}cm_{density}_assembly
    """
    return f'''
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
STRUCT_NAME = "GrowPyTreeInfo"
DATATABLE_NAME = "DT_GrowPyTrees"
STRUCT_PATH = IMPORT_PATH + "/" + STRUCT_NAME
DATATABLE_PATH = IMPORT_PATH + "/" + DATATABLE_NAME

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
    _scripts_dir = os.path.dirname(os.path.abspath(__file__))
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

    # Step 4: Try to create DataTable programmatically
    # UE 5.7+ UserDefinedStructFactory is not available in Python, so we
    # try multiple approaches and fall back to CSV file for manual import.
    tree_struct = None
    data_table = None

    # Approach A: Reuse existing struct if it already exists
    if editor_asset_lib.does_asset_exist(STRUCT_PATH):
        print(f"Struct already exists: {{STRUCT_PATH}} -- reusing")
        tree_struct = editor_asset_lib.load_asset(STRUCT_PATH)

    # Approach B: Try creating struct via Python (may fail in some UE versions)
    if tree_struct is None:
        try:
            _factory = unreal.UserDefinedStructFactory()
            tree_struct = asset_tools.create_asset(
                STRUCT_NAME, IMPORT_PATH,
                unreal.UserDefinedStruct, _factory,
            )
        except Exception:
            pass

    # If struct creation succeeded, try DataTable creation + population
    if tree_struct is not None:
        # Delete existing DataTable if present
        if editor_asset_lib.does_asset_exist(DATATABLE_PATH):
            editor_asset_lib.delete_asset(DATATABLE_PATH)
            print(f"Deleted existing DataTable: {{DATATABLE_PATH}}")

        try:
            dt_factory = unreal.DataTableFactory()
            dt_factory.set_editor_property("struct", tree_struct)
            data_table = asset_tools.create_asset(
                DATATABLE_NAME, IMPORT_PATH, unreal.DataTable, dt_factory
            )
        except Exception as e:
            unreal.log_warning(f"Could not create DataTable: {{e}}")

        if data_table is not None:
            print(f"Created DataTable: {{DATATABLE_PATH}}")
            json_str = json.dumps(json_rows, indent=2)
            try:
                success = unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(
                    data_table, json_str
                )
                if success:
                    print(f"Populated {{len(json_rows)}} rows in DataTable")
                else:
                    # Try CSV fallback
                    csv_str = "\\n".join(["---,SkeletalMesh,Species,Height,DBH,Competition"] + csv_lines[1:])
                    try:
                        success2 = unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(
                            data_table, csv_str
                        )
                        if success2:
                            print(f"Populated {{len(rows)}} rows via CSV fallback")
                    except Exception:
                        pass
            except Exception as e:
                unreal.log_warning(f"Error populating DataTable: {{e}}")
            editor_asset_lib.save_asset(DATATABLE_PATH)

    if data_table is None:
        print("")
        print("NOTE: Automated DataTable creation not supported in this UE version.")
        print("Tree inventory saved to disk. To import manually:")
        print(f"  CSV: {{_csv_path}}")
        print(f"  JSON: {{_json_path}}")
        print("")
        print("Manual DataTable creation:")
        print("  1. Create a struct (Miscellaneous > Structure) with fields:")
        print("     - SkeletalMesh (Soft Object Reference)")
        print("     - Species (String)")
        print("     - Height (Float)")
        print("     - DBH (Float)")
        print("     - Competition (Bool)")
        print("  2. Create a DataTable using that struct")
        print("  3. Right-click DataTable > Reimport > select tree_inventory.csv")

    gc.collect()
    try:
        unreal.SystemLibrary.collect_garbage(full_purge=True)
    except Exception:
        unreal.SystemLibrary.collect_garbage()

print("")
print("=" * 60)
print("DataTable creation complete")
print("=" * 60)
'''


# Unreal Python preamble for configuring nanite assemblies after import.
# Included in species batch scripts to set shape preservation, wind data, etc.
_NANITE_CONFIG_PREAMBLE = '''
import os
import json
import math

# ---------------------------------------------------------------------------
# UE 5.7 API discovery: DynamicWind plugin classes may not have Python stubs.
# We try direct module access first, then fall back to dynamic class loading
# via the UE reflection system.
# ---------------------------------------------------------------------------

def _resolve_ue_class(direct_name, script_path):
    """Find a UClass by direct attribute or by /Script/ object path."""
    # 1. Direct unreal.ClassName (works if Python stubs exist)
    try:
        return getattr(unreal, direct_name)
    except AttributeError:
        pass
    # 2. load_object with the /Script/Module.ClassName path
    try:
        cls = unreal.load_object(unreal.Class, script_path)
        if cls is not None:
            return cls
    except Exception:
        pass
    # 3. find_object fallback
    try:
        cls = unreal.find_object(None, script_path)
        if cls is not None:
            return cls
    except Exception:
        pass
    return None

def _resolve_ue_struct_class(direct_name):
    """Check if a USTRUCT wrapper is available on the unreal module."""
    try:
        return getattr(unreal, direct_name)
    except AttributeError:
        return None

# Pre-resolve DynamicWind classes once at import time
_WIND_SKEL_CLS = _resolve_ue_class(
    "DynamicWindSkeletalData",
    "/Script/DynamicWind.DynamicWindSkeletalData",
)
_WIND_SIM_GROUP_CLS = _resolve_ue_struct_class("DynamicWindSimulationGroupData")
_WIND_BONE_LOOKUP_CLS = _resolve_ue_struct_class("DynamicWindSimulationGroupBoneLookup")
_WIND_BONE_CHAIN_CLS = _resolve_ue_struct_class("DynamicWindBoneChainData")
_WIND_EXTRA_BONE_CLS = _resolve_ue_struct_class("DynamicWindExtraBoneData")

if _WIND_SKEL_CLS:
    print("  [DynamicWind] Skeletal data class found -- batch wind import available")
else:
    print("  [DynamicWind] Skeletal data class not found in Python")
    print("  Wind data must be imported manually: right-click mesh > Scripted Asset Actions > Import Dynamic Wind Data")


def _set_nanite_shape_voxelize(mesh, label):
    """Set Nanite shape preservation to Voxelize using multiple strategies.

    ENaniteShapePreservation: None=0, PreserveArea=1, Voxelize=2
    The exact Python API varies by UE version, so we try several approaches.
    """
    _strategies = []

    # Strategy A: Enum via get/set_editor_property
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

    # Strategy B: Integer via set_editor_property
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property("shape_preservation", 2)
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"int: {_e}")

    # Strategy C: String value
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property("shape_preservation", "Voxelize")
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"str: {_e}")

    # Strategy D: Direct attribute assignment on struct copy
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.shape_preservation = 2
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"attr: {_e}")

    # Strategy E: C++ getter/setter methods
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


def _import_wind_data(mesh, wind_json_path, label):
    """Import DynamicWind skeletal data from JSON into a SkeletalMesh.

    Replicates the C++ DynamicWind::ImportSkeletalData logic:
    1. Creates UDynamicWindSkeletalData as asset user data
    2. Sets simulation groups from JSON
    3. Maps joints to bone indices
    4. Computes bone chains and extra bone data
    """
    if not wind_json_path or not os.path.isfile(wind_json_path):
        return None

    try:
        with open(wind_json_path, "r") as _wf:
            _wind_json = json.load(_wf)
    except Exception as _e:
        unreal.log_warning(f"Could not read wind JSON for {label}: {_e}")
        return False

    _joints = _wind_json.get("Joints", [])
    _sim_groups = _wind_json.get("SimulationGroups", [])
    _is_ground_cover = _wind_json.get("bIsGroundCover", False)
    _gust_atten = _wind_json.get("GustAttenuation", 0.0)

    # --- Strategy A: Create DynamicWindSkeletalData via resolved class ---
    if _WIND_SKEL_CLS is not None:
        try:
            _skel_data = mesh.get_asset_user_data_of_class(_WIND_SKEL_CLS)
            if _skel_data is None:
                _skel_data = unreal.new_object(type=_WIND_SKEL_CLS, outer=mesh)
                mesh.add_asset_user_data(_skel_data)

            # Basic properties (C++ names: bIsEnabled, bIsGroundCover, GustAttenuation)
            for _prop, _val in (
                ("is_enabled", True),
                ("is_ground_cover", _is_ground_cover),
                ("gust_attenuation", float(_gust_atten)),
            ):
                try:
                    _skel_data.set_editor_property(_prop, _val)
                except Exception:
                    setattr(_skel_data, _prop, _val)

            # Build skeleton bone lookup: name -> index
            _ref_skel = mesh.get_editor_property("ref_skeleton")
            _bone_count = _ref_skel.get_num() if _ref_skel else 0
            _bone_name_to_idx = {}
            _bone_parent = {}
            for _bi in range(_bone_count):
                _bname = str(_ref_skel.get_bone_name(_bi))
                _bone_name_to_idx[_bname] = _bi
                _bone_parent[_bi] = _ref_skel.get_parent_index(_bi)

            # Map joints to bone indices and track max simulation group index
            _max_sg = -1
            _bone_sg = {}  # bone_index -> sim_group_index
            for _j in _joints:
                _jn = _j.get("JointName", "")
                _si = _j.get("SimulationGroupIndex", 0)
                if _jn in _bone_name_to_idx:
                    _bidx = _bone_name_to_idx[_jn]
                    _bone_sg[_bidx] = _si
                    _max_sg = max(_max_sg, _si)

            # Ensure enough simulation groups exist (C++ fills missing with defaults)
            _groups_data = list(_sim_groups)
            while len(_groups_data) < _max_sg + 1:
                _groups_data.append({"Influence": 1.0})

            # Set simulation groups (try struct creation, fall back to direct property)
            if _WIND_SIM_GROUP_CLS is not None:
                _groups = []
                for _sg in _groups_data:
                    _g = _WIND_SIM_GROUP_CLS()
                    for _pn, _jk, _dv in (
                        ("use_dual_influence", "bUseDualInfluence", False),
                        ("influence", "Influence", 1.0),
                        ("min_influence", "MinInfluence", 0.0),
                        ("max_influence", "MaxInfluence", 0.0),
                        ("shift_top", "ShiftTop", 0.0),
                        ("is_trunk_group", "bIsTrunkGroup", False),
                    ):
                        try:
                            _g.set_editor_property(_pn, _sg.get(_jk, _dv))
                        except Exception:
                            setattr(_g, _pn, _sg.get(_jk, _dv))
                    _groups.append(_g)
                _skel_data.set_editor_property("simulation_groups", _groups)
            else:
                unreal.log_warning(f"    DynamicWindSimulationGroupData not available; sim groups not set")

            # Build SimulationGroupBones using bone INDICES (int32, not names)
            _sg_bone_map = {}
            for _bidx, _si in _bone_sg.items():
                _sg_bone_map.setdefault(_si, set()).add(_bidx)

            if _WIND_BONE_LOOKUP_CLS is not None:
                _lookups = []
                for _si, _bset in sorted(_sg_bone_map.items()):
                    _lk = _WIND_BONE_LOOKUP_CLS()
                    try:
                        _lk.set_editor_property("simulation_group_index", _si)
                        _lk.set_editor_property("bone_indices", _bset)
                    except Exception:
                        _lk.simulation_group_index = _si
                        _lk.bone_indices = _bset
                    _lookups.append(_lk)
                _skel_data.set_editor_property("simulation_group_bones", _lookups)

            # Compute BoneChains and ExtraBonesData (mirrors C++ ImportSkeletalData)
            # BoneChains: for each chain-origin bone, store count and total length
            # ExtraBonesData: for each bone, store chain origin and position in chain
            if _WIND_BONE_CHAIN_CLS and _WIND_EXTRA_BONE_CLS:
                try:
                    _bone_chains = {}  # origin_idx -> (num_bones, chain_length)
                    _extra_bones = {}  # bone_idx -> (origin_idx, idx_in_chain)

                    # Get bone transforms for chain length calculation
                    _bone_pos = {}
                    for _bi in range(_bone_count):
                        try:
                            _t = _ref_skel.get_ref_bone_pose(_bi)
                            _loc = _t.translation
                            _bone_pos[_bi] = (_loc.x, _loc.y, _loc.z)
                        except Exception:
                            _bone_pos[_bi] = (0.0, 0.0, 0.0)

                    for _bidx, _si in _bone_sg.items():
                        # Walk parent chain to find origin (first bone with different sim group)
                        _origin = _bidx
                        _depth = 0
                        _cur = _bone_parent.get(_bidx, -1)
                        while _cur >= 0:
                            if _bone_sg.get(_cur, -1) != _si:
                                break
                            _origin = _cur
                            _depth += 1
                            _cur = _bone_parent.get(_cur, -1)

                        _extra_bones[_bidx] = (_origin, _depth)

                        # Accumulate chain data
                        if _origin not in _bone_chains:
                            _bone_chains[_origin] = [0, 0.0]
                        _bone_chains[_origin][0] += 1

                        # Chain length: distance from parent pos to this bone pos
                        _pidx = _bone_parent.get(_bidx, -1)
                        _start = _bone_pos.get(_pidx, (0, 0, 0)) if _pidx >= 0 else (0, 0, 0)
                        _end = _bone_pos.get(_bidx, (0, 0, 0))
                        _dx = _end[0] - _start[0]
                        _dy = _end[1] - _start[1]
                        _dz = _end[2] - _start[2]
                        _bone_chains[_origin][1] += math.sqrt(_dx*_dx + _dy*_dy + _dz*_dz)

                    # Set BoneChains as dict: int32 -> FDynamicWindBoneChainData
                    _bc_map = {}
                    for _oidx, (_cnt, _clen) in _bone_chains.items():
                        _bc = _WIND_BONE_CHAIN_CLS()
                        try:
                            _bc.set_editor_property("num_bones", _cnt)
                            _bc.set_editor_property("chain_length", _clen)
                        except Exception:
                            _bc.num_bones = _cnt
                            _bc.chain_length = _clen
                        _bc_map[_oidx] = _bc
                    _skel_data.set_editor_property("bone_chains", _bc_map)

                    # Set ExtraBonesData as dict: int32 -> FDynamicWindExtraBoneData
                    _eb_map = {}
                    for _bidx, (_oidx, _depth) in _extra_bones.items():
                        _eb = _WIND_EXTRA_BONE_CLS()
                        try:
                            _eb.set_editor_property("bone_chain_origin_bone_index", _oidx)
                            _eb.set_editor_property("index_in_bone_chain", _depth)
                        except Exception:
                            _eb.bone_chain_origin_bone_index = _oidx
                            _eb.index_in_bone_chain = _depth
                        _eb_map[_bidx] = _eb
                    _skel_data.set_editor_property("extra_bones_data", _eb_map)
                except Exception as _ce:
                    unreal.log_warning(f"    BoneChain computation failed (non-critical): {_ce}")

            # Trigger hash recalculation via property change notification
            try:
                _skel_data.modify(True)
            except Exception:
                pass

            mesh.modify(True)
            print(f"    [Wind] Imported ({len(_joints)} joints, {len(_sim_groups)} groups): {label}")
            return True
        except Exception as _we:
            unreal.log_warning(f"    Wind (Python) failed for {label}: {_we}")

    # Fallback: log manual instructions (do NOT use file-dialog API)
    unreal.log_warning(
        f"Could not auto-import wind for {label}\\n"
        f"  Manual: right-click mesh > Scripted Asset Actions > Import Dynamic Wind Data\\n"
        f"  JSON: {wind_json_path}"
    )
    return False


def _configure_nanite_assembly(mesh, wind_json_path, label):
    """Configure a nanite assembly after USD import.

    Sets Nanite shape preservation to Voxelize and imports DynamicWind data.
    """
    _set_nanite_shape_voxelize(mesh, label)
    _import_wind_data(mesh, wind_json_path, label)
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

print("=" * 60)
print("GrowPy Batch Import: {batch_label}")
print("=" * 60)

IMPORT_PATH = "{project_path}"
IMPORT_DELAY = 5.0
_BATCH_PROGRESS = os.path.join(os.path.dirname(r'{script_path_str}'), "{batch_progress_name}")

# --- VRAM management: safe to run standalone ---
_world = None
try:
    _world = unreal.EditorLevelLibrary.get_editor_world()
except Exception:
    pass
_VRAM_SAVED = {{}}
if _world:
    for _vk, _vv in (
        ("r.Lumen.DiffuseIndirect.Allow", "0"),
        ("r.Lumen.Reflections.Allow", "0"),
        ("r.Shadow.Virtual.Enable", "0"),
        ("r.Streaming.PoolSize", "256"),
        ("r.Nanite.MaxAllocatedPages", "2048"),
        ("r.Nanite.Streaming.MaxPendingPages", "64"),
        ("r.AllowCachedUniformExpressions", "0"),
    ):
        try:
            unreal.KismetSystemLibrary.execute_console_command(_world, f"{{_vk}} {{_vv}}")
        except Exception:
            pass
    print("VRAM management active (Lumen/VSM off, Nanite capped)")

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

# --- VRAM status at end of batch ---
if _vram_exceeded:
    print("")
    print("** VRAM limit reached -- batch stopped early. Restart UE and re-run. **")

# --- Restore rendering settings ---
if _world:
    for _rk, _rv in (
        ("r.Lumen.DiffuseIndirect.Allow", "1"),
        ("r.Lumen.Reflections.Allow", "1"),
        ("r.Shadow.Virtual.Enable", "1"),
        ("r.Streaming.PoolSize", "0"),
        ("r.Nanite.MaxAllocatedPages", "0"),
        ("r.Nanite.Streaming.MaxPendingPages", "128"),
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

    # Batch 0+: Shared instances (split into sub-batches of max 10 files
    # to avoid VRAM exhaustion from importing all twigs at once)
    MAX_INSTANCE_BATCH = 10
    if instance_files:
        sorted_instances = sorted(instance_files)
        for sub_idx, chunk_start in enumerate(
            range(0, len(sorted_instances), MAX_INSTANCE_BATCH)
        ):
            chunk = sorted_instances[chunk_start : chunk_start + MAX_INSTANCE_BATCH]
            chunk_count = len(chunk)
            blocks = ""
            blocks += 'print("Importing shared twig/foliage instances...")\n'
            for inst_file in chunk:
                inst_path = str(inst_file.resolve()).replace("\\", "/")
                blocks += _build_import_block(
                    inst_path, "Instances", inst_file.stem
                )

            batch_name = f"import_batch_00{chr(ord('a') + sub_idx)}_instances.py"
            batch_label = (
                f"Shared instances part {sub_idx + 1} ({chunk_count} files)"
            )
            _write_batch_script(
                script_dir / batch_name,
                project_path,
                batch_label,
                blocks,
                chunk_count,
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

    # DataTable batch: catalogue all imported assemblies
    datatable_code = _build_datatable_script(project_path)
    datatable_name = "import_batch_100_datatable.py"
    datatable_label = "Create tree inventory DataTable"
    datatable_path = script_dir / datatable_name
    datatable_path.write_text(datatable_code, encoding="utf-8")
    batch_scripts.append((datatable_name, datatable_label))

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
import subprocess

print("=" * 60)
print("GrowPy Forest Import to Unreal Engine")
print("=" * 60)

IMPORT_PATH = "{project_path}"
SCRIPTS_DIR = r"{scripts_dir_str}"

# Delay between batches (seconds) - increase if you still get VRAM crashes
BATCH_DELAY = 60.0

# Maximum VRAM usage percentage before auto-stopping (0 = disabled)
VRAM_LIMIT_PERCENT = 85

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

def _check_vram(context=""):
    """Print VRAM usage and return True if over limit (should stop)."""
    info = _get_gpu_vram()
    if info is None:
        return False
    used, total, pct = info
    bar_len = 20
    filled = int(bar_len * pct / 100)
    bar = "#" * filled + "-" * (bar_len - filled)
    status = f"  [VRAM] {{used}}/{{total}} MB ({{pct}}%) [{{bar}}]"
    if context:
        status += f"  ({{context}})"
    print(status)
    if VRAM_LIMIT_PERCENT > 0 and pct >= VRAM_LIMIT_PERCENT:
        print(f"  ** VRAM usage {{pct}}% >= limit {{VRAM_LIMIT_PERCENT}}% -- stopping to prevent crash **")
        return True
    return False

# Show initial VRAM state
_check_vram("before import")

# --- VRAM management: reduce GPU memory pressure during import ---
# Disable expensive rendering features that consume VRAM during import
_world = None
try:
    _world = unreal.EditorLevelLibrary.get_editor_world()
except Exception:
    pass

_VRAM_SETUP_CMDS = (
    # Cap texture streaming pool to 256 MB (default ~1024 MB)
    "r.Streaming.PoolSize 256",
    # Disable Lumen GI and reflections (major VRAM consumers)
    "r.Lumen.DiffuseIndirect.Allow 0",
    "r.Lumen.Reflections.Allow 0",
    # Disable Virtual Shadow Maps
    "r.Shadow.Virtual.Enable 0",
    # Cap Nanite page pool to limit GPU memory usage
    "r.Nanite.MaxAllocatedPages 2048",
    # Limit Nanite streaming pressure
    "r.Nanite.Streaming.MaxPendingPages 64",
    # Disable thumbnail generation during import
    "r.AllowCachedUniformExpressions 0",
)
if _world:
    for _cmd in _VRAM_SETUP_CMDS:
        try:
            unreal.KismetSystemLibrary.execute_console_command(_world, _cmd)
        except Exception:
            pass
    print("VRAM management: Lumen/VSM disabled, Nanite pool capped")

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
    # Save all dirty packages to disk so editor can release GPU resources
    try:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)
    except Exception:
        pass
    try:
        _world = unreal.EditorLevelLibrary.get_editor_world()
        for _cmd in (
            "FlushRenderingCommands",
            "r.Streaming.FlushAll",
            "r.Nanite.CoarseMeshStreaming.ForceFlush 1",
            "r.Nanite.Streaming.MaxPendingPages 0",
            "r.RHI.GPUDefrag",
            "r.D3D12.ResidencyManagement.DenyBudgetUpdates 1",
            "r.D3D12.FreeAllPooledTextures",
            "r.D3D12.FreeUnusedResources",
        ):
            try:
                unreal.KismetSystemLibrary.execute_console_command(_world, _cmd)
            except Exception:
                pass
        # Re-enable budget updates and nanite streaming
        for _re_cmd in (
            "r.D3D12.ResidencyManagement.DenyBudgetUpdates 0",
            "r.Nanite.Streaming.MaxPendingPages 64",
        ):
            try:
                unreal.KismetSystemLibrary.execute_console_command(_world, _re_cmd)
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

    # Check VRAM between batches -- stop master loop if over limit
    if _check_vram(f"after batch {{_batch_idx + 1}}"):
        print(f"\\n** VRAM limit reached after batch {{_batch_idx + 1}} -- stopping master import **")
        print("** Restart UE and re-run import_forest.py to continue (resume is automatic) **")
        break

# Clean up progress files on successful completion
if total_failed == 0 and os.path.isfile(PROGRESS_FILE):
    os.remove(PROGRESS_FILE)
    # Also clean up per-file batch progress files
    for _done_file in [f for f in os.listdir(SCRIPTS_DIR) if f.endswith("_done.txt")]:
        try:
            os.remove(os.path.join(SCRIPTS_DIR, _done_file))
        except Exception:
            pass

# Restore default rendering settings
try:
    _world = unreal.EditorLevelLibrary.get_editor_world()
    for _restore_cmd in (
        "r.Streaming.PoolSize 0",
        "r.Lumen.DiffuseIndirect.Allow 1",
        "r.Lumen.Reflections.Allow 1",
        "r.Shadow.Virtual.Enable 1",
        "r.Nanite.MaxAllocatedPages 0",
        "r.Nanite.Streaming.MaxPendingPages 128",
        "r.AllowCachedUniformExpressions 1",
    ):
        try:
            unreal.KismetSystemLibrary.execute_console_command(_world, _restore_cmd)
        except Exception:
            pass
    print("Rendering settings restored (Lumen, VSM, Nanite pools)")
except Exception:
    pass
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
