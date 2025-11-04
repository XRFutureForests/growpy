#!/usr/bin/env python3
"""
Generate Unreal Engine cleanup script for GrowPy imported assets.

Creates a standalone Python script that can be executed in Unreal Engine to clean
imported GrowPy tree assets from the Content Browser.

Quick Start:
    # Generate cleanup script for default location
    python src/growpy/cli/clean_unreal_assets.py

    # Generate for custom location
    python src/growpy/cli/clean_unreal_assets.py --unreal-project-path /Game/MyProject/Trees

    # Generate dry-run script (preview only, no deletion)
    python src/growpy/cli/clean_unreal_assets.py --dry-run

Usage:
    python src/growpy/cli/clean_unreal_assets.py [--unreal-project-path PATH] [--dry-run]
"""

import sys
from pathlib import Path


def generate_unreal_cleanup_script(
    project_path: str = "/Game/GrowPy/Trees",
    dry_run: bool = False,
    output_path: Path = None,
) -> Path:
    """
    Generate a standalone Unreal Python script for cleaning GrowPy assets.

    Args:
        project_path: Unreal project Content path to clean
        dry_run: If True, generates preview-only script
        output_path: Where to save script (default: src/growpy/io/unreal_scripts/clean_assets_generated.py)

    Returns:
        Path to generated script file
    """
    if output_path is None:
        script_dir = Path(__file__).parent.parent / "io" / "unreal_scripts"
        script_dir.mkdir(parents=True, exist_ok=True)
        output_path = script_dir / "clean_assets_generated.py"

    # Generate script content with forward slashes to avoid Unicode escape errors
    output_path_str = str(output_path).replace("\\", "/")

    script_content = f'''"""
Unreal Engine cleanup script for GrowPy assets - Auto-generated

Execute this script in Unreal Engine:
1. Right-click this file in VSCode > "Execute Python File in Unreal"
2. Or from Unreal Python console: exec(open(r'{output_path_str}').read())
"""

import unreal

print("=" * 60)
print("GrowPy Asset Cleanup")
print("=" * 60)

# Cleanup configuration
CLEANUP_PATH = "{project_path}"
DRY_RUN = {str(dry_run)}

print(f"Target path: {{CLEANUP_PATH}}")

if DRY_RUN:
    print("\\n*** DRY RUN MODE - No assets will be deleted ***\\n")
else:
    print("\\n*** LIVE MODE - Assets will be permanently deleted ***\\n")

# Get asset registry
asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()

# Find all assets in target path
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
        editor_asset_lib = unreal.EditorAssetLibrary()
        deleted_count = 0
        failed_count = 0
        
        for asset in assets:
            asset_path = str(asset.package_name)
            asset_name = str(asset.asset_name)
            
            try:
                if editor_asset_lib.delete_asset(asset_path):
                    deleted_count += 1
                    unreal.log(f"✓ Deleted {{asset_name}}")
                else:
                    failed_count += 1
                    unreal.log_warning(f"✗ Failed to delete: {{asset_name}}")
            except Exception as e:
                failed_count += 1
                unreal.log_error(f"✗ Error deleting {{asset_name}}: {{e}}")
        
        print("")
        print("=" * 60)
        print(f"Cleanup complete: {{deleted_count}} deleted, {{failed_count}} failed")
        print("=" * 60)
        
        if failed_count > 0:
            unreal.log_warning("Some assets could not be deleted. They may be in use.")
        else:
            print(f"\\nAll assets removed from: {{CLEANUP_PATH}}")
'''

    # Write script file
    output_path.write_text(script_content, encoding="utf-8")

    return output_path


def main():
    """Main cleanup script generator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Unreal Engine cleanup script for GrowPy assets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate cleanup script for default location
    python src/growpy/cli/clean_unreal_assets.py

    # Generate for custom location
    python src/growpy/cli/clean_unreal_assets.py --unreal-project-path /Game/MyProject/Trees

    # Generate dry-run script (preview only)
    python src/growpy/cli/clean_unreal_assets.py --dry-run

    # Custom output location
    python src/growpy/cli/clean_unreal_assets.py --output-path my_cleanup.py

How to use generated script:
    1. Open the generated script in VSCode
    2. Right-click > "Execute Python File in Unreal"
    3. Or run in Unreal Python console

Requirements:
    - VSCode with Unreal Python extension
    - Editor Scripting Utilities plugin enabled in Unreal
        """,
    )

    parser.add_argument(
        "--unreal-project-path",
        type=str,
        default="/Game/GrowPy/Trees",
        help="Unreal project Content path to clean (default: /Game/GrowPy/Trees)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate preview-only script (no deletion)",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Where to save script (default: src/growpy/io/unreal_scripts/clean_assets_generated.py)",
    )

    args = parser.parse_args()

    try:
        script_path = generate_unreal_cleanup_script(
            args.unreal_project_path,
            args.dry_run,
            args.output_path,
        )

        print("\n" + "=" * 60)
        print("UNREAL CLEANUP SCRIPT GENERATED")
        print("=" * 60)
        print(f"Script saved to: {script_path}")
        print(f"Target path: {args.unreal_project_path}")

        if args.dry_run:
            print("Mode: DRY RUN (preview only)")
        else:
            print("Mode: LIVE (will delete assets)")

        print("\nTo execute in Unreal Engine:")
        print("1. Open the script file in VSCode")
        print("2. Right-click > 'Execute Python File in Unreal'")
        print("3. Or run in Unreal Python console:")
        print(f"   exec(open(r'{script_path}').read())")
        print("\nRequirements:")
        print("- Unreal Engine must be running")
        print("- Editor Scripting Utilities plugin enabled")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
