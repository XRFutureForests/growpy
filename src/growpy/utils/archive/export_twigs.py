#!/usr/bin/env python3
"""
Simplified twig export from Blender files to FBX format.

This script processes .blend files containing twig assets and exports each twig
as an individual FBX file with materials, textures, and any available bones.

Usage:
    python export_twigs.py                    # Auto-find twig directories
    python export_twigs.py /path/to/twigs/    # Use specific directory

Features:
- Processes all .blend files in twig directories
- Exports each mesh object as separate FBX
- Preserves materials and textures
- Includes bones/armatures if present
- Auto-searches common twig directory locations
- Supports custom directory specification
- Exports FBX files to same directory as source .blend files
"""

from pathlib import Path
from tqdm import tqdm

from growpy import (
    GrowPyConfig,
    get_config,
    export_twigs_from_blend,
    EXPORT_AVAILABLE,
)


def process_twig_blend_files(blend_files: list) -> None:
    """Process list of blend files and export as FBX to same directories."""
    if not EXPORT_AVAILABLE:
        print("❌ Export not available - bpy module required")
        return

    if not blend_files:
        print("❌ No .blend files found")
        return

    print(f"🌿 Found {len(blend_files)} .blend files to process")

    exported_total = 0
    processed_files = 0

    for blend_file in tqdm(blend_files, desc="Processing blend files"):
        try:
            # Export to same directory as the blend file
            twig_output_dir = blend_file.parent

            # Export all twigs from this blend file
            exported_fbx_files = export_twigs_from_blend(blend_file, twig_output_dir)

            if exported_fbx_files:
                print(f"✅ {blend_file.name}: {len(exported_fbx_files)} twigs exported")
                exported_total += len(exported_fbx_files)
                processed_files += 1
            else:
                print(f"⚠️ {blend_file.name}: No twigs exported")

        except Exception as e:
            print(f"❌ Error processing {blend_file.name}: {e}")
            continue

    print(f"\n🎯 Twig export complete:")
    print(f"   📁 Processed files: {processed_files}/{len(blend_files)}")
    print(f"   🌿 Total twigs exported: {exported_total}")


def find_all_twig_blend_files(config: GrowPyConfig) -> list:
    """Find all twig blend files in common locations."""
    blend_files = []

    # Find blend files in common twig directories
    project_root = Path(__file__).parent.parent.parent.parent

    # Look for twig directories in common locations
    common_twig_paths = [
        project_root / "data" / "assets" / "twigs",
        project_root / "assets" / "twigs",
        project_root / "data" / "twigs",
        project_root / "twigs",
        Path.cwd() / "assets" / "twigs",
        Path.cwd() / "data" / "twigs",
        Path.cwd() / "twigs",
    ]

    print("🔍 Searching for .blend files in:")
    for path in common_twig_paths:
        print(f"   📁 {path}")
        if path.exists():
            found_blends = list(path.glob("**/*.blend"))
            if found_blends:
                blend_files.extend(found_blends)
                print(f"   ✅ Found {len(found_blends)} .blend files")
            else:
                print(f"   ⚠️ Directory exists but no .blend files found")
        else:
            print(f"   ❌ Directory does not exist")

    # Also try to get from config if possible
    try:
        # Get all available species and look for their twig directories
        species_list = config.get_available_species()
        for species in species_list:
            try:
                twig_dir = config.get_twig_directory_path(species)
                if twig_dir and twig_dir.exists():
                    found_blends = list(twig_dir.glob("**/*.blend"))
                    if found_blends:
                        blend_files.extend(found_blends)
                        print(f"   ✅ Found {len(found_blends)} .blend files for {species}")
            except Exception:
                continue
    except Exception as e:
        print(f"⚠️ Could not check config for twig directories: {e}")

    return blend_files


def find_custom_twig_blend_files(twig_dir: Path) -> list:
    """Find blend files in a specific directory."""
    return list(twig_dir.glob("**/*.blend"))


def main():
    """Main twig export function."""
    import sys

    try:
        config = get_config()

        # Check for custom twig directory argument
        if len(sys.argv) > 1:
            custom_twig_dir = Path(sys.argv[1])
            if not custom_twig_dir.exists():
                print(f"❌ Custom twig directory not found: {custom_twig_dir}")
                return
            print(f"🎯 Using custom twig directory: {custom_twig_dir}")
            blend_files = find_custom_twig_blend_files(custom_twig_dir)
        else:
            blend_files = find_all_twig_blend_files(config)

        print("🌿 Starting FBX twig export...")
        process_twig_blend_files(blend_files)

    except Exception as e:
        print(f"❌ Export failed: {e}")


if __name__ == "__main__":
    main()