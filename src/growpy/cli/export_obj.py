#!/usr/bin/env python3
"""Export USDA tree assemblies to OBJ/MTL for Helios++ LiDAR simulation.

Step 5 of the pipeline. Defaults from growpy.toml [helios]. See docs/cli-reference.md.
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
    from growpy.config import get_config

    config = get_config()

    project_root = Path(
        os.environ.get(
            "GROWPY_PROJECT_ROOT", Path(__file__).parent.parent.parent.parent
        )
    )

    parser = argparse.ArgumentParser(
        description="Export USDA tree assemblies to OBJ/MTL for Helios++ LiDAR simulation",
    )
    parser.add_argument(
        "csv_file",
        type=Path,
        nargs="?",
        default=None,
        help="Input CSV file with tree positions and species (default: from config)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Forest output directory containing USDA assemblies (default: from config)",
    )
    parser.add_argument(
        "--twig-decimate-ratio",
        type=float,
        default=None,
        help="Twig decimation ratio (0.0-1.0, lower = fewer polygons, default: from config)",
    )
    parser.add_argument(
        "--stem-decimate-ratio",
        type=float,
        default=None,
        help="Stem/branch decimation ratio (0.0-1.0, lower = fewer polygons, default: from config)",
    )
    parser.add_argument(
        "--helios-scene",
        action="store_true",
        default=None,
        help="Generate Helios++ scene XML placing all tree OBJs at CSV positions",
    )
    parser.add_argument(
        "--combined-obj",
        action="store_true",
        default=None,
        help="Export a single combined OBJ with all trees positioned at CSV coordinates",
    )

    args = parser.parse_args()

    # Resolve config: TOML defaults + CLI overrides
    config.resolve(args)

    # Resolve paths
    csv_path = config.csv_file
    if args.csv_file is not None:
        csv_path = args.csv_file
    elif not csv_path.is_absolute():
        csv_path = project_root / csv_path

    output_dir = config.output_dir
    if args.output_dir is not None:
        output_dir = args.output_dir
    elif not output_dir.is_absolute():
        output_dir = project_root / output_dir

    decimate_ratio = config.helios_decimate_ratio
    stem_decimate_ratio = config.helios_stem_decimate_ratio
    if args.stem_decimate_ratio is not None:
        stem_decimate_ratio = args.stem_decimate_ratio
    do_helios_scene = config.helios_helios_scene
    do_combined_obj = config.helios_combined_obj

    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    if not output_dir.exists():
        print(f"Error: Output directory not found: {output_dir}")
        sys.exit(1)

    from growpy.io.obj_export import clear_twig_decimate_cache, convert_tree_to_obj

    clear_twig_decimate_cache()

    # Find all assembly USDA files (matching _assembly naming convention)
    assembly_files = [usda for usda in output_dir.glob("*/tree_*/*_assembly.usda")]

    if not assembly_files:
        print("No assembly USDA files found in output directory")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"HELIOS OBJ EXPORT ({len(assembly_files)} trees)")
    print(f"{'='*60}")

    forest_data = pd.read_csv(csv_path)
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
            decimate_ratio=decimate_ratio,
            stem_decimate_ratio=stem_decimate_ratio,
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

    if do_helios_scene and obj_files:
        from growpy.io.helios_scene import generate_helios_scene

        scene_path = output_dir / "helios_scene.xml"
        generate_helios_scene(tree_entries=obj_files, output_path=scene_path)

    if do_combined_obj and obj_files:
        from growpy.io.obj_export import write_combined_obj

        is_conifer_forest = any(
            any(kw in sp.lower() for kw in CONIFER_KEYWORDS)
            for _, _, _, _, sp in obj_files
        )
        spectra = "conifer" if is_conifer_forest else "deciduous"
        combined_path = output_dir / "forest_combined.obj"
        write_combined_obj(
            tree_entries=obj_files,
            output_path=combined_path,
            helios_spectra_leaves=spectra,
        )

    print(f"\nOBJ export complete: {len(obj_files)} trees converted")


if __name__ == "__main__":
    main()
