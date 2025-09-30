#!/usr/bin/env python3
"""
Simplified tree export using FBX format.

This script exports Grove tree models as FBX files with mesh, skeleton, and materials.
No complex USD handling, positioning issues, or LOD variants - just clean FBX export.

Usage:
    python export_trees_fbx.py

Features:
- Single high-quality FBX export per species
- Grove mesh + skeleton integration
- Simple material assignment
- Batch processing for multiple species
"""

from pathlib import Path
from tqdm import tqdm

from growpy import (
    GrowPyConfig,
    get_config,
    create_grove,
    export_tree_as_fbx,
    EXPORT_AVAILABLE,
)
from growpy.common import gc


def export_all_species_as_fbx(
    config: GrowPyConfig,
    output_dir: Path,
    growth_flushes: int = 10
) -> None:
    """Export all configured species as individual FBX files.

    Args:
        config: GrowPy configuration with species settings
        output_dir: Directory to save FBX files
        growth_flushes: Number of growth cycles to simulate
    """
    if not EXPORT_AVAILABLE:
        print("❌ Export not available - bpy module required")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get all available species from config
    species_list = config.get_all_species()

    if not species_list:
        print("❌ No species found in configuration")
        return

    print(f"🌳 Exporting {len(species_list)} species as FBX...")

    exported_count = 0
    failed_count = 0

    for species in tqdm(species_list, desc="Exporting species"):
        try:
            # Create grove for this species
            grove = create_grove(species)

            # Add single tree at origin
            grove.add_new_tree(
                gc.Vector(0, 0, 0),  # Origin
                gc.Vector(0, 0, 1),  # Up direction
                0  # No delay
            )

            # Simulate realistic growth
            grove.simulate(flushes=growth_flushes)

            # Clean species name for filename
            species_clean = "".join(c for c in species if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
            if not species_clean:
                species_clean = f"species_{exported_count}"

            fbx_path = output_dir / f"{species_clean}.fbx"

            # Export as FBX with skeleton
            if export_tree_as_fbx(grove, fbx_path, species, include_skeleton=True):
                print(f"✅ Exported: {fbx_path}")
                exported_count += 1
            else:
                print(f"❌ Failed to export: {species}")
                failed_count += 1

        except Exception as e:
            print(f"❌ Error processing {species}: {e}")
            failed_count += 1
            continue

    print(f"\n🎯 Export complete:")
    print(f"   ✅ Successful: {exported_count}")
    print(f"   ❌ Failed: {failed_count}")


def main():
    """Main export function."""
    try:
        config = get_config()

        # Set output directory
        output_dir = Path("output/trees_fbx")

        print("🌲 Starting FBX tree export...")
        export_all_species_as_fbx(config, output_dir)

    except Exception as e:
        print(f"❌ Export failed: {e}")


if __name__ == "__main__":
    main()