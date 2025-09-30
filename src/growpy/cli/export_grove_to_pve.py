#!/usr/bin/env python3
"""Export Grove trees to Unreal Engine PVE JSON format.

Usage:
    python export_grove_to_pve.py --species "European beech" --cycles 10 --output output/beech_pve.json
"""

from pathlib import Path
import argparse

from growpy import create_grove, get_config
from growpy.utils.grove_to_pve_converter import export_grove_to_pve


def main():
    """Main export function."""
    parser = argparse.ArgumentParser(
        description="Export Grove tree to Unreal Engine PVE JSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Export single species with 10 growth cycles
    python export_grove_to_pve.py --species "European beech" --cycles 10 --output output/beech.json

    # Export multiple species
    python export_grove_to_pve.py --species "European oak" --cycles 15 --output output/oak.json
    python export_grove_to_pve.py --species "Silver fir" --cycles 12 --output output/fir.json

    # Export with custom parameters
    python export_grove_to_pve.py --species "Hazel" --cycles 8 --gravity 1.3 --output output/hazel.json
        """
    )

    parser.add_argument(
        "--species",
        type=str,
        required=True,
        help="Tree species name (must match species in lookup table)"
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=10,
        help="Number of growth cycles to simulate (default: 10)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--gravity",
        type=float,
        default=None,
        help="Gravity force (optional, overrides preset)"
    )
    parser.add_argument(
        "--phototropism",
        type=float,
        default=None,
        help="Phototropism strength (optional, overrides preset)"
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )

    args = parser.parse_args()

    try:
        config = get_config()
        config.random_seed = args.random_seed

        print(f"Creating Grove for species: {args.species}")
        grove = create_grove(args.species)

        print(f"Simulating {args.cycles} growth cycles...")
        grove.simulate(flushes=args.cycles)

        # Prepare properties to export
        grove_properties = {
            'growth_cycles': args.cycles,
            'random_seed': args.random_seed,
        }

        if args.gravity is not None:
            grove_properties['gravity_force'] = args.gravity

        if args.phototropism is not None:
            grove_properties['phototropism'] = args.phototropism

        print(f"Exporting to PVE JSON: {args.output}")
        if export_grove_to_pve(grove, args.species, args.output, grove_properties):
            print(f"Successfully exported to {args.output}")

            # Print statistics
            import json
            with open(args.output) as f:
                data = json.load(f)
                point_count = len(data['points']['positions'])
                polyline_count = len(data['primitives']['points'])
                print(f"\nExport statistics:")
                print(f"  Points: {point_count}")
                print(f"  Polylines (branches): {polyline_count}")
        else:
            print("Export failed")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()