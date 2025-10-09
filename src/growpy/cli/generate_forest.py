#!/usr/bin/env python3
"""
Forest generation with FBX export.

Usage:
    python generate_forest.py [csv_file]
"""

# CRITICAL: Setup USD PATH first before any other imports (especially bpy)
# This must happen BEFORE Blender DLLs are loaded to avoid conflicts
import os
import site
import sys

if sys.platform == "win32":
    # Add USD DLLs to PATH before importing bpy
    site_packages_dirs = site.getsitepackages()
    if hasattr(site, "getusersitepackages"):
        site_packages_dirs.append(site.getusersitepackages())

    for sp in site_packages_dirs:
        pxr_path = os.path.join(sp, "pxr")
        if os.path.exists(pxr_path):
            if pxr_path not in os.environ.get("PATH", ""):
                os.environ["PATH"] = pxr_path + os.pathsep + os.environ.get("PATH", "")

GROWTH_CYCLE_LIMIT = 10
HEIGHT_SCALE = 4

# IMPORTANT: Import bpy after USD path setup
try:
    import bpy
except (ImportError, OSError):
    bpy = None

from pathlib import Path

import pandas as pd
from tqdm import tqdm

from growpy import (
    EXPORT_AVAILABLE,
    GrowPyConfig,
    calculate_growth_cycles_from_height,
    create_forest,
    get_config,
    simulate_forest_growth,
)
from growpy.io.blender_export import get_quality_preset


def place_twigs_on_exported_trees(
    tree_usd_files: list, twigs_dir: Path, output_dir: Path
) -> None:
    """Place twigs on exported tree USD files.

    Args:
        tree_usd_files: List of tree USD file paths
        twigs_dir: Directory containing twig files
        output_dir: Output directory for tree+twig assemblies
    """
    import bpy

    from growpy.io.twig_placement import (
        export_twig_placements_to_usd,
        extract_twig_placements_from_mesh,
    )

    twigs_output = output_dir / "twigs_assemblies"
    twigs_output.mkdir(parents=True, exist_ok=True)

    for tree_file in tree_usd_files:
        try:
            # Find matching twig directory for this species
            species_name = tree_file.stem.replace("_tree", "")

            # Look for twig directory matching species
            twig_candidates = list(twigs_dir.glob(f"*{species_name}*Twig"))
            if not twig_candidates:
                twig_candidates = list(twigs_dir.glob("*Twig"))

            if not twig_candidates:
                print(f"  No twig found for {species_name}, skipping")
                continue

            twig_dir = twig_candidates[0]
            print(f"  Using twigs from: {twig_dir.name}")

            # Find twig USD files
            twig_files = list(twig_dir.glob("*.usda")) + list(twig_dir.glob("*.usd"))
            if not twig_files:
                print(f"  No USD twigs found in {twig_dir.name}")
                continue

            # Load tree to extract placement data
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.wm.usd_import(filepath=str(tree_file.resolve()))

            tree_obj = None
            for obj in bpy.context.scene.objects:
                if obj.type == "MESH":
                    tree_obj = obj
                    break

            if not tree_obj:
                print(f"  No mesh found in {tree_file.name}")
                continue

            # Map twig types to USD files
            twig_usd_map = {}
            for twig_file in twig_files:
                name_lower = twig_file.stem.lower()
                if "end" in name_lower or "long" in name_lower:
                    twig_usd_map["twig_long"] = twig_file
                elif "side" in name_lower or "short" in name_lower:
                    twig_usd_map["twig_short"] = twig_file
                else:
                    # Use first generic twig for all types
                    twig_usd_map["twig_long"] = twig_file
                    twig_usd_map["twig_short"] = twig_file
                    break

            if not twig_usd_map:
                print(f"  Could not map twig types for {species_name}")
                continue

            # Export assembly with twigs
            output_file = twigs_output / f"{species_name}_with_twigs.usda"
            # Pass tree_mesh (tree_obj) to avoid re-importing USD
            if export_twig_placements_to_usd(
                tree_file.resolve(),
                twig_usd_map,
                output_file.resolve(),
                tree_obj,
                extract_from_usd=False,
            ):
                print(f"  Created assembly: {output_file.name}")

        except Exception as e:
            print(f"  Failed to place twigs on {tree_file.name}: {e}")
            continue


def export_individual_trees(
    forest_data: pd.DataFrame,
    output_dir: Path,
    config: GrowPyConfig,
    quality_params: dict,
    formats: list,
    create_nanite_assembly: bool,
) -> list:
    """Export each tree individually as separate USD/FBX files.

    Args:
        forest_data: DataFrame with tree data including species, growth_cycles
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality_params: Quality parameters dict
        formats: List of export formats
        create_nanite_assembly: Create Nanite Assembly USD

    Returns:
        List of exported USD file paths
    """
    import gc as _gc_module

    from growpy.core.grove import create_grove
    from growpy.io.blender_export import (
        _get_gc,
        export_grove_tree_as_usda_native,
        get_twig_usd_map_for_species,
    )

    exported_files = []

    for idx, row in tqdm(
        forest_data.iterrows(),
        total=len(forest_data),
        desc="Exporting trees"
    ):
        species = row["species"]
        growth_cycles = int(row.get("growth_cycles", 10))

        species_clean = (
            "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
            .strip()
            .replace(" ", "_")
        )

        species_dir = output_dir / species_clean
        usd_dir = species_dir / "USD"
        usd_dir.mkdir(parents=True, exist_ok=True)

        tree_name = f"{species_clean}_tree_{idx:04d}"

        try:
            grove = create_grove(species)
            gc = _get_gc()

            grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
            grove.simulate(flushes=growth_cycles)

            if "usd" in formats or "usda" in formats:
                usd_path = usd_dir / f"{tree_name}.usda"

                twig_usd_map = get_twig_usd_map_for_species(
                    species, config, prefer_skeletal=False
                )

                export_success = export_grove_tree_as_usda_native(
                    grove,
                    usd_path,
                    species,
                    twig_usd_paths=twig_usd_map,
                    include_twigs=True,
                    use_point_instancer=True,
                    convert_to_ue=True,
                    create_nanite_assembly=create_nanite_assembly,
                    include_skeleton=True,
                    resolution=quality_params["resolution"],
                    resolution_reduce=quality_params["resolution_reduce"],
                    texture_repeat=quality_params["texture_repeat"],
                    build_cutoff_age=quality_params["build_cutoff_age"],
                    build_cutoff_thickness=quality_params["build_cutoff_thickness"],
                    build_blend=quality_params["build_blend"],
                    build_end_cap=quality_params["build_end_cap"],
                    config=config,
                )

                if export_success:
                    exported_files.append(usd_path)

            del grove
            _gc_module.collect()

        except Exception as e:
            print(f"Failed to export tree {idx} ({species}): {e}")
            continue

    return exported_files


def generate_forest_exports(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    formats: list = ["fbx"],
    quality: str = "high",
    resolution: int = None,
    place_twigs: bool = False,
    twigs_dir: Path = None,
    create_nanite_assembly: bool = True,
) -> None:
    """Generate forest from CSV data and export in specified formats.

    Args:
        csv_path: Path to CSV file with forest data
        output_dir: Directory to save export files
        config: GrowPy configuration
        formats: List of export formats ('fbx', 'usd', 'usda')
        quality: Quality preset name ('ultra', 'high', 'medium', 'low', 'performance')
        resolution: Override resolution from quality preset (4-32, optional)
        place_twigs: Whether to place twig instances on trees (default: False)
        twigs_dir: Directory containing twig files (default: config.twigs_path)
        create_nanite_assembly: Create Nanite Assembly USD for Unreal Engine (default: True)
    """
    if not EXPORT_AVAILABLE:
        print("ERROR: Export not available - bpy module required")
        return

    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        return

    print(f"Loading forest data from: {csv_path}")

    # Load forest data
    try:
        forest_data = pd.read_csv(csv_path)
        required_columns = ["x", "y", "species", "height"]

        # Check required columns
        missing_cols = [
            col for col in required_columns if col not in forest_data.columns
        ]
        if missing_cols:
            print(f"ERROR: CSV missing required columns: {missing_cols}")
            print(f"   Available columns: {list(forest_data.columns)}")
            print(f"   Required columns: {required_columns}")
            return

        # Ensure z column exists (will be added by create_forest if missing)
        if "z" not in forest_data.columns:
            print("INFO: No 'z' column found, using z=0 for all trees")

    except Exception as e:
        print(f"ERROR: Error loading CSV: {e}")
        return

    try:
        calculate_growth_cycles_from_height(forest_data)
    except Exception:
        forest_data["growth_cycles"] = 10
        forest_data["delay"] = 0

    # Scale growth cycles if max exceeds GROWTH_CYCLE_LIMIT
    max_growth_cycles = forest_data["growth_cycles"].max()
    if max_growth_cycles > GROWTH_CYCLE_LIMIT:
        scale_factor = GROWTH_CYCLE_LIMIT / max_growth_cycles
        forest_data["growth_cycles"] = (forest_data["growth_cycles"] * scale_factor).astype(int)
        forest_data["growth_cycles"] = forest_data["growth_cycles"].clip(lower=1)
        print(f"Scaled growth cycles: max {max_growth_cycles} -> {GROWTH_CYCLE_LIMIT}")
    else:
        # Apply height scale only if not scaling growth cycles
        forest_data["height"] /= HEIGHT_SCALE

    try:
        forest = create_forest(forest_data)
        max_cycles = forest_data["growth_cycles"].max()
        simulate_forest_growth(forest, max_cycles)
    except Exception as e:
        print(f"Forest simulation failed: {e}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get quality settings
    quality_params = get_quality_preset(quality)
    if resolution is not None:
        quality_params["resolution"] = resolution

    if any(fmt in formats for fmt in ["fbx", "usd", "usda"]):
        try:
            print(f"\nExporting {len(forest_data)} individual trees...")
            exported_files = export_individual_trees(
                forest_data,
                output_dir,
                config,
                quality_params,
                formats,
                create_nanite_assembly,
            )

            if exported_files:
                format_str = ", ".join(formats)
                print(
                    f"Exported {len(exported_files)} tree files ({format_str}) with '{quality}' quality"
                )

                # Bundle twig files for each unique species
                from growpy.io.blender_export import bundle_twigs_for_species

                unique_species = forest_data["species"].unique()
                print(f"\nBundling twig files for {len(unique_species)} species...")
                for species in unique_species:
                    species_clean = (
                        "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
                        .strip()
                        .replace(" ", "_")
                    )
                    species_dir = output_dir / species_clean

                    bundle_twigs_for_species(
                        species_name=species,
                        output_dir=species_dir,
                        formats=["usda"] if "usda" in formats or "usd" in formats else [],
                        config=config,
                    )

                # Place twigs if requested
                if place_twigs and bpy is not None:
                    try:
                        from growpy.io.twig_placement import (
                            export_twig_placements_to_usd,
                            place_twigs_in_blender,
                        )

                        # Use provided twigs directory or config default
                        if twigs_dir is None:
                            twigs_dir = config.twigs_path

                        if twigs_dir.exists():
                            print(f"\nPlacing twigs from: {twigs_dir}")
                            place_twigs_on_exported_trees(
                                exported_files, twigs_dir, output_dir
                            )
                        else:
                            print(f"Warning: Twigs directory not found: {twigs_dir}")
                            print("Skipping twig placement")
                    except ImportError as e:
                        print(f"Warning: Could not import twig placement module: {e}")
                    except Exception as e:
                        print(f"Warning: Twig placement failed: {e}")
        except Exception as e:
            print(f"Export failed: {e}")


def main():
    """Main forest generation function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate forest from CSV data and export trees in multiple formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
CSV Format:
    Required columns: x, y, species, height
    Optional columns: z (defaults to 0)

Examples:
    # Generate forest with default high quality
    python generate_forest.py forest_data.csv

    # Ultra quality for hero trees (32 vertices, max detail)
    python generate_forest.py forest_data.csv --quality ultra

    # Medium quality for background trees (16 vertices)
    python generate_forest.py forest_data.csv --quality medium

    # Performance mode for distant trees (8 vertices, minimal detail)
    python generate_forest.py forest_data.csv --quality performance

    # Custom: high quality preset but with 32 vertices
    python generate_forest.py forest_data.csv --quality high --resolution 32

    # Specify output directory
    python generate_forest.py forest_data.csv --output-dir data/output/my_forest --quality ultra
        """,
    )

    parser.add_argument(
        "csv_file",
        type=Path,
        nargs="?",
        default=None,
        help="Path to CSV file with forest data (x, y, species, height)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output/forest"),
        help="Directory to save export files (default: data/output/forest)",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["fbx", "usd", "usda"],
        default=["fbx"],
        help="Export formats (default: fbx)",
    )
    parser.add_argument(
        "--quality",
        type=str,
        default="ultra",
        choices=["ultra", "high", "medium", "low", "performance"],
        help="Quality preset (default: ultra). Controls resolution, detail level, and geometry complexity",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=None,
        choices=range(4, 33),
        metavar="4-32",
        help="Override resolution from quality preset. Vertices around branch circumference (4-32)",
    )
    parser.add_argument(
        "--place-twigs",
        action="store_true",
        help="Place twig instances on exported trees (requires twigs directory)",
    )
    parser.add_argument(
        "--twigs-dir",
        type=Path,
        default=None,
        help="Directory containing twig files (default: from config)",
    )
    parser.add_argument(
        "--create-nanite-assembly",
        action="store_true",
        default=True,
        help="Create Nanite Assembly USD files for Unreal Engine 5.7+ (default: True)",
    )
    parser.add_argument(
        "--no-nanite-assembly",
        dest="create_nanite_assembly",
        action="store_false",
        help="Skip Nanite Assembly USD creation",
    )

    args = parser.parse_args()

    try:
        # Determine CSV path
        if args.csv_file:
            csv_path = args.csv_file
        else:
            # Look for common CSV file locations
            project_root = Path(__file__).parent.parent.parent.parent
            possible_csvs = [
                project_root / "data" / "forest.csv",
                project_root / "forest_data.csv",
                Path("forest.csv"),
            ]

            csv_path = None
            for path in possible_csvs:
                if path.exists():
                    csv_path = path
                    break

            if csv_path is None:
                print("ERROR: No CSV file found")
                print("Usage: python generate_forest.py <csv_file>")
                print("Or place forest.csv in data/ or current directory")
                return

        config = get_config()
        generate_forest_exports(
            csv_path,
            args.output_dir,
            config,
            args.formats,
            args.quality,
            args.resolution,
            args.place_twigs,
            args.twigs_dir,
            args.create_nanite_assembly,
        )

    except Exception as e:
        print(f"ERROR: Generation failed: {e}")


if __name__ == "__main__":
    main()
