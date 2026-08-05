#!/usr/bin/env python3
"""CLI front-end for forest generation.

Step 4 of the pipeline. Defaults from config/forest.toml, config/unreal.toml, config/quality.toml.
Argument parsing and dispatch only -- pipeline logic lives in
`growpy.pipelines.forest_stages` and `growpy.pipelines.forest_exports`.
See docs/cli-reference.md.

Two ways to say what to build:

* ``--species NAME`` -- dataset mode. The job rows (one per configured surround
  radius) are derived from config: ``Max Height`` in tree_asset_lookup.csv and
  ``[surround] radii``. No CSV is involved, so nothing can drift from config.
* ``csv_file`` -- layout mode. A real spatial layout: x/y/z are positions, trees
  of a species share a grove, and neighbours compete for light. This is the path
  where growth-pacing calibration is meaningful ([calibration] enabled in
  growth_models.toml, off by default).
"""

import bpy

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

import logging
import sys
from pathlib import Path

from growpy import get_config
from growpy.config.preset_overrides import create_overrides_from_args
from growpy.io.unreal.script_generation import generate_unreal_scripts
from growpy.pipelines.forest_exports import generate_forest_exports
from growpy.pipelines.forest_stages import generate_forest_stages
from growpy.utils.naming import filename_safe_species_slug
from growpy.utils.profiling import init_profiler

logger = logging.getLogger(__name__)


def _resolve_forest_data(args, config, project_root):
    """Resolve the trees to build, from --species or from a CSV.

    Two readings, one return type:

    * ``--species NAME`` -- dataset mode. The job rows are derived entirely from
      config (Max Height in tree_asset_lookup.csv, [surround] radii), so nothing
      needs to be read from disk and nothing can drift from config.
    * ``csv_file`` -- plot mode. A real spatial layout with meaningful
      coordinates, supplied by the caller.

    Returns None (after logging) when the input is unusable, so the caller can
    exit non-zero.
    """
    import pandas as pd

    if args.species:
        from growpy.pipelines.dataset_csv_planner import build_job_matrix

        try:
            forest_data = build_job_matrix(args.species)
        except (ValueError, KeyError) as e:
            logger.error("Cannot build job rows for %s: %s", args.species, e)
            return None
        logger.info(
            "Dataset mode: %s, %d job row(s) from config (radii %s)",
            args.species,
            len(forest_data),
            ", ".join(f"{r:g}" for r in forest_data["surround_radius"]),
        )
        return forest_data

    csv_path = config.csv_file
    if not csv_path.is_absolute():
        csv_path = project_root / csv_path
    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        return None

    logger.info("Layout mode: reading %s", csv_path)
    return pd.read_csv(csv_path)



def _resolve_static_export_for_obj(config) -> bool:
    """Force static mesh export on when OBJ export needs it.

    OBJ export's assembly discovery (obj_export.py::_find_assembly_files)
    only globs *_assembly_static<ext> -- there is no skeletal fallback at
    that level. [export] static defaults False (the UE 5.7/5.8 Nanite
    Assembly builder deadlocks on StaticMesh targets), so without this,
    requesting --export-obj on the live default config silently exports
    zero trees.

    Returns True if export_static was forced on.
    """
    do_export_obj = config.helios_export_obj or config.helios_helios_scene
    if do_export_obj and not config.export_static:
        logger.warning(
            "OBJ export requires static mesh assemblies, enabling static mesh export"
        )
        config.export_static = True
        return True
    return False


def main():
    """Main forest generation function."""
    import argparse

    from growpy.config.paths import get_project_root

    project_root = get_project_root()

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

    # Generate and import directly to Unreal Engine Content Browser
    python src/growpy/cli/generate_forest.py --quality high --import-to-unreal

    # Complete pipeline with custom destination in Unreal
    python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 15 --import-to-unreal --unreal-project-path "/Game/MyProject/Trees"

    # Ultra quality for hero trees (32 vertices, max detail)
    python src/growpy/cli/generate_forest.py --quality ultra

    # Medium quality for background trees (16 vertices)
    python src/growpy/cli/generate_forest.py --quality medium

    # Performance mode for distant trees (8 vertices, minimal detail)
    python src/growpy/cli/generate_forest.py --quality performance

    # Custom: high quality preset but with 32 vertices
    python src/growpy/cli/generate_forest.py --quality high --resolution 32

    # Extra smooth branches for hero trees (20 iterations)
    python src/growpy/cli/generate_forest.py --quality ultra --smooth-iterations 20

    # Disable smoothing entirely for raw simulation output
    python src/growpy/cli/generate_forest.py --smooth-iterations 0

    # Use a different CSV file with custom output directory
    python src/growpy/cli/generate_forest.py my_forest.csv --output-dir data/output/my_forest --quality ultra --growth-cycle-limit 15

Note:
    PVE preset JSON files are always generated automatically for each tree.

Unreal Engine Integration:
    The --import-to-unreal flag generates a standalone Python script that can be executed
    in Unreal Engine using the VSCode Unreal Python extension. Right-click the generated
    script and select "Execute Python File in Unreal"
        """,
    )

    parser.add_argument(
        "csv_file",
        type=Path,
        nargs="?",
        default=None,
        help="Path to CSV file with forest data (default: from config)",
    )
    parser.add_argument(
        "--species",
        type=str,
        default=None,
        metavar="NAME",
        help=(
            "Dataset mode: build this species' job rows from config "
            "(tree_asset_lookup.csv Max Height + [surround] radii) instead of "
            "reading a CSV. Mutually exclusive with the csv_file argument."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to save export files (default: from config)",
    )
    parser.add_argument(
        "--quality",
        type=str,
        default=None,
        choices=["ultra", "high", "medium", "low", "performance"],
        help="Quality preset (default: from config). Controls resolution, detail level, and geometry complexity",
    )
    parser.add_argument(
        "--growth-cycle-limit",
        type=int,
        default=None,
        help="Maximum growth cycles per tree (default: from config). Trees exceeding this will be scaled down proportionally",
    )
    parser.add_argument(
        "--plateau-cycles",
        type=int,
        default=None,
        help="Stop early after this many consecutive cycles with no height "
        "increase across any tree (default: from config). 0 = run until max_cycles.",
    )
    parser.add_argument(
        "--smooth-iterations",
        type=int,
        default=None,
        help="Number of branch smoothing iterations (default: from config, range: 0-20). Higher values produce smoother branches with less sharp angles. Set to 0 to disable smoothing",
    )
    # Skeleton simplification parameters (independent of mesh quality)
    # See Grove documentation: each parameter independently reduces bone count
    parser.add_argument(
        "--skeleton-length",
        type=float,
        default=None,
        help="Create longer bones by merging nodes along branches (0.0-5.0). "
        "Higher values merge more nodes into single bones, reducing total bone count. "
        "Affects bone granularity along branch length. "
        "Default from preset (ultra=0.1, medium=2.0, performance=4.0)",
    )
    parser.add_argument(
        "--skeleton-reduce",
        type=float,
        default=None,
        help="Skip thin side branches entirely to reduce bone count (0.0-1.0). "
        "Higher values filter out more thin branches from having any bones. "
        "This is typically the most effective parameter for reducing bone count. "
        "Default from preset (ultra=0.1, medium=0.4, performance=0.8)",
    )
    parser.add_argument(
        "--skeleton-bias",
        type=float,
        default=None,
        help="Bone distribution bias (0.0-1.0). 0=more bones near trunk, 1=more near tips. Default: 0.5",
    )
    parser.add_argument(
        "--skeleton-connected",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Use connected bone chains (true=more bones, false=fewer bones). Default: true",
    )
    parser.add_argument(
        "--import-to-unreal",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Generate Unreal Python script for importing trees (execute in Unreal via VSCode extension)",
    )
    parser.add_argument(
        "--unreal-project-path",
        type=str,
        default=None,
        help="Unreal project Content path for imports (default: from config)",
    )
    parser.add_argument(
        "--include-grove-attributes",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include Grove metadata attributes (age, mass, vigor, etc.) in USD files for analysis (increases file size ~70%%).",
    )
    parser.add_argument(
        "--pve",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Generate PVE preset JSON files for Unreal import (default: from config).",
    )
    parser.add_argument(
        "--wind",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Generate DynamicWind JSON for the USD skeleton (default: from config).",
    )
    parser.add_argument(
        "--preset-override",
        type=str,
        action="append",
        metavar="PARAM=VALUE",
        help="Override preset parameter with fixed value (e.g., --preset-override drop_decay=0.1). Can be specified multiple times.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable verbose output (INFO-level logging)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress INFO-level logging (only show warnings and errors)",
    )
    parser.add_argument(
        "--profile",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable profiling to track execution time of each processing step",
    )
    # Note: --skip-wind-json removed - wind data now embedded in USD skeleton
    parser.add_argument(
        "--skip-validation",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Skip assembly validation (saves ~5-10%% of export time)",
    )
    parser.add_argument(
        "--previews",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Generate the preview PNG per tree (default: from config). "
            "The export-control render has its own flag, --export-control."
        ),
    )
    parser.add_argument(
        "--export-control",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Generate the export-control PNG per tree (default: from config). "
            "Separate from --previews because it is the most expensive image "
            "stage by a wide margin."
        ),
    )
    parser.add_argument(
        "--icons",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Generate front/side/top icon PNGs per tree (default: from config).",
    )

    # Mesh type export flags (independent, any combination works)
    parser.add_argument(
        "--skeletal",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable skeletal mesh export (default: from config)",
    )
    parser.add_argument(
        "--static",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable static mesh export (default: from config)",
    )

    # Multi-stage export: generate trees at multiple growth stages from a single position
    parser.add_argument(
        "--height-interval",
        type=float,
        default=None,
        help="Export trees at height intervals in meters (e.g., 5 = 5m, 10m, 15m...). "
        "Uses growth models to determine cycles. Enables multi-stage mode.",
    )
    parser.add_argument(
        "--max-height",
        type=float,
        default=None,
        help="Cap tree heights at this value in meters (e.g., 15). "
        "Trees taller than this in the CSV are clamped. 0 = no limit (default).",
    )
    parser.add_argument(
        "--export-trees",
        type=str,
        default=None,
        help="Comma-separated list of tree IDs (fid) to export. Other trees still participate in growth simulation but are not exported. Example: --export-trees 1,2,5",
    )
    # Helios++ OBJ/MTL export
    parser.add_argument(
        "--export-obj",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Export OBJ/MTL files for Helios++ LiDAR simulation (post-processes USDA files)",
    )
    parser.add_argument(
        "--helios-scene",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Generate Helios++ scene XML placing all tree OBJs at CSV positions (implies --export-obj)",
    )
    parser.add_argument(
        "--individual-obj",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Also write individual per-tree OBJ files (default: only combined OBJ)",
    )
    parser.add_argument(
        "--classification",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Per-tree Helios++ classification codes for labeled point clouds "
        "(requires 'selected_*' species and fid 1-9; see docs/guides/helios-export.md)",
    )
    parser.add_argument(
        "--obj-up-axis",
        type=str,
        default=None,
        choices=["y", "z"],
        help="OBJ coordinate up axis: 'y' (standard, default) or 'z' (matches USD)",
    )
    parser.add_argument(
        "--no-unreal-scripts",
        action="store_true",
        help="Skip Unreal import/cleanup script generation (used by parallel pipeline)",
    )

    args = parser.parse_args()

    if args.species and args.csv_file is not None:
        parser.error(
            "--species and csv_file are mutually exclusive -- pass one or the other"
        )

    # Resolve config: TOML defaults + CLI overrides
    config = get_config()
    config.resolve(args)

    # --quiet overrides --verbose and config
    if args.quiet:
        config.verbose = False

    from growpy.utils.log import setup_logging

    setup_logging(verbose=config.verbose)

    # Validate export flags
    _resolve_static_export_for_obj(config)

    if not config.export_skeletal and not config.export_static:
        logger.error(
            "No mesh export types enabled. "
            "Enable at least one of: --skeletal, --static, or --export-obj"
        )
        return 1

    # Initialize profiler
    timer = init_profiler(enabled=config.profile)

    try:
        forest_data = _resolve_forest_data(args, config, project_root)
        if forest_data is None:
            return 1

        output_dir = config.output_dir
        if not output_dir.is_absolute():
            output_dir = project_root / output_dir

        # Build preset overrides from CLI arguments
        preset_overrides = None
        if args.preset_override:
            preset_overrides = create_overrides_from_args(
                static_args=args.preset_override,
            )
            logger.info(
                "\n[Preset Overrides] Static: %s",
                preset_overrides.static_overrides,
            )

        skip_pve_json = not config.unreal_generate_pve_presets
        skip_validation = config.export_skip_validation

        # Export-trees filter (config value already merged with CLI by resolve())
        export_tree_ids = None
        if config.forest_export_trees:
            export_tree_ids = set(config.forest_export_trees)
            logger.info(
                "\n[Export Filter] Only exporting trees with fid: %s",
                sorted(export_tree_ids),
            )

        # Build skeleton overrides from config (CLI args already resolved into config)
        skeleton_overrides = {}
        if config.forest_skeleton_length is not None:
            skeleton_overrides["skeleton_length"] = config.forest_skeleton_length
        if config.forest_skeleton_reduce is not None:
            skeleton_overrides["skeleton_reduce"] = config.forest_skeleton_reduce
        if config.forest_skeleton_bias is not None:
            skeleton_overrides["skeleton_bias"] = config.forest_skeleton_bias
        if config.forest_skeleton_connected is not None:
            skeleton_overrides["skeleton_connected"] = config.forest_skeleton_connected
        skeleton_overrides = skeleton_overrides if skeleton_overrides else None

        # Detect multi-stage mode (config value already merged with CLI by resolve())
        is_multistage = config.forest_height_interval > 0

        with timer.track("total_forest_generation"):
            if is_multistage:
                # Multi-stage export mode: generate trees at height milestones
                generate_forest_stages(
                    forest_data,
                    output_dir,
                    config,
                    config.forest_quality,
                    height_interval=config.forest_height_interval,
                    growth_cycle_limit=config.forest_growth_cycle_limit,
                    plateau_cycles=config.forest_plateau_cycles,
                    smooth_iterations=config.forest_smooth_iterations,
                    include_grove_attributes=config.forest_include_grove_attributes,
                    verbose=config.verbose,
                    preset_overrides=preset_overrides,
                    timer=timer,
                    skip_pve_json=skip_pve_json,
                    skip_validation=skip_validation,
                    skeleton_overrides=skeleton_overrides,
                    export_tree_ids=export_tree_ids,
                )
            else:
                # Standard height-based export mode
                generate_forest_exports(
                    forest_data,
                    output_dir,
                    config,
                    config.forest_quality,
                    config.forest_growth_cycle_limit,
                    config.forest_smooth_iterations,
                    include_grove_attributes=config.forest_include_grove_attributes,
                    verbose=config.verbose,
                    preset_overrides=preset_overrides,
                    timer=timer,
                    skip_pve_json=skip_pve_json,
                    skip_validation=skip_validation,
                    skeleton_overrides=skeleton_overrides,
                    export_tree_ids=export_tree_ids,
                )

        # OBJ/MTL export for Helios++ (post-processes USDA output)
        do_export_obj = config.helios_export_obj or config.helios_helios_scene
        if do_export_obj:
            from growpy.io.helios.obj_export import export_forest_obj

            with timer.track("obj_export"):
                simp_ratios = None
                simp_per_species = None
                if config.helios_simplification_enabled:
                    simp_ratios = config.helios_simplification_ratios
                    simp_per_species = config.helios_simplification_per_species
                export_forest_obj(
                    output_dir=output_dir,
                    forest_data=forest_data,
                    generate_scene_xml=config.helios_helios_scene,
                    individual_obj=config.helios_individual_obj,
                    up_axis=config.helios_obj_up_axis,
                    timer=timer,
                    simplification_ratios=simp_ratios,
                    per_species_ratios=simp_per_species,
                )

        # Print profiling report if enabled
        if config.profile:
            timer.print_report()

        # Generate Unreal scripts if requested
        if config.unreal_import_to_unreal and not getattr(
            args, "no_unreal_scripts", False
        ):
            import_script, cleanup_script = generate_unreal_scripts(
                output_dir, config, include_static=config.export_static
            )

            logger.info("\n%s", "=" * 60)
            logger.info("UNREAL SCRIPTS GENERATED")
            logger.info("%s", "=" * 60)
            logger.info("Scripts directory: %s", import_script)
            logger.info("Cleanup script: %s", cleanup_script)
            logger.info("\nTo import trees to Unreal Engine:")
            logger.info(
                "  python -m growpy.tools.ue_exec %s --vram-limit 85", import_script
            )
            logger.info("\nTo cleanup assets:")
            logger.info("1. Open clean_assets.py in VSCode")
            logger.info("2. Review DRY_RUN setting (True = preview, False = delete)")
            logger.info("3. Right-click > 'Execute Python File in Unreal'")
            logger.info("\nRequirements:")
            logger.info("- Unreal Engine must be running")
            logger.info("- Python Remote Execution enabled in UE Editor Preferences")
            logger.info("- USD Importer plugin enabled")
            logger.info("- Editor Scripting Utilities plugin enabled")

        # Pipeline completion summary (always visible, even in quiet mode).
        # Scoped to this run's own species dirs -- output_dir is shared by every
        # parallel step-4 worker, so an unscoped glob reports a cumulative count
        # from every species already exported, not just this run's.
        total_time = timer.get_total_time() if timer.enabled else 0
        run_species_dirs = sorted(
            {filename_safe_species_slug(sp) for sp in forest_data["species"].unique()}
        )
        species_dirs = [
            output_dir / sp_dir
            for sp_dir in run_species_dirs
            if (output_dir / sp_dir).is_dir()
        ]
        tree_count = sum(
            len(list(sp_dir.glob(f"**/*_assembly*{config.usd_ext}")))
            for sp_dir in species_dirs
        )
        summary_parts = [
            f"{tree_count} assemblies",
            f"{len(species_dirs)} species",
        ]
        if total_time > 0:
            summary_parts.append(f"{total_time:.1f}s")
        print(
            f"\nPipeline complete: {', '.join(summary_parts)} -> {output_dir}",
            file=sys.stderr,
        )

    except Exception as e:
        logger.error("Forest generation failed: %s", e)
        logger.debug("Traceback:", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
