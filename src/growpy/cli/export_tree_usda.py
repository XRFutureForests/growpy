#!/usr/bin/env python3
"""
Export Grove trees as USDA with twig point instances.

This script demonstrates the new native USD export functionality that:
1. Uses Grove's native model_to_usda_string() for the base tree
2. Extracts twig placement data from the USD
3. Adds twigs as PointInstancer prims for memory-efficient instancing
4. Follows Grove documentation for twig orientation

Usage:
    python export_tree_usda.py <species_name> [--output OUTPUT_PATH] [--no-twigs]

Examples:
    # Export European Beech with twigs
    python export_tree_usda.py "European Beech" --output beech_tree.usda

    # Export Scots Pine without twigs
    python export_tree_usda.py "Scots Pine" --no-twigs
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Export Grove tree as USDA with twig point instances",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Export with twigs (default)
    python export_tree_usda.py "European Beech"

    # Export without twigs
    python export_tree_usda.py "European Beech" --no-twigs

    # Specify output path
    python export_tree_usda.py "Scots Pine" --output pine.usda

    # Adjust quality settings
    python export_tree_usda.py "European Beech" --resolution 16 --flushes 8
        """,
    )

    parser.add_argument(
        "species",
        type=str,
        help="Tree species name (e.g., 'European Beech', 'Scots Pine')",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output USDA file path (default: <species_name>.usda)",
    )
    parser.add_argument(
        "--no-twigs",
        action="store_true",
        help="Don't include twigs in the export",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=24,
        help="Branch resolution (vertices around circumference, 4-32, default: 24)",
    )
    parser.add_argument(
        "--flushes",
        type=int,
        default=10,
        help="Number of growth flushes (default: 10)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output/usd"),
        help="Output directory (default: data/output/usd)",
    )
    parser.add_argument(
        "--nanite-assembly",
        action="store_true",
        default=True,
        help="Create Nanite Assembly USD for Unreal Engine (default: True)",
    )
    parser.add_argument(
        "--no-nanite-assembly",
        action="store_false",
        dest="nanite_assembly",
        help="Don't create Nanite Assembly USD",
    )

    args = parser.parse_args()

    # Setup paths
    if args.output:
        output_path = args.output
    else:
        species_clean = args.species.replace(" ", "_").lower()
        output_path = args.output_dir / f"{species_clean}_tree.usda"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Grove Tree USD Export")
    print(f"{'='*60}")
    print(f"Species: {args.species}")
    print(f"Output: {output_path}")
    print(f"Resolution: {args.resolution}")
    print(f"Growth flushes: {args.flushes}")
    print(f"Include twigs: {not args.no_twigs}")
    print(f"{'='*60}\n")

    try:
        # Import GrowPy modules
        from growpy import GrowPyConfig, get_config
        from growpy.core.grove import create_grove
        from growpy.io.blender_export import (
            export_grove_tree_as_usda_native,
            get_twig_usd_map_for_species,
        )

        config = get_config()

        # Create and simulate grove
        print("Creating grove...")
        grove = create_grove(args.species)

        # Import grove core for tree creation
        import the_grove_22_core as gc

        grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

        print(f"Simulating {args.flushes} growth flushes...")
        grove.simulate(flushes=args.flushes)

        # Get twig USD paths if including twigs
        twig_usd_map = None
        if not args.no_twigs:
            print("Finding twig USD files...")
            twig_usd_map = get_twig_usd_map_for_species(args.species, config)

            if twig_usd_map:
                print(f"  Found {len(twig_usd_map)} twig types:")
                for twig_type, twig_path in twig_usd_map.items():
                    print(f"    - {twig_type}: {twig_path.name}")
            else:
                print(
                    f"  Warning: No twig USD files found for {args.species}"
                )
                print("  Continuing without twigs...")

        # Export tree as USDA
        print("\nExporting tree...")
        success = export_grove_tree_as_usda_native(
            grove=grove,
            output_path=output_path,
            species_name=args.species,
            twig_usd_paths=twig_usd_map,
            include_twigs=(not args.no_twigs and twig_usd_map is not None),
            use_point_instancer=True,
            convert_to_ue=True,
            create_nanite_assembly=args.nanite_assembly,
            resolution=args.resolution,
            resolution_reduce=0.8,
            texture_repeat=3,
            build_cutoff_age=0,
            build_cutoff_thickness=0.0,
            build_blend=True,
            build_end_cap=True,
        )

        if success:
            print(f"\n{'='*60}")
            print("✓ Export Complete!")
            print(f"{'='*60}")
            print(f"Output file: {output_path}")
            print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")

            if not args.no_twigs and twig_usd_map:
                print(f"\nTwig USD files used:")
                for twig_type, twig_path in twig_usd_map.items():
                    print(f"  - {twig_type}: {twig_path}")

            print(f"\nImport in Unreal Engine:")
            print(f"  1. Enable Nanite on import")
            print(f"  2. Use 'Keep Instances' for twig instances")
            print(f"  3. Verify twig orientations point outward")
            print()

            return 0
        else:
            print("\n✗ Export failed")
            return 1

    except ImportError as e:
        print(f"\n✗ Error: Missing dependencies")
        print(f"  {e}")
        print(f"\nMake sure you have:")
        print(f"  - Grove core installed")
        print(f"  - USD Python (usd-core) installed")
        return 1

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
