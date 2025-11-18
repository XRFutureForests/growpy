#!/usr/bin/env python3
"""
Generate DynamicWind JSON files for tree exports.

Usage:
    # Generate for all trees in a species directory
    python src/growpy/cli/generate_wind_json.py data/output/forest/european_beech/

    # Generate for a single tree
    python src/growpy/cli/generate_wind_json.py data/output/forest/european_beech/european_beech_tree_0000_skeletal.usda

    # Specify skeleton data explicitly
    python src/growpy/cli/generate_wind_json.py tree.usda --skeleton-data skeleton_data.txt
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from growpy.io.wind_json import generate_wind_json, generate_wind_json_for_species


def main():
    parser = argparse.ArgumentParser(
        description="Generate DynamicWind JSON files for Unreal Engine skeletal tree meshes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "input_path",
        type=Path,
        help="Path to skeletal USD file or directory containing tree USD files",
    )

    parser.add_argument(
        "--skeleton-data",
        type=Path,
        help="Path to skeleton_data.txt (optional, auto-detected if in grove_geometry_dump)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for JSON file (default: same directory as input with _DynamicWind.json suffix)",
    )

    parser.add_argument(
        "--tree-prefix",
        default="tree",
        help="Prefix for tree files when processing directory (default: 'tree')",
    )

    args = parser.parse_args()

    input_path = args.input_path.resolve()

    if not input_path.exists():
        print(f"Error: Input path does not exist: {input_path}")
        sys.exit(1)

    try:
        # Directory: process all skeletal USD files
        if input_path.is_dir():
            print(f"Processing directory: {input_path}")
            generated_files = generate_wind_json_for_species(
                species_output_dir=input_path,
                tree_prefix=args.tree_prefix,
            )

            if generated_files:
                print(
                    f"\n✓ Successfully generated {len(generated_files)} wind JSON files"
                )
            else:
                print(
                    "\n⚠ No wind JSON files generated. Check that directory contains *_skeletal.usda files."
                )
                sys.exit(1)

        # Single file: process one USD
        else:
            print(f"Processing file: {input_path.name}")

            # Determine output path
            output_path = args.output
            if not output_path:
                stem = input_path.stem.replace("_skeletal", "")
                output_path = input_path.parent / f"{stem}_DynamicWind.json"

            # Generate wind JSON
            generate_wind_json(
                tree_usd_path=input_path,
                skeleton_data_path=args.skeleton_data,
                output_path=output_path,
            )

            print(f"✓ Generated: {output_path}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
