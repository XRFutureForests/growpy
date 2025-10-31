#!/usr/bin/env python3
"""
Forest generation with USD export.

Generates multi-species forests from CSV data with configurable quality settings.

Quick Start:
    # Uses data/input/test.csv by default
    python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 15

    # Or specify a different CSV file
    python src/growpy/cli/generate_forest.py my_forest.csv --quality high

Common Flags:
    --quality {ultra,high,medium,low,performance}  Quality preset (default: ultra)
    --growth-cycle-limit INT                       Max growth cycles (default: 10)
    --height-scale FLOAT                           Tree height scale (default: 1.0)
    --formats {usd,usda}                          Export formats (default: usda)
    --output-dir PATH                              Output directory

Full Documentation:
    See docs/guides/cli-reference.md for complete flag reference and examples

Usage:
    python src/growpy/cli/generate_forest.py [csv_file] --quality high --output-dir data/output/forest --growth-cycle-limit 5
"""

# CRITICAL: Import bpy and expose bundled modules BEFORE any other imports
# This ensures USD (pxr) is available for all subsequent imports
try:
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
except ImportError:
    pass  # bpy not available, will fall back to system USD if available

import multiprocessing as mp
import sys
from functools import partial
from typing import Optional

GROWTH_CYCLE_LIMIT = 1
HEIGHT_SCALE = 1
MAX_WORKERS = max(1, mp.cpu_count() - 1)  # Leave one core for system

from pathlib import Path

import pandas as pd
from tqdm import tqdm

from growpy import (
    TREE_EXPORT_AVAILABLE,
    GrowPyConfig,
    calculate_growth_cycles_from_height,
    create_forest,
    get_config,
    simulate_forest_growth,
)
from growpy.config.quality import get_quality_preset


def place_twigs_on_exported_trees(
    tree_usd_files: list, twigs_dir: Path, output_dir: Path
) -> None:
    """Place twigs on exported tree USD files.

    Args:
        tree_usd_files: List of tree USD file paths
        twigs_dir: Directory containing twig files
        output_dir: Output directory for tree+twig assemblies
    """
    # DEPRECATED: twig_placement.py removed - this functionality not yet refactored
    print("Warning: place_twigs_on_exported_trees is deprecated and disabled")
    return
    
    import bpy

    # from growpy.io.twig_placement import (
    #     export_twig_placements_to_usd,
    #     extract_twig_placements_from_mesh,
    # )

    twigs_output = output_dir / "twigs_assemblies"
    twigs_output.mkdir(parents=True, exist_ok=True)

    for tree_file in tree_usd_files:
        try:
            # Find matching twig directory for this species
            species_name = tree_file.stem.replace("_tree", "")

            # Look for twig directory matching species (snake_case naming)
            twig_candidates = list(twigs_dir.glob(f"*{species_name}*_twig"))
            if not twig_candidates:
                twig_candidates = list(twigs_dir.glob("*_twig"))

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


def _export_single_tree_from_forest(args: tuple) -> list:
    """Export a single tree from an already-simulated grove (forest simulation phase).

    This exports a tree directly from a grove that was already simulated with inter-species
    light competition. No re-simulation is performed - this is significantly faster than
    the old approach of recreating and re-simulating each tree individually.

    Args:
        args: Tuple of (idx, grove_instance, species_name, output_dir, quality_params,
                        formats, create_nanite_assembly, cleanup_mesh)

    Returns:
        List of exported file paths
    """
    # CRITICAL: Import bpy and expose bundled modules in worker process
    try:
        import bpy

        if hasattr(bpy.utils, "expose_bundled_modules"):
            bpy.utils.expose_bundled_modules()
    except ImportError:
        pass

    import gc as _gc_module

    from growpy import get_config
    from growpy.io.tree_export import export_tree, get_twig_usd_map_for_species

    (
        idx,
        grove,
        species,
        output_dir,
        quality_params,
        formats,
        create_nanite_assembly,
        cleanup_mesh,
    ) = args

    # Get config in worker process
    config = get_config()

    species_clean = (
        "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
        .strip()
        .replace(" ", "_")
        .lower()
    )

    species_dir = output_dir / species_clean
    if "usd" in formats or "usda" in formats:
        species_dir.mkdir(parents=True, exist_ok=True)

    tree_name = f"{species_clean}_tree_{idx:04d}"
    exported = []

    try:
        # Export directly from already-simulated grove (from forest simulation phase)
        # This grove was grown with inter-species light competition and is ready to export
        # No re-simulation needed - much faster!

        if "usd" in formats or "usda" in formats:
            usd_path = species_dir / f"{tree_name}.usda"

            # For skeletal assemblies, use skeletal twigs; for static, use static twigs
            prefer_skeletal_twigs = create_nanite_assembly
            twig_usd_map = get_twig_usd_map_for_species(
                species, config, prefer_skeletal=prefer_skeletal_twigs
            )

            export_success = export_tree(
                grove,
                usd_path,
                species,
                twig_usd_paths=twig_usd_map,
                include_twigs=True,
                use_point_instancer=True,
                convert_to_ue=True,
                create_nanite_assembly=create_nanite_assembly,
                resolution=quality_params["resolution"],
                resolution_reduce=quality_params["resolution_reduce"],
                texture_repeat=quality_params["texture_repeat"],
                build_cutoff_age=quality_params["build_cutoff_age"],
                build_cutoff_thickness=quality_params["build_cutoff_thickness"],
                build_blend=quality_params["build_blend"],
                build_end_cap=quality_params["build_end_cap"],
                skeleton_length=quality_params.get("skeleton_length", 1.0),
                skeleton_reduce=quality_params.get("skeleton_reduce", 0.25),
                skeleton_bias=quality_params.get("skeleton_bias", 0.5),
                skeleton_connected=quality_params.get("skeleton_connected", True),
                clean_export=quality_params.get("clean_export", False),
                config=config,
            )

            if export_success:
                exported.append(str(usd_path))

        _gc_module.collect()

    except Exception as e:
        print(f"Failed to export tree {idx} ({species}): {e}")

    return exported


def export_individual_trees(
    forest: list,
    forest_data: pd.DataFrame,
    output_dir: Path,
    config: GrowPyConfig,
    quality_params: dict,
    formats: list,
    create_nanite_assembly: bool,
    cleanup_mesh: bool = False,
    use_multiprocessing: bool = True,
    max_workers: Optional[int] = None,
) -> list:
    """Export trees directly from already-simulated forest groves (no re-simulation).

    Each tree is exported from the grove that was already simulated with inter-species
    light competition in the forest simulation phase. This is significantly faster than
    re-simulating individual trees.

    Args:
        forest: List of (grove, species_name, tree_count) from create_forest() + simulate_forest_growth()
        forest_data: DataFrame with tree data including species, growth_cycles
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality_params: Quality parameters dict
        formats: List of export formats
        create_nanite_assembly: Create Nanite Assembly USD
        cleanup_mesh: Perform mesh cleanup operations (slow for large meshes)
        use_multiprocessing: Enable parallel export (default: True)
        max_workers: Number of parallel workers (default: CPU count - 1)

    Returns:
        List of exported file paths
    """
    exported_files = []

    # Set defaults
    if max_workers is None:
        max_workers = MAX_WORKERS

    # Build tree export tasks from forest groves
    # Map species → grove for efficient lookup
    grove_map = {species_name: grove for grove, species_name, _ in forest}

    # Convert DataFrame rows to export tasks
    # Each task contains the actual grove (not row data) for direct export
    tree_tasks = []
    for idx, row in forest_data.iterrows():
        species = row["species"]
        grove = grove_map.get(species)

        if grove is None:
            print(f"Warning: No grove found for species '{species}' at row {idx}")
            continue

        tree_tasks.append(
            (
                idx,
                grove,
                species,
                output_dir,
                quality_params,
                formats,
                create_nanite_assembly,
                cleanup_mesh,
            )
        )

    total_trees = len(tree_tasks)
    print(
        f"\nExporting {total_trees} trees from simulated forest (no re-simulation)..."
    )

    # Always use sequential processing (bpy/USD not compatible with multiprocessing)
    print("Using sequential processing")
    for task in tqdm(tree_tasks, desc="Exporting trees"):
        result = _export_single_tree_from_forest(task)
        if result:
            exported_files.extend([Path(p) for p in result])

    return exported_files


def generate_forest_exports(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    formats: list = ["usda"],
    quality: str = "high",
    resolution: Optional[int] = None,
    place_twigs: bool = False,
    twigs_dir: Optional[Path] = None,
    create_nanite_assembly: bool = True,
    growth_cycle_limit: Optional[int] = None,
    height_scale: Optional[float] = None,
    cleanup_mesh: bool = False,
    use_multiprocessing: bool = True,
    max_workers: Optional[int] = None,
    skeleton_length: float = 1.0,
    skeleton_reduce: float = 0.25,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
    clean_export: bool = False,
) -> None:
    """Generate forest from CSV data and export in specified formats.

    Args:
        csv_path: Path to CSV file with forest data
        output_dir: Directory to save export files
        config: GrowPy configuration
        formats: List of export formats ('usd', 'usda')
        quality: Quality preset name ('ultra', 'high', 'medium', 'low', 'performance')
        resolution: Override resolution from quality preset (4-32, optional)
        place_twigs: Whether to place twig instances on trees (default: False)
        twigs_dir: Directory containing twig files (default: config.twigs_path)
        create_nanite_assembly: Create Nanite Assembly USD for Unreal Engine (default: True)
        growth_cycle_limit: Maximum growth cycles per tree (default: GROWTH_CYCLE_LIMIT)
        height_scale: Scale factor for tree heights (default: HEIGHT_SCALE)
        cleanup_mesh: Perform mesh cleanup operations (slow for large meshes) (default: False)
        use_multiprocessing: Enable parallel export processing (default: True)
        max_workers: Number of parallel workers (default: CPU count - 1)
        skeleton_length: Bone length multiplier (default: 1.0)
        skeleton_reduce: Bone reduction factor (default: 0.25)
        skeleton_bias: Weight bias (default: 0.5)
        skeleton_connected: Connected bone hierarchy (default: True)
        clean_export: If True, creates minimal USD without materials/textures (demo mode)
    """
    # Use defaults if not specified
    if growth_cycle_limit is None:
        growth_cycle_limit = GROWTH_CYCLE_LIMIT
    if height_scale is None:
        height_scale = HEIGHT_SCALE

    if not TREE_EXPORT_AVAILABLE:
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

    # Scale growth cycles if max exceeds growth_cycle_limit
    max_growth_cycles = forest_data["growth_cycles"].max()
    if max_growth_cycles > growth_cycle_limit:
        scale_factor = growth_cycle_limit / max_growth_cycles
        forest_data["growth_cycles"] = (
            forest_data["growth_cycles"] * scale_factor
        ).astype(int)
        forest_data["growth_cycles"] = forest_data["growth_cycles"].clip(lower=1)
        print(f"Scaled growth cycles: max {max_growth_cycles} -> {growth_cycle_limit}")
    else:
        # Apply height scale only if not scaling growth cycles
        forest_data["height"] /= height_scale

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

    # Add skeleton parameters to quality_params
    quality_params["skeleton_length"] = skeleton_length
    quality_params["skeleton_reduce"] = skeleton_reduce
    quality_params["skeleton_bias"] = skeleton_bias
    quality_params["skeleton_connected"] = skeleton_connected
    quality_params["clean_export"] = clean_export

    if any(fmt in formats for fmt in ["usd", "usda"]):
        try:
            # Bundle twig files BEFORE export so Nanite Assembly can reference them
            from growpy.io.tree_export import bundle_twigs_for_species

            unique_species = forest_data["species"].unique()
            print(f"\nBundling twig files for {len(unique_species)} species...")

            twig_formats = []
            if "usda" in formats or "usd" in formats:
                twig_formats.append("usda")

            for species in unique_species:
                species_clean = (
                    "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
                    .strip()
                    .replace(" ", "_")
                    .lower()
                )
                species_dir = output_dir / species_clean

                bundle_twigs_for_species(
                    species_name=species,
                    output_dir=species_dir,
                    formats=twig_formats,
                    config=config,
                )

            print(f"\nExporting {len(forest_data)} individual trees...")
            exported_files = export_individual_trees(
                forest,
                forest_data,
                output_dir,
                config,
                quality_params,
                formats,
                create_nanite_assembly,
                cleanup_mesh=cleanup_mesh,
                use_multiprocessing=use_multiprocessing,
                max_workers=max_workers,
            )

            if exported_files:
                format_str = ", ".join(formats)
                print(
                    f"Exported {len(exported_files)} tree files ({format_str}) with '{quality}' quality"
                )

                # Validate skeletal structure if creating Nanite assemblies
                if create_nanite_assembly:
                    print(f"\nValidating skeletal assemblies...")
                # Place twigs if requested
                if place_twigs:
                    print("Warning: place_twigs functionality disabled (twig_placement.py deprecated)")
                    # try:
                    #     from growpy.io.twig_placement import (
                    #         export_twig_placements_to_usd,
                    #         place_twigs_in_blender,
                    #     )
                    #
                    #     # Use provided twigs directory or config default
                    #     if twigs_dir is None:
                    #         twigs_dir = config.twigs_path
                    #
                    #     if twigs_dir.exists():
                    #         print(f"\nPlacing twigs from: {twigs_dir}")
                    #         place_twigs_on_exported_trees(
                    #             exported_files, twigs_dir, output_dir
                    #         )
                    # else:
                    #     print(f"Warning: Twigs directory not found: {twigs_dir}")
                    #     print("Skipping twig placement")
                    # except ImportError as e:
                    #     print(f"Warning: Could not import twig placement module: {e}")
                    # except Exception as e:
                    #     print(f"Warning: Twig placement failed: {e}")
        except Exception as e:
            print(f"Export failed: {e}")


def main():
    """Main forest generation function."""
    import argparse

    # Get script directory for default paths
    script_dir = Path(__file__).parent.parent.parent.parent
    default_csv = script_dir / "data" / "input" / "test.csv"

    parser = argparse.ArgumentParser(
        description="Generate forest from CSV data and export trees in multiple formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
CSV Format:
    Required columns: x, y, species, height
    Optional columns: z (defaults to 0)

Examples:
    # Generate forest using default input CSV (data/input/test.csv) with ultra quality
    python src/growpy/cli/generate_forest.py

    # Ultra quality for hero trees (32 vertices, max detail)
    python src/growpy/cli/generate_forest.py --quality ultra

    # Medium quality for background trees (16 vertices)
    python src/growpy/cli/generate_forest.py --quality medium

    # Performance mode for distant trees (8 vertices, minimal detail)
    python src/growpy/cli/generate_forest.py --quality performance

    # Custom: high quality preset but with 32 vertices
    python src/growpy/cli/generate_forest.py --quality high --resolution 32

    # Use a different CSV file with custom output directory
    python src/growpy/cli/generate_forest.py my_forest.csv --output-dir data/output/my_forest --quality ultra --growth-cycle-limit 15
        """,
    )

    parser.add_argument(
        "csv_file",
        type=Path,
        nargs="?",
        default=default_csv,
        help="Path to CSV file with forest data (default: data/input/test.csv)",
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
        choices=["usd", "usda"],
        default=["usda"],
        help="Export formats (default: usda)",
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
    parser.add_argument(
        "--growth-cycle-limit",
        type=int,
        default=GROWTH_CYCLE_LIMIT,
        help=f"Maximum growth cycles per tree (default: {GROWTH_CYCLE_LIMIT}). Trees exceeding this will be scaled down proportionally",
    )
    parser.add_argument(
        "--height-scale",
        type=float,
        default=HEIGHT_SCALE,
        help=f"Scale factor for tree heights (default: {HEIGHT_SCALE})",
    )
    parser.add_argument(
        "--cleanup-mesh",
        action="store_true",
        default=False,
        help="Perform mesh cleanup operations (slow for large meshes, improves Nanite compatibility)",
    )
    parser.add_argument(
        "--no-multiprocessing",
        dest="use_multiprocessing",
        action="store_false",
        default=True,
        help="Disable parallel processing (use sequential export)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help=f"Number of parallel workers (default: {MAX_WORKERS} = CPU count - 1)",
    )
    parser.add_argument(
        "--skeleton-length",
        type=float,
        default=1.0,
        help="Skeleton bone length multiplier (default: 1.0). Higher values create longer/merged bones. Note: ALL exports include skeleton (skeletal-only workflow)",
    )
    parser.add_argument(
        "--skeleton-reduce",
        type=float,
        default=0.25,
        help="Skeleton bone reduction factor (default: 0.25). Higher values create fewer bones (range: 0.0-1.0). Controls skeleton complexity",
    )
    parser.add_argument(
        "--skeleton-bias",
        type=float,
        default=0.5,
        help="Skeleton weight bias (default: 0.5, range: 0.0-1.0). Controls skinning weight distribution",
    )
    parser.add_argument(
        "--skeleton-disconnected",
        dest="skeleton_connected",
        action="store_false",
        default=True,
        help="Create disconnected bones instead of connected hierarchy (default: connected). Connected hierarchy is required for proper animation",
    )
    parser.add_argument(
        "--clean-export",
        action="store_true",
        default=False,
        help="Create minimal USD without materials/textures (demo mode, matches demo structure)",
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
            args.growth_cycle_limit,
            args.height_scale,
            args.cleanup_mesh,
            args.use_multiprocessing,
            args.max_workers,
            args.skeleton_length,
            args.skeleton_reduce,
            args.skeleton_bias,
            args.skeleton_connected,
            args.clean_export,
        )

    except Exception as e:
        print(f"ERROR: Generation failed: {e}")


if __name__ == "__main__":
    main()
