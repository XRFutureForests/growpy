"""
Unreal Engine script to import GrowPy forest USD files.

This script should be executed directly in Unreal Engine using:
- VSCode Unreal Python extension (right-click > Execute in Unreal)
- Unreal Editor Python console
- Command line: UnrealEditor-Cmd.exe <project> -run=pythonscript -script=<path>

Usage:
    1. Update USD_FILES_DIR and IMPORT_PATH below
    2. Right-click this file in VSCode > "Execute Python File in Unreal"

    Or from Unreal Python console:
    exec(open(r'C:/path/to/import_forest.py').read())
"""

import unreal

# ============================================================================
# CONFIGURATION - UPDATE THESE PATHS
# ============================================================================

# Directory containing exported USD files
USD_FILES_DIR = r"C:\Users\Maximilian Sperlich\Git\the-grove\data\output\forest"

# Unreal Content Browser destination path
IMPORT_PATH = "/Game/GrowPy/Trees"

# ============================================================================
# IMPORT LOGIC
# ============================================================================

print("=" * 60)
print("GrowPy Forest Import to Unreal Engine")
print("=" * 60)
print(f"Source: {USD_FILES_DIR}")
print(f"Destination: {IMPORT_PATH}")
print("")

# Find all Nanite Assembly USD files
import os
from pathlib import Path

usd_dir = Path(USD_FILES_DIR)
nanite_files = list(usd_dir.glob("**/*nanite_assembly.usda")) + list(
    usd_dir.glob("**/*nanite_assembly.usd")
)

if not nanite_files:
    print(f"ERROR: No Nanite Assembly USD files found in {USD_FILES_DIR}")
    print("Looking for files matching: *nanite_assembly.usda or *nanite_assembly.usd")
else:
    print(f"Found {len(nanite_files)} Nanite Assembly USD files to import\n")

    # Configure USD import options
    options = unreal.UsdStageImportOptions()
    options.import_actors = False  # Don't spawn actors in level
    options.import_geometry = True
    options.import_materials = True

    # Get asset tools
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

    imported_count = 0
    failed_count = 0

    # Import each USD file
    for usd_file in nanite_files:
        asset_name = usd_file.stem
        usd_path = str(usd_file.resolve()).replace("\\", "/")

        try:
            unreal.log(f"Importing {asset_name}...")

            task = unreal.AssetImportTask()
            task.filename = usd_path
            task.destination_path = IMPORT_PATH
            task.replace_existing = True
            task.automated = True
            task.save = True
            task.factory = unreal.UsdStageImporterFactory()
            task.options = options

            asset_tools.import_asset_tasks([task])

            if task.imported_object_paths:
                imported_count += 1
                unreal.log(f"✓ Imported {asset_name}")
            else:
                failed_count += 1
                unreal.log_warning(f"✗ Failed to import {asset_name}")
        except Exception as e:
            failed_count += 1
            unreal.log_error(f"✗ Error importing {asset_name}: {e}")

    print("")
    print("=" * 60)
    print(f"Import complete: {imported_count} succeeded, {failed_count} failed")
    print("=" * 60)

    if failed_count > 0:
        unreal.log_warning(
            "Some imports failed. Check that USD Importer plugin is enabled."
        )
    else:
        print(f"\nAssets imported to Content Browser: {IMPORT_PATH}")
        print("Trees are ready to place in level or use with PCG")
