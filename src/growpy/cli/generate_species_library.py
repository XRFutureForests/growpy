#!/usr/bin/env python3
"""Tree export using FBX format.

Usage:
    python export_trees.py
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
from growpy.utils.dependencies import gc


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
        print("Export not available - bpy module required")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    species_list = config.get_all_species()

    if not species_list:
        print("No species found in configuration")
        return

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
                exported_count += 1
            else:
                failed_count += 1

        except Exception:
            failed_count += 1
            continue

    print(f"Export complete: {exported_count} successful, {failed_count} failed")


def main():
    """Main export function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Export Grove tree species as FBX files with mesh, skeleton, and materials",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Export all species with default settings (10 growth cycles)
    python export_trees.py

    # Export with custom growth cycles and output directory
    python export_trees.py --cycles 15 --output-dir output/my_trees
        """
    )

    parser.add_argument(
        "--cycles",
        type=int,
        default=10,
        help="Number of growth cycles to simulate (default: 10)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/trees_fbx"),
        help="Directory to save FBX files (default: output/trees_fbx)"
    )

    args = parser.parse_args()

    try:
        config = get_config()
        export_all_species_as_fbx(config, args.output_dir, args.cycles)
    except Exception as e:
        print(f"Export failed: {e}")


if __name__ == "__main__":
    main()