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

import bpy

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

import multiprocessing as mp
import sys
from functools import partial
from itertools import groupby
from pathlib import Path
from typing import Optional

import pandas as pd
from tqdm import tqdm

GROWTH_CYCLE_LIMIT = 10
HEIGHT_SCALE = 1
MAX_WORKERS = max(1, mp.cpu_count() - 1)
SMOOTH_ITERATIONS = 5

from growpy import (
    TREE_EXPORT_AVAILABLE,
    GrowPyConfig,
    calculate_growth_cycles_from_height,
    create_forest,
    get_config,
    simulate_forest_growth,
)
from growpy.config.quality import get_quality_preset


def _export_single_tree_from_forest(args: tuple) -> list:
    """Export all trees from an already-simulated grove (forest simulation phase).

    This exports trees directly from a grove that was already simulated with inter-species
    light competition. No re-simulation is performed - this is significantly faster than
    the old approach of recreating and re-simulating each tree individually.

    Args:
        args: Tuple of (start_idx, grove_instance, species_name, output_dir, quality_params)
              start_idx is the base tree number for sequential numbering

    Returns:
        List of exported file paths
    """
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()

    import gc as _gc_module

    from growpy import get_config
    from growpy.io.assembly_export import export_tree_as_nanite_assembly
    from growpy.io.tree_export import get_twig_usd_map_for_species

    (start_idx, grove, species, output_dir, quality_params) = args

    # Get config in worker process
    config = get_config()

    species_clean = (
        "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
        .strip()
        .replace(" ", "_")
        .lower()
    )

    species_dir = output_dir / species_clean
    species_dir.mkdir(parents=True, exist_ok=True)

    exported = []

    try:
        # Export directly from already-simulated grove (from forest simulation phase)
        # This grove was grown with inter-species light competition and is ready to export
        # No re-simulation needed - much faster!
        for i in range(SMOOTH_ITERATIONS):
            grove.smooth()

        # CRITICAL BUILD ORDER: skeleton -> bones -> models
        # 1. Build skeletons first
        skeletons = grove.build_skeletons()

        # 2. Tag bone IDs with length=0.0 and reduce=0.0 for maximum bone count
        # Skeletal simplification happens later in Unreal Engine if needed
        # Note: tag_bone_id() takes positional args: (length, reduce, bias, connected)
        bones = grove.tag_bone_id(
            0.0,  # skeleton_length - no merging by length
            0.0,  # skeleton_reduce - no reduction by thickness
            quality_params.get("skeleton_bias", 0.5),
            quality_params.get("skeleton_connected", True),
        )

        # 3. NOW build models (with bone_id attributes already tagged)
        models = grove.build_models(
            {
                "resolution": quality_params["resolution"],
                "resolution_reduce": quality_params["resolution_reduce"],
                "texture_repeat": quality_params["texture_repeat"],
                "build_cutoff_age": quality_params["build_cutoff_age"],
                "build_cutoff_thickness": quality_params["build_cutoff_thickness"],
                "build_blend": quality_params["build_blend"],
                "build_end_cap": quality_params["build_end_cap"],
            }
        )

        if not models:
            return exported

        # Slice bones list for each tree in grove
        bones_grouped = [list(g) for k, g in groupby(bones, lambda x: x[0])]
        tree_bones = [
            bones_grouped[i]
            + (bones_grouped[i + 1] if i + 1 < len(bones_grouped) else [])
            for i in range(0, len(bones_grouped), 2)
        ]

        # Export each model/skeleton/bones triplet (each is a separate tree)
        for model_idx, (model, skeleton, bones_for_tree) in enumerate(
            zip(models, skeletons, tree_bones)
        ):
            # Use sequential numbering: start_idx + model_idx
            tree_num = start_idx + model_idx
            tree_name = f"{species_clean}_tree_{tree_num:04d}"
            usd_path = species_dir / f"{tree_name}_nanite_assembly.usda"

            # Always use skeletal twigs for Nanite assemblies
            twig_usd_map = get_twig_usd_map_for_species(
                species, config, prefer_skeletal=True
            )

            # Export as skeletal Nanite Assembly (includes twigs, skeleton, proper UE schema)
            export_success = export_tree_as_nanite_assembly(
                model=model,
                skeleton=skeleton,
                bones_info=bones_for_tree,
                output_path=usd_path,
                species_name=species,
                twig_usd_paths=twig_usd_map,
                include_twigs=True,
                use_skeletal_mesh=True,
            )

            if export_success:
                exported.append(str(usd_path))

        _gc_module.collect()

    except Exception as e:
        import traceback

        traceback.print_exc()

    return exported


def export_individual_trees(
    forest: list,
    forest_data: pd.DataFrame,
    output_dir: Path,
    config: GrowPyConfig,
    quality_params: dict,
    use_multiprocessing: bool = True,
    max_workers: Optional[int] = None,
) -> list:
    """Export trees directly from already-simulated forest groves (no re-simulation).

    Each tree is exported from the grove that was already simulated with inter-species
    light competition in the forest simulation phase. This is significantly faster than
    re-simulating individual trees.

    Always exports as skeletal Nanite Assembly USD files (.usda format).

    Args:
        forest: List of (grove, species_name, tree_count) from create_forest() + simulate_forest_growth()
        forest_data: DataFrame with tree data including species, growth_cycles
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality_params: Quality parameters dict
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
    # Each grove contains multiple trees for that species, export all at once
    # Trees are numbered per-species (starting at 0) since each species has its own folder
    grove_tasks = []

    for grove, species_name, tree_count in forest:
        # Create one task per grove (which will export all trees in that grove)
        # start_idx=0 for each grove since trees are numbered within species folder
        grove_tasks.append((0, grove, species_name, output_dir, quality_params))

    # Always use sequential processing (bpy/USD not compatible with multiprocessing)
    for task in tqdm(grove_tasks, desc="Exporting groves"):
        result = _export_single_tree_from_forest(task)
        if result:
            exported_files.extend([Path(p) for p in result])

    return exported_files


def generate_forest_exports(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    quality: str = "high",
    resolution: Optional[int] = None,
    growth_cycle_limit: Optional[int] = None,
    height_scale: Optional[float] = None,
    use_multiprocessing: bool = True,
    max_workers: Optional[int] = None,
    skeleton_length: float = 0.0,
    skeleton_reduce: float = 0.0,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
    clean_export: bool = True,
) -> None:
    """Generate forest from CSV data and export as skeletal Nanite Assembly USD files.

    Always exports as .usda format with skeletal mesh structure for Unreal Engine.

    Args:
        csv_path: Path to CSV file with forest data
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality: Quality preset name ('ultra', 'high', 'medium', 'low', 'performance')
        resolution: Override resolution from quality preset (4-32, optional)
        growth_cycle_limit: Maximum growth cycles per tree (default: GROWTH_CYCLE_LIMIT)
        height_scale: Scale factor for tree heights (default: HEIGHT_SCALE)
        use_multiprocessing: Enable parallel export processing (default: True)
        max_workers: Number of parallel workers (default: CPU count - 1)
        skeleton_length: Bone length multiplier (default: 1.0)
        skeleton_reduce: Bone reduction factor (default: 0.25)
        skeleton_bias: Weight bias (default: 0.5)
        skeleton_connected: Connected bone hierarchy (default: True)
        clean_export: If True, creates minimal USD without materials/textures (default for Nanite)
    """
    # Use defaults if not specified
    if growth_cycle_limit is None:
        growth_cycle_limit = GROWTH_CYCLE_LIMIT
    if height_scale is None:
        height_scale = HEIGHT_SCALE

    if not TREE_EXPORT_AVAILABLE:
        return

    if not csv_path.exists():
        return

    # Load forest data
    try:
        forest_data = pd.read_csv(csv_path)
        required_columns = ["x", "y", "species", "height"]

        # Check required columns
        missing_cols = [
            col for col in required_columns if col not in forest_data.columns
        ]
        if missing_cols:
            return

        # Ensure z column exists (will be added by create_forest if missing)
        if "z" not in forest_data.columns:
            pass

    except Exception as e:
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
    else:
        # Apply height scale only if not scaling growth cycles
        forest_data["height"] /= height_scale

    try:
        forest = create_forest(forest_data)
        max_cycles = forest_data["growth_cycles"].max()
        simulate_forest_growth(forest, max_cycles)
    except Exception as e:
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

    try:
        # Bundle twig files BEFORE export so Nanite Assembly can reference them
        from growpy.io.tree_export import bundle_twigs_for_species

        unique_species = forest_data["species"].unique()

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
                formats=["usda"],
                config=config,
            )

        exported_files = export_individual_trees(
            forest,
            forest_data,
            output_dir,
            config,
            quality_params,
            use_multiprocessing=use_multiprocessing,
            max_workers=max_workers,
        )

        if exported_files:
            pass

    except Exception as e:
        pass


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
        default=True,
        help="Create minimal USD without materials/textures (default: True for Nanite compatibility)",
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
                return

        config = get_config()
        generate_forest_exports(
            csv_path,
            args.output_dir,
            config,
            args.quality,
            args.resolution,
            args.growth_cycle_limit,
            args.height_scale,
            args.use_multiprocessing,
            args.max_workers,
            args.skeleton_length,
            args.skeleton_reduce,
            args.skeleton_bias,
            args.skeleton_connected,
            args.clean_export,
        )

    except Exception as e:
        pass


if __name__ == "__main__":
    main()
