#!/usr/bin/env python3
"""Export USDA tree assemblies to OBJ/MTL for Helios++ LiDAR simulation.

Converts previously generated USDA assemblies (from generate_forest.py) to
Wavefront OBJ with baked twig instances and Helios++ material extensions.
Optionally generates a Helios++ scene XML with tree positions from the CSV.

Usage:
    python src/growpy/cli/export_obj.py data/input/test_single.csv
    python src/growpy/cli/export_obj.py data/input/test.csv --decimate-ratio 0.5
    python src/growpy/cli/export_obj.py data/input/test.csv --helios-scene
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

CONIFER_KEYWORDS = [
    "spruce",
    "pine",
    "fir",
    "cedar",
    "cypress",
    "juniper",
    "larch",
    "hemlock",
    "yew",
    "redwood",
    "sequoia",
    "thuja",
]


def main():
    project_root = Path(os.environ.get("GROWPY_PROJECT_ROOT", Path(__file__).parent.parent.parent.parent))
    default_csv = project_root / "data" / "input" / "test.csv"
    default_output = project_root / "data" / "output" / "forest"

    parser = argparse.ArgumentParser(
        description="Export USDA tree assemblies to OBJ/MTL for Helios++ LiDAR simulation",
    )
    parser.add_argument(
        "csv_file",
        type=Path,
        nargs="?",
        default=default_csv,
        help=f"Input CSV file with tree positions and species (default: {default_csv})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help=f"Forest output directory containing USDA assemblies (default: {default_output})",
    )
    parser.add_argument(
        "--decimate-ratio",
        type=float,
        default=0.3,
        help="Twig decimation ratio (0.0-1.0, lower = fewer polygons, default: 0.3)",
    )
    parser.add_argument(
        "--helios-scene",
        action="store_true",
        help="Generate Helios++ scene XML placing all tree OBJs at CSV positions",
    )

    args = parser.parse_args()

    if not args.csv_file.exists():
        print(f"Error: CSV file not found: {args.csv_file}")
        sys.exit(1)

    if not args.output_dir.exists():
        print(f"Error: Output directory not found: {args.output_dir}")
        sys.exit(1)

    from growpy.io.obj_export import clear_twig_decimate_cache, convert_tree_to_obj

    clear_twig_decimate_cache()

    # Find all assembly USDA files (matching _assembly naming convention)
    assembly_files = [usda for usda in args.output_dir.glob("*/tree_*/*_assembly.usda")]

    if not assembly_files:
        print("No assembly USDA files found in output directory")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"HELIOS OBJ EXPORT ({len(assembly_files)} trees)")
    print(f"{'='*60}")

    forest_data = pd.read_csv(args.csv_file)
    if "fid" not in forest_data.columns:
        forest_data["fid"] = range(1, len(forest_data) + 1)
    if "z" not in forest_data.columns:
        forest_data["z"] = 0.0

    obj_files = []
    for assembly_path in sorted(assembly_files):
        tree_dir_name = assembly_path.parent.name
        tree_id_str = tree_dir_name.replace("tree_", "")

        species_dir = assembly_path.parent.parent.name
        species_name = species_dir.replace("_", " ").title()

        is_conifer = any(kw in species_dir.lower() for kw in CONIFER_KEYWORDS)
        spectra = "conifer" if is_conifer else "deciduous"

        obj_path = convert_tree_to_obj(
            assembly_usda_path=assembly_path,
            species_name=species_name,
            decimate_ratio=args.decimate_ratio,
            helios_spectra_leaves=spectra,
        )

        if obj_path:
            try:
                fid = int(tree_id_str)
                row = forest_data[forest_data["fid"] == fid].iloc[0]
                obj_files.append(
                    (
                        obj_path,
                        float(row["x"]),
                        float(row["y"]),
                        float(row["z"]),
                        species_name,
                    )
                )
            except (ValueError, IndexError):
                obj_files.append((obj_path, 0.0, 0.0, 0.0, species_name))

    if args.helios_scene and obj_files:
        from growpy.io.helios_scene import generate_helios_scene

        scene_path = args.output_dir / "helios_scene.xml"
        generate_helios_scene(tree_entries=obj_files, output_path=scene_path)

    print(f"\nOBJ export complete: {len(obj_files)} trees converted")


if __name__ == "__main__":
    main()
