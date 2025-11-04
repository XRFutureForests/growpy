"""
Unreal Engine script to clean GrowPy imported assets.

This script should be executed directly in Unreal Engine using:
- VSCode Unreal Python extension (right-click > Execute in Unreal)
- Unreal Editor Python console
- Command line: UnrealEditor-Cmd.exe <project> -run=pythonscript -script=<path>

Usage:
    1. Update CLEANUP_PATH below
    2. Set DRY_RUN = True to preview deletions without deleting
    3. Right-click this file in VSCode > "Execute Python File in Unreal"

    Or from Unreal Python console:
    exec(open(r'C:/path/to/clean_assets.py').read())
"""

import unreal

# ============================================================================
# CONFIGURATION - UPDATE THESE SETTINGS
# ============================================================================

# Unreal Content Browser path to clean
CLEANUP_PATH = "/Game/GrowPy/Trees"

# Dry run mode - set to True to preview without deleting
DRY_RUN = False

# ============================================================================
# CLEANUP LOGIC
# ============================================================================

print("=" * 60)
print("GrowPy Asset Cleanup")
print("=" * 60)
print(f"Target path: {CLEANUP_PATH}")

if DRY_RUN:
    print("\n*** DRY RUN MODE - No assets will be deleted ***\n")
else:
    print("\n*** LIVE MODE - Assets will be permanently deleted ***\n")

# Get asset registry
asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()

# Find all assets in target path
assets = asset_registry.get_assets_by_path(CLEANUP_PATH, recursive=True)

if not assets:
    print(f"No assets found at {CLEANUP_PATH}")
else:
    print(f"Found {len(assets)} assets at {CLEANUP_PATH}\n")

    if DRY_RUN:
        # Dry run - just list assets
        print("Assets that would be deleted:\n")
        for asset in assets:
            asset_path = str(asset.package_name)
            asset_name = str(asset.asset_name)
            asset_class = str(asset.asset_class_path.asset_name)

            print(f"  {asset_class}: {asset_name}")
            print(f"    Path: {asset_path}")

        print("\n" + "=" * 60)
        print("DRY RUN COMPLETE")
        print("=" * 60)
        print("Set DRY_RUN = False to perform actual deletion")

    else:
        # Real cleanup - delete assets
        print("Deleting assets...\n")
        editor_asset_lib = unreal.EditorAssetLibrary()
        deleted_count = 0
        failed_count = 0

        for asset in assets:
            asset_path = str(asset.package_name)
            asset_name = str(asset.asset_name)

            try:
                if editor_asset_lib.delete_asset(asset_path):
                    deleted_count += 1
                    unreal.log(f"✓ Deleted {asset_name}")
                else:
                    failed_count += 1
                    unreal.log_warning(f"✗ Failed to delete: {asset_name}")
            except Exception as e:
                failed_count += 1
                unreal.log_error(f"✗ Error deleting {asset_name}: {e}")

        print("")
        print("=" * 60)
        print(f"Cleanup complete: {deleted_count} deleted, {failed_count} failed")
        print("=" * 60)

        if failed_count > 0:
            unreal.log_warning("Some assets could not be deleted. They may be in use.")
        else:
            print(f"\nAll assets removed from: {CLEANUP_PATH}")
