#!/usr/bin/env python3
"""Generate species library - export template trees for each configured species.

Usage:
    python generate_species_library.py
"""

from pathlib import Path
from tqdm import tqdm

try:
    import the_grove_22_core as gc
except ImportError:
    gc = None

from growpy import (
    GrowPyConfig,
    get_config,
    create_grove,
    export_tree_as_usd,
    EXPORT_AVAILABLE,
)


def place_twigs_on_species_library(
    tree_usd_files: list,
    twigs_dir: Path,
    output_dir: Path
) -> None:
    """Place twigs on exported species library USD files.

    Args:
        tree_usd_files: List of tree USD file paths
        twigs_dir: Directory containing twig files
        output_dir: Output directory for tree+twig assemblies
    """
    import bpy
    from growpy.io.twig_placement import export_twig_placements_to_usd

    twigs_output = output_dir / "with_twigs"
    twigs_output.mkdir(parents=True, exist_ok=True)

    for tree_file in tree_usd_files:
        try:
            species_name = tree_file.stem

            # Look for twig directory matching species
            twig_candidates = list(twigs_dir.glob(f"*{species_name}*Twig"))
            if not twig_candidates:
                # Try without species name
                twig_candidates = list(twigs_dir.glob("*Twig"))

            if not twig_candidates:
                print(f"  No twig found for {species_name}, skipping")
                continue

            twig_dir = twig_candidates[0]
            print(f"  {species_name}: using {twig_dir.name}")

            # Find twig USD files
            twig_files = list(twig_dir.glob("*.usda")) + list(twig_dir.glob("*.usd"))
            if not twig_files:
                print(f"    No USD twigs found")
                continue

            # Load tree to extract placement data
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.wm.usd_import(filepath=str(tree_file))

            tree_obj = None
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH':
                    tree_obj = obj
                    break

            if not tree_obj:
                print(f"    No mesh found")
                continue

            # Map twig types to USD files
            twig_usd_map = {}
            for twig_file in twig_files:
                name_lower = twig_file.stem.lower()
                if 'end' in name_lower or 'long' in name_lower:
                    twig_usd_map['twig_long'] = twig_file
                elif 'side' in name_lower or 'short' in name_lower:
                    twig_usd_map['twig_short'] = twig_file
                else:
                    # Use generic twig for all types
                    twig_usd_map['twig_long'] = twig_file
                    twig_usd_map['twig_short'] = twig_file
                    break

            if not twig_usd_map:
                print(f"    Could not map twig types")
                continue

            # Export assembly with twigs
            output_file = twigs_output / f"{species_name}_with_twigs.usda"
            if export_twig_placements_to_usd(tree_file, twig_usd_map, output_file, tree_obj):
                print(f"    Created: {output_file.name}")

        except Exception as e:
            print(f"  Failed for {tree_file.name}: {e}")
            continue


def export_all_species(
    config: GrowPyConfig,
    output_dir: Path,
    growth_flushes: int = 10,
    formats: list = ['usda'],
    place_twigs: bool = False,
    twigs_dir: Path = None
) -> None:
    """Export all configured species as template trees in USD format.

    Args:
        config: GrowPy configuration with species settings
        output_dir: Directory to save export files
        growth_flushes: Number of growth cycles to simulate
        formats: List of export formats ('usd', 'usda')
        place_twigs: Whether to place twig instances on trees (default: False)
        twigs_dir: Directory containing twig files (default: config.twigs_path)
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
    exported_files = []

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

            # Export in requested formats
            format_success = False

            usd_ext = 'usda' if 'usda' in formats else 'usd'
            usd_path = output_dir / f"{species_clean}.{usd_ext}"
            if export_tree_as_usd(grove, usd_path, species, include_skeleton=True):
                format_success = True
                exported_files.append(usd_path)

            if format_success:
                exported_count += 1
            else:
                failed_count += 1

        except Exception:
            failed_count += 1
            continue

    print(f"Export complete: {exported_count} successful, {failed_count} failed")

    # Place twigs if requested
    if place_twigs and exported_files:
        try:
            import bpy

            # Use provided twigs directory or config default
            if twigs_dir is None:
                twigs_dir = Path(config.twigs_path) if hasattr(config, 'twigs_path') else None

            if twigs_dir and twigs_dir.exists():
                print(f"\nPlacing twigs from: {twigs_dir}")
                place_twigs_on_species_library(exported_files, twigs_dir, output_dir)
            else:
                print(f"Warning: Twigs directory not found: {twigs_dir}")
                print("Skipping twig placement")
        except ImportError:
            print("Warning: bpy not available, skipping twig placement")
        except Exception as e:
            print(f"Warning: Twig placement failed: {e}")


def main():
    """Main export function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate species library - export template trees for all configured species",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Export all species with default settings (10 flushes, USDA)
    python generate_species_library.py

    # Export with custom growth flushes
    python generate_species_library.py --flushes 15

    # Export to USD binary format
    python generate_species_library.py --formats usd

    # Export with custom output directory
    python generate_species_library.py --output-dir data/output/species
        """
    )

    parser.add_argument(
        "--flushes",
        type=int,
        default=10,
        help="Number of growth flushes to simulate (default: 10)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output/species_library"),
        help="Directory to save species library (default: data/output/species_library)"
    )
    parser.add_argument(
        "--formats",
        nargs='+',
        choices=['usd', 'usda'],
        default=['usda'],
        help="Export formats (default: usda)"
    )
    parser.add_argument(
        "--place-twigs",
        action='store_true',
        help="Place twig instances on exported trees (requires twigs directory)"
    )
    parser.add_argument(
        "--twigs-dir",
        type=Path,
        default=None,
        help="Directory containing twig files (default: from config)"
    )

    args = parser.parse_args()

    try:
        config = get_config()
        export_all_species(
            config,
            args.output_dir,
            args.flushes,
            args.formats,
            args.place_twigs,
            args.twigs_dir
        )
    except Exception as e:
        print(f"Export failed: {e}")


if __name__ == "__main__":
    main()