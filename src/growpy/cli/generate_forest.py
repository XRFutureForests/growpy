#!/usr/bin/env python3
"""Generate multi-species forests from CSV with USD export for Unreal Engine.

Step 4 of the pipeline. Defaults from growpy.toml [forest], [export], [unreal].
See docs/cli-reference.md.
"""

import bpy

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

import shutil
import sys
from itertools import groupby
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from tqdm import tqdm

GROWTH_CYCLE_LIMIT = 10
SMOOTH_ITERATIONS = 10  # Default: 10 iterations for natural smoothing (range: 0-20)

import logging

from growpy import (
    TREE_EXPORT_AVAILABLE,
    GrowPyConfig,
    calculate_growth_cycles_from_height,
    create_forest,
    get_config,
    simulate_forest_growth,
)
from growpy.config.preset_overrides import (
    PresetOverrides,
    create_overrides_from_args,
)
from growpy.config.quality import get_quality_preset
from growpy.core.forest import simulate_forest_growth_with_snapshots
from growpy.io.forest_export import export_individual_trees
from growpy.io.usd.preview import generate_preview_image as _generate_preview_image
from growpy.io.usd.preview import (
    generate_export_control_image as _generate_export_control_image,
)
from growpy.io.usd.preview import generate_icon_image as _generate_icon_image
from growpy.io.usd.tree_export import (
    derive_static_from_skeletal as _derive_static_from_skeletal,
)
from growpy.io.usd.tree_export import (
    handle_bone_limit_error as _handle_bone_limit_error,
)
from growpy.io.usd.tree_export import (
    is_bone_limit_error as _is_bone_limit_error,
)
from growpy.io.unreal.unreal_scripts import (
    generate_unreal_cleanup_script,
    generate_unreal_import_script,
)
from growpy.utils.export_naming import (
    format_dbh_for_filename,
    format_density_for_filename,
    format_height_for_filename,
)
from growpy.utils.profiling import ProfileTimer, init_profiler

logger = logging.getLogger(__name__)


def generate_forest_stages(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    quality: str = "high",
    height_interval: Optional[float] = None,
    growth_cycle_limit: Optional[int] = None,
    smooth_iterations: Optional[int] = None,
    include_grove_attributes: bool = False,
    verbose: bool = False,
    preset_overrides: Optional[PresetOverrides] = None,
    timer: Optional["ProfileTimer"] = None,
    skip_pve_json: bool = False,
    skip_validation: bool = False,
    skeleton_overrides: Optional[Dict[str, Any]] = None,
    export_tree_ids: Optional[set] = None,
) -> None:
    """Generate trees at multiple growth stages using height-based milestones.

    Exports multiple tree models at different heights from a single tree position,
    with height and DBH encoded in the filename for easy asset selection.

    Height milestones (e.g., every 5m) are converted to growth cycles using
    pre-trained growth models. Each species gets its own set of milestone
    cycles, producing equal height spacing regardless of species growth rate.

    CSV Format (requires height column):
        fid,species,x,y,z,height
        1,Norway spruce,0,0,0,35.0

    Args:
        csv_path: Path to CSV file with forest data (requires: species, x, y, height)
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality: Quality preset name
        height_interval: Export every N meters of height (default: 5.0)
        growth_cycle_limit: Cap cycles at this limit
        smooth_iterations: Number of smoothing iterations for branches
        include_grove_attributes: If True, include Grove metadata in USD files
        verbose: Print detailed progress information
        preset_overrides: Optional PresetOverrides for dynamic parameter adjustment
        timer: Optional ProfileTimer for tracking execution times
        skip_pve_json: If True, skip PVE preset JSON generation
        skip_validation: If True, skip assembly validation
    """
    from growpy.config.preset_overrides import (
        load_height_dbh_model_from_preset,
        load_target_dbh_from_preset,
        predict_dbh_from_height_model,
    )
    from growpy.io.usd.assembly_export import export_tree_as_nanite_assembly
    from growpy.io.usd.tree_export import get_twig_usd_map_for_species
    from growpy.utils.profiling import ProfileTimer
    from growpy.utils.log import is_verbose

    if timer is None:
        timer = ProfileTimer(enabled=False)

    # Clear twig file copy cache at start of export session
    from growpy.io.usd.assembly_export import clear_twig_copy_cache

    clear_twig_copy_cache()

    # Shared twig/foliage instances directory (Megaplant-style)
    instances_dir = output_dir / "Instances"
    instances_dir.mkdir(parents=True, exist_ok=True)

    # Use defaults if not specified
    if smooth_iterations is None:
        smooth_iterations = SMOOTH_ITERATIONS

    if not TREE_EXPORT_AVAILABLE:
        logger.error("Tree export not available (missing dependencies)")
        return

    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        return

    # Load forest data
    try:
        with timer.track("load_csv"):
            forest_data = pd.read_csv(csv_path)

            # Check required columns - height is required for cycle calculation
            required_columns = ["x", "y", "species", "height"]
            missing_cols = [
                col for col in required_columns if col not in forest_data.columns
            ]
            if missing_cols:
                logger.error("Missing required columns: %s", missing_cols)
                logger.error(
                    "  Multi-stage mode requires height to calculate growth cycles"
                )
                return

            # Ensure fid column exists
            if "fid" not in forest_data.columns:
                forest_data["fid"] = range(1, len(forest_data) + 1)

            # Ensure z column exists
            if "z" not in forest_data.columns:
                forest_data["z"] = 0.0

    except Exception as e:
        logger.error("Error loading CSV: %s", e)
        return

    # Cap tree heights if max_height is configured
    if config.forest_max_height > 0:
        original_max = forest_data["height"].max()
        forest_data["height"] = forest_data["height"].clip(
            upper=config.forest_max_height
        )
        logger.info(
            "Max height cap: %.1fm (original max: %.1fm)",
            config.forest_max_height,
            original_max,
        )

    # Height-threshold mode: no growth model cycle prediction needed.
    # The simulation runs until milestones are captured, growth plateaus,
    # or the cycle limit is reached.
    effective_interval = height_interval if height_interval is not None else 5.0
    effective_max_height = config.forest_max_height if config.forest_max_height > 0 else 0.0
    global_max_cycles = growth_cycle_limit if growth_cycle_limit is not None else 65

    logger.info("\n%s", "=" * 60)
    logger.info("MULTI-STAGE FOREST GENERATION (height-threshold mode)")
    logger.info("%s", "=" * 60)
    logger.info("  Trees: %d", len(forest_data))
    logger.info(
        "  Height range: %.1fm - %.1fm",
        forest_data["height"].min(),
        forest_data["height"].max(),
    )
    logger.info("  Height interval: %.0fm", effective_interval)
    logger.info("  Target height: %.0fm", effective_max_height)
    logger.info("  Cycle limit: %d (safety cap)", global_max_cycles)
    if config.forest_competition_distance_increase > 0:
        logger.info(
            "  Competition thinning: %.1fm per interval",
            config.forest_competition_distance_increase,
        )
    logger.info("%s", "=" * 60)

    # All trees start at cycle 0 (no delay in multi-stage mode)
    forest_data["delay"] = 0

    with timer.track("create_forest"):
        forest = create_forest(forest_data)

    # Get quality settings
    quality_params = get_quality_preset(quality)
    quality_params["skeleton_bias"] = 0.5
    quality_params["skeleton_connected"] = True
    quality_params["minimal_export"] = True
    quality_params["include_grove_attributes"] = include_grove_attributes
    quality_params["skip_pve_json"] = skip_pve_json
    quality_params["skip_validation"] = skip_validation
    quality_params["export_tree_ids"] = export_tree_ids

    # Apply skeleton overrides (allows simplified skeleton with ultra mesh)
    if skeleton_overrides:
        for key, value in skeleton_overrides.items():
            quality_params[key] = value
        logger.info("[Skeleton Overrides] Applied: %s", skeleton_overrides)

    # Build species-to-grove mapping for PVE JSON generation
    species_grove_map: Dict[str, Any] = {}
    for grove_obj, sp_name, _tc, _fids in forest:
        species_grove_map[sp_name] = grove_obj

    # Run simulation with height-threshold-based snapshots
    with timer.track("simulate_with_snapshots"):
        snapshots, milestone_map = simulate_forest_growth_with_snapshots(
            forest,
            max_cycles=global_max_cycles,
            snapshot_cycles=[],
            smooth_iterations=smooth_iterations,
            preset_overrides=preset_overrides,
            use_species_curves=config.calibration_align_height,
            quality_params=quality_params,
            height_interval=effective_interval,
            max_height=effective_max_height,
            competition_distance_increase=config.forest_competition_distance_increase,
            forest_data=forest_data,
        )

    if not snapshots:
        logger.error("No snapshots captured during simulation")
        return

    # Clean stale exports (only subdirectories that this CSV will write to)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Ensure shared instances directory exists (don't wipe -- other species may share it)
    instances_dir.mkdir(parents=True, exist_ok=True)
    has_individual_type = "individual_type" in forest_data.columns
    for sp in forest_data["species"].unique():
        sp_dir_name = (
            "".join(c for c in sp if c.isalnum() or c in (" ", "-", "_"))
            .strip()
            .replace(" ", "_")
            .lower()
        )
        sp_dir = output_dir / sp_dir_name
        if has_individual_type:
            for itype in forest_data.loc[
                forest_data["species"] == sp, "individual_type"
            ].unique():
                sub = sp_dir / str(itype)
                if sub.exists():
                    shutil.rmtree(sub)
        elif sp_dir.exists():
            shutil.rmtree(sp_dir)

    # Export each snapshot
    logger.info("\n%s", "=" * 60)
    logger.info("PHASE 3: EXPORTING STAGES (%d cycles)", len(snapshots))
    logger.info("%s", "=" * 60)

    # Cache height-DBH models and fallback curves per species for radial scaling
    h_dbh_model_cache: Dict[str, Optional[Dict[str, float]]] = {}
    target_dbh_cache: Dict[str, list] = {}

    # Build per-tree CSV DBH map (fid -> dbh in meters) for custom diameter scaling
    csv_dbh_map: Dict[int, float] = {}
    if "dbh" in forest_data.columns:
        for _, row in forest_data.iterrows():
            val = row["dbh"]
            if pd.notna(val) and float(val) > 0:
                csv_dbh_map[int(row["fid"])] = float(val) / 100.0  # cm -> m

    density_variants = config.get_density_variants()
    if density_variants and "twig_density" in forest_data.columns:
        logger.info("Density variants active -- CSV twig_density column ignored")

    exported_files = []
    for cycle, species_snapshots in tqdm(snapshots.items(), desc="Exporting stages", disable=not is_verbose()):
        for species_name, tree_data_list in species_snapshots.items():
            # Get fids and max cycles for this species from forest data
            species_rows = forest_data[forest_data["species"] == species_name]

            for tree_idx, (model, skeleton, bones_info, height, _dbh) in enumerate(
                tree_data_list
            ):
                # Get tree's fid and max cycles before skip checks
                if tree_idx < len(species_rows):
                    tree_row = species_rows.iloc[tree_idx]
                    fid = int(tree_row["fid"])
                    tree_twig_density = (
                        float(tree_row["twig_density"])
                        if "twig_density" in tree_row.index and pd.notna(tree_row.get("twig_density"))
                        else None
                    )
                    tree_individual_type = (
                        str(tree_row["individual_type"]).strip()
                        if "individual_type" in tree_row.index and pd.notna(tree_row.get("individual_type"))
                        else None
                    )
                else:
                    fid = tree_idx + 1
                    tree_twig_density = None
                    tree_individual_type = None

                if model is None:
                    logger.warning(
                        "  Skipping %s tree %d (fid=%d) at cycle %d: model is None",
                        species_name,
                        tree_idx,
                        fid,
                        cycle,
                    )
                    continue

                # Only export trees that triggered a milestone crossing at this
                # cycle.  milestone_map tells us which tree crossed which height.
                cycle_milestones = milestone_map.get(cycle, {}).get(species_name, {})
                if tree_idx not in cycle_milestones:
                    continue

                # Skip trees not in export filter (they still participated in growth simulation)
                if export_tree_ids is not None and fid not in export_tree_ids:
                    continue

                # Generate filename with height and DBH (tree ID is in folder name)
                species_clean = (
                    "".join(
                        c for c in species_name if c.isalnum() or c in (" ", "-", "_")
                    )
                    .strip()
                    .replace(" ", "_")
                    .replace("-", "_")
                    .lower()
                )
                # Use milestone height for clean filenames (e.g., h04m, h08m)
                # In height-threshold mode, the milestone is the exact threshold
                # the tree crossed. In legacy mode, use actual height.
                height_for_filename = cycle_milestones.get(tree_idx, height)
                height_str = format_height_for_filename(height_for_filename)
                # Use yield table target DBH when available
                # Prefer height-DBH model (allometric, height-driven) over age-indexed curve
                grove_dbh = _dbh if _dbh else 0.0
                filename_dbh = grove_dbh
                target_dbh_m = None
                if species_name not in h_dbh_model_cache:
                    h_dbh_model_cache[species_name] = load_height_dbh_model_from_preset(
                        config.get_preset_path(species_name)
                    )
                    if not h_dbh_model_cache[species_name]:
                        target_dbh_cache[species_name] = load_target_dbh_from_preset(
                            config.get_preset_path(species_name)
                        )
                sp_h_dbh_model = h_dbh_model_cache[species_name]
                if sp_h_dbh_model and height > 0:
                    target_dbh_m = predict_dbh_from_height_model(height, sp_h_dbh_model)
                    filename_dbh = target_dbh_m
                elif target_dbh_cache.get(species_name):
                    cidx = min(cycle - 1, len(target_dbh_cache[species_name]) - 1)
                    if cidx >= 0:
                        target_dbh_m = target_dbh_cache[species_name][cidx]
                        filename_dbh = target_dbh_m

                # CSV DBH override: when the input CSV specifies a non-zero DBH,
                # use that as the target instead of the yield table value
                csv_dbh_for_tree = csv_dbh_map.get(fid)
                dbh_from_csv = False
                if csv_dbh_for_tree and csv_dbh_for_tree > 0:
                    target_dbh_m = csv_dbh_for_tree
                    filename_dbh = csv_dbh_for_tree
                    dbh_from_csv = True

                # Shared per-tree work (independent of density variant)
                twig_usd_map = get_twig_usd_map_for_species(
                    species_name, config, prefer_skeletal=True, prefer_static=False
                )
                try:
                    model.triangulate()
                except Exception:
                    logger.warning("Model triangulation failed for %s", species_name)

                tree_radial_scale = 1.0
                if config.calibration_align_dbh and target_dbh_m and grove_dbh > 0.001:
                    tree_radial_scale = target_dbh_m / grove_dbh
                    if dbh_from_csv:
                        tree_radial_scale = max(0.1, min(tree_radial_scale, 5.0))
                    else:
                        tree_radial_scale = max(0.5, min(tree_radial_scale, 2.0))

                # Use the actual DBH after clamped radial scaling for the filename,
                # so the filename reflects what the exported mesh actually shows.
                if tree_radial_scale != 1.0 and grove_dbh > 0.001:
                    filename_dbh = grove_dbh * tree_radial_scale

                dbh_str = format_dbh_for_filename(filename_dbh)
                dims_suffix = f"{height_str}_{dbh_str}"

                use_skeletal = config.export_skeletal
                use_static_only = not use_skeletal and config.export_static

                # Build export iterations: one per density variant, or single default
                if density_variants:
                    export_iterations = [
                        (vname, vcfg["twig_density"])
                        for vname, vcfg in density_variants
                    ]
                else:
                    export_iterations = [(None, tree_twig_density)]

                for variant_idx, (variant_name, effective_twig_density) in enumerate(
                    export_iterations
                ):
                    # Build output directory and filename prefix
                    if tree_individual_type:
                        tree_dir = output_dir / species_clean / tree_individual_type
                        density_str = (
                            variant_name
                            if variant_name
                            else format_density_for_filename(effective_twig_density)
                        )
                        individual_short = (
                            "comp" if "comp" in tree_individual_type else "open"
                        )
                        species_title = (
                            species_clean.replace("_", " ").title().replace(" ", "_")
                        )
                        file_prefix = f"{species_title}_{individual_short}_{dims_suffix}_{density_str}"
                    else:
                        tree_dir = output_dir / species_clean / f"tree_{fid:04d}"
                        if variant_name:
                            file_prefix = f"{species_clean}_{dims_suffix}_{variant_name}"
                        else:
                            file_prefix = f"{species_clean}_{dims_suffix}"
                    tree_dir.mkdir(parents=True, exist_ok=True)

                    usd_path = tree_dir / f"{file_prefix}_assembly{config.usd_ext}"

                    # Export as Nanite Assembly
                    try:
                        captured_twig_placements = {}
                        export_success = export_tree_as_nanite_assembly(
                            model=model,
                            skeleton=skeleton if use_skeletal else None,
                            bones_info=bones_info if use_skeletal else None,
                            output_path=usd_path,
                            species_name=species_name,
                            tree_id=None,
                            twig_usd_paths=twig_usd_map,
                            include_twigs=True,
                            use_skeletal_mesh=use_skeletal,
                            use_static_mesh=use_static_only,
                            include_grove_attributes=include_grove_attributes,
                            validate=not skip_validation,
                            timer=timer,
                            stems_file_suffix=dims_suffix,
                            radial_scale=tree_radial_scale,
                            twig_density=effective_twig_density,
                            twig_placements_out=captured_twig_placements,
                            instances_dir=instances_dir,
                        )
                    except ValueError as e:
                        if _is_bone_limit_error(e):
                            _handle_bone_limit_error(e)
                        raise

                    if export_success:
                        exported_files.append(str(usd_path))
                        logger.info("  Exported: %s", usd_path.name)

                        # Preview and static derivation only for first variant
                        if variant_idx == 0:
                            stems_base = f"{species_clean}_{dims_suffix}"

                            # DynamicWind JSON for Unreal import
                            if use_skeletal:
                                from growpy.io.unreal.wind_json import generate_wind_json

                                wind_json_path = (
                                    tree_dir / f"{file_prefix}_stems_unreal_wind.json"
                                )
                                try:
                                    with timer.track("generate_wind_json"):
                                        generate_wind_json(
                                            tree_usd_path=tree_dir / f"{stems_base}_stems_skeletal{config.usd_ext}",
                                            skeleton=skeleton,
                                            bones_info=bones_info,
                                            output_path=wind_json_path,
                                        )
                                except Exception as wind_error:
                                    logger.warning(
                                        "Failed to generate wind JSON for %s fid=%d: %s",
                                        species_name,
                                        fid,
                                        wind_error,
                                    )
                                    logger.debug("Wind JSON traceback:", exc_info=True)

                            # PVE preset JSON (optional)
                            skip_pve = quality_params.get("skip_pve_json", False)
                            if use_skeletal and not skip_pve:
                                from growpy.io.unreal.pve_grove_mapper import generate_pve_from_grove

                                pve_json_path = tree_dir / f"{file_prefix}_stems_unreal_pve.json"
                                pve_config_dir = Path("data/assets/pve_configs")
                                grove_for_species = species_grove_map.get(species_name)

                                try:
                                    with timer.track("generate_pve_json"):
                                        generate_pve_from_grove(
                                            grove=grove_for_species,
                                            output_path=pve_json_path,
                                            species_name=species_name,
                                            tree_index=tree_idx,
                                            model=model,
                                            skeleton=skeleton,
                                            bones_info=bones_info,
                                            verbose=True,
                                            pve_config_dir=pve_config_dir,
                                        )
                                except Exception as pve_error:
                                    logger.warning(
                                        "Failed to generate PVE preset JSON for %s fid=%d: %s",
                                        species_name,
                                        fid,
                                        pve_error,
                                    )
                                    logger.debug("PVE JSON traceback:", exc_info=True)

                            preview_bounds = _generate_preview_image(
                                tree_dir, species_clean, file_prefix, skeleton, timer
                            )
                            _generate_export_control_image(
                                tree_dir, species_clean, file_prefix, timer,
                                view_bounds=preview_bounds,
                                stems_file_base=stems_base,
                            )
                            _generate_icon_image(
                                tree_dir, file_prefix, skeleton, timer
                            )

                            if use_skeletal and config.export_static:
                                static_path = _derive_static_from_skeletal(
                                    tree_dir=tree_dir,
                                    species_clean=species_clean,
                                    species_name=species_name,
                                    tree_id=None,
                                    model=model,
                                    twig_usd_map=twig_usd_map,
                                    skip_validation=skip_validation,
                                    stems_suffix=dims_suffix,
                                    twig_placements=captured_twig_placements or None,
                                    instances_dir=instances_dir,
                                )
                                if static_path:
                                    exported_files.append(static_path)
                    else:
                        logger.warning(
                            "  Export failed for tree %d (%s) at cycle %d (h=%.1fm)",
                            fid,
                            species_name,
                            cycle,
                            height,
                        )

    logger.info("\nExported %d tree stage files", len(exported_files))


def generate_forest_exports(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    quality: str = "high",
    growth_cycle_limit: Optional[int] = None,
    smooth_iterations: Optional[int] = None,
    include_grove_attributes: bool = False,
    verbose: bool = False,
    preset_overrides: Optional[PresetOverrides] = None,
    timer: Optional["ProfileTimer"] = None,
    skip_pve_json: bool = False,
    skip_validation: bool = False,
    skeleton_overrides: Optional[Dict[str, Any]] = None,
    export_tree_ids: Optional[set] = None,
) -> None:
    """Generate forest from CSV data and export as Nanite Assembly USD files.

    Export types are controlled by config flags (export_skeletal, export_static).

    DynamicWind attributes are now embedded directly in the USD skeleton prim
    (unreal:dynamicWind:jointNames, unreal:dynamicWind:jointSimulationGroups).

    Args:
        csv_path: Path to CSV file with forest data
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality: Quality preset name ('ultra', 'high', 'medium', 'low', 'performance')
        growth_cycle_limit: Maximum growth cycles per tree (default: GROWTH_CYCLE_LIMIT)
        smooth_iterations: Number of smoothing iterations for branches (default: SMOOTH_ITERATIONS)
                          Higher values (10-20) produce smoother branches, 0 disables smoothing
        include_grove_attributes: If True, include Grove metadata in USD files (increases size ~70%)
        verbose: Print detailed progress information
        preset_overrides: Optional PresetOverrides for dynamic parameter adjustment during simulation
        timer: Optional ProfileTimer for tracking execution times
        skip_pve_json: If True, skip PVE preset JSON generation (saves ~3% export time)
        skip_validation: If True, skip assembly validation (saves ~5-10% export time)
    """
    from growpy.utils.profiling import ProfileTimer

    if timer is None:
        timer = ProfileTimer(enabled=False)

    # Clear twig file copy cache at start of export session
    from growpy.io.usd.assembly_export import clear_twig_copy_cache

    clear_twig_copy_cache()

    # Use defaults if not specified
    if growth_cycle_limit is None:
        growth_cycle_limit = GROWTH_CYCLE_LIMIT
    if smooth_iterations is None:
        smooth_iterations = SMOOTH_ITERATIONS

    if not TREE_EXPORT_AVAILABLE:
        logger.error("Tree export not available (missing dependencies)")
        return

    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        return

    # Load forest data
    try:
        with timer.track("load_csv"):
            forest_data = pd.read_csv(csv_path)
            required_columns = ["x", "y", "species", "height"]

            # Check required columns
            missing_cols = [
                col for col in required_columns if col not in forest_data.columns
            ]
            if missing_cols:
                logger.error("Missing required columns: %s", missing_cols)
                return

            # Z column will be added by create_forest if missing

    except Exception as e:
        logger.error("Error loading CSV: %s", e)
        return

    # Cap tree heights if max_height is configured
    if config.forest_max_height > 0:
        original_max = forest_data["height"].max()
        forest_data["height"] = forest_data["height"].clip(
            upper=config.forest_max_height
        )
        logger.info(
            "Max height cap: %.1fm (original max: %.1fm)",
            config.forest_max_height,
            original_max,
        )

    with timer.track("calculate_growth_cycles"):
        try:
            calculate_growth_cycles_from_height(forest_data)
        except Exception as e:
            logger.warning("Could not calculate growth cycles from height: %s", e)
            logger.warning("  Using default: growth_cycles=10, delay=0")
            forest_data["growth_cycles"] = 10
            forest_data["delay"] = 0

        # Cap each tree's cycles individually at the limit
        forest_data["growth_cycles"] = forest_data["growth_cycles"].clip(
            upper=growth_cycle_limit, lower=1
        )

        # Recalculate delays after clipping
        max_cycles_after_clip = forest_data["growth_cycles"].max()
        forest_data["delay"] = max_cycles_after_clip - forest_data["growth_cycles"]

    try:
        with timer.track("create_forest"):
            forest = create_forest(forest_data)
        max_cycles = forest_data["growth_cycles"].max()
        # Smoothing is applied automatically during simulation:
        # 1. smooth_minimal() - Fixes ugly kinks on thick branches
        # 2. smooth() - Reduces sharp corner angles (smooth_iterations times)
        # 3. weigh_and_bend() - Re-calculates branch positions with smoothed angles
        with timer.track("simulate_forest_growth"):
            simulate_forest_growth(
                forest,
                max_cycles,
                smooth_iterations=smooth_iterations,
                preset_overrides=preset_overrides,
                use_species_curves=config.calibration_align_height,
            )
    except Exception as e:
        logger.error("Error creating/simulating forest: %s", e)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get quality settings
    quality_params = get_quality_preset(quality)

    # Hardcode skeleton parameters
    quality_params["skeleton_bias"] = 0.5
    quality_params["skeleton_connected"] = True

    # Apply skeleton overrides (allows simplified skeleton with ultra mesh)
    if skeleton_overrides:
        for key, value in skeleton_overrides.items():
            quality_params[key] = value
        logger.info("[Skeleton Overrides] Applied: %s", skeleton_overrides)

    # CRITICAL: Force minimal export for Nanite compatibility
    # Skeletal meshes: geometry + skeleton only (no materials/textures/attributes)
    # Grove attributes can be optionally added via include_grove_attributes flag
    quality_params["minimal_export"] = True

    # Include Grove attributes if requested (adds ~70% file size to skeletal meshes)
    quality_params["include_grove_attributes"] = include_grove_attributes

    # Skip optional JSON generation (passed via quality_params for simplicity)
    # Note: DynamicWind JSON is always generated for skeletal meshes
    quality_params["skip_pve_json"] = skip_pve_json
    quality_params["skip_validation"] = skip_validation
    quality_params["profile_pve"] = (
        timer.enabled
    )  # Enable PVE profiling when --profile is set
    quality_params["export_tree_ids"] = export_tree_ids

    try:
        # Twigs/foliage are copied to shared Instances/ directory by assembly_export
        # Ensure shared instances directory exists (don't wipe -- other species may share it)
        instances_dir = output_dir / "Instances"
        instances_dir.mkdir(parents=True, exist_ok=True)

        # Export types controlled by config.export_skeletal / config.export_static
        with timer.track("export_trees"):
            export_individual_trees(
                forest,
                forest_data,
                output_dir,
                config,
                quality_params,
                verbose=verbose,
                timer=timer,
            )

    except ValueError as e:
        if _is_bone_limit_error(e):
            _handle_bone_limit_error(e)
        raise

    except Exception as e:
        logger.warning("Export failed: %s", e)


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
        type=str,
        default=None,
        choices=["true", "false"],
        help="Use connected bone chains (true=more bones, false=fewer bones). Default: true",
    )
    parser.add_argument(
        "--import-to-unreal",
        action="store_true",
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
        action="store_true",
        help="Include Grove metadata attributes (age, mass, vigor, etc.) in USD files for analysis (increases file size ~70%%). Note: PVE preset JSON files are always generated automatically",
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
        action="store_true",
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
        action="store_true",
        help="Enable profiling to track execution time of each processing step",
    )
    # Note: --skip-wind-json removed - wind data now embedded in USD skeleton
    parser.add_argument(
        "--skip-pve-json",
        action="store_true",
        help="Skip PVE preset JSON generation (saves ~3%% of export time)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip assembly validation (saves ~5-10%% of export time)",
    )

    # Mesh type export flags (independent, any combination works)
    parser.add_argument(
        "--skeletal",
        action="store_true",
        default=None,
        help="Enable skeletal mesh export (default: from config, typically True)",
    )
    parser.add_argument(
        "--no-skeletal",
        action="store_true",
        default=None,
        help="Disable skeletal mesh export",
    )
    parser.add_argument(
        "--static",
        action="store_true",
        default=None,
        help="Enable static mesh export (default: from config, typically False)",
    )
    parser.add_argument(
        "--no-static",
        action="store_true",
        default=None,
        help="Disable static mesh export",
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
        "--competition-distance-increase",
        type=float,
        default=None,
        help="Move competition neighbor trees outward by this many meters at "
        "each height interval to simulate thinning. 0 = no movement (default). "
        "Only affects neighbor trees (fid >= 100) in height-threshold mode.",
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
        action="store_true",
        help="Export OBJ/MTL files for Helios++ LiDAR simulation (post-processes USDA files)",
    )
    parser.add_argument(
        "--helios-scene",
        action="store_true",
        help="Generate Helios++ scene XML placing all tree OBJs at CSV positions (implies --export-obj)",
    )
    parser.add_argument(
        "--individual-obj",
        action="store_true",
        help="Also write individual per-tree OBJ files (default: only combined OBJ)",
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

    # Resolve config: TOML defaults + CLI overrides
    config = get_config()
    config.resolve(args)

    # --quiet overrides --verbose and config
    if args.quiet:
        config.verbose = False

    from growpy.utils.log import setup_logging

    setup_logging(verbose=config.verbose)

    # Validate export flags
    do_export_obj = config.helios_export_obj or config.helios_helios_scene
    if do_export_obj and not config.export_skeletal and not config.export_static:
        logger.warning(
            "OBJ export requires mesh generation, enabling static mesh export"
        )
        config.export_static = True

    if not config.export_skeletal and not config.export_static:
        logger.error(
            "No mesh export types enabled. "
            "Enable at least one of: --skeletal, --static, or --export-obj"
        )
        return

    # Initialize profiler
    timer = init_profiler(enabled=config.profile)

    try:
        csv_path = config.csv_file
        if not csv_path.is_absolute():
            csv_path = script_dir / csv_path

        if not csv_path.exists():
            logger.error("CSV file not found: %s", csv_path)
            return

        output_dir = config.output_dir
        if not output_dir.is_absolute():
            output_dir = script_dir / output_dir

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

        skip_pve_json = config.export_skip_pve_json
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
                    csv_path,
                    output_dir,
                    config,
                    config.forest_quality,
                    height_interval=config.forest_height_interval,
                    growth_cycle_limit=config.forest_growth_cycle_limit,
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
                    csv_path,
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
                simp_leaf = None
                if config.helios_simplification_enabled:
                    simp_ratios = config.helios_simplification_ratios
                    simp_leaf = config.helios_simplification_leaf_per_species
                export_forest_obj(
                    output_dir=output_dir,
                    csv_path=csv_path,
                    generate_scene_xml=config.helios_helios_scene,
                    individual_obj=config.helios_individual_obj,
                    up_axis=config.helios_obj_up_axis,
                    timer=timer,
                    simplification_ratios=simp_ratios,
                    leaf_per_species=simp_leaf,
                )

        # Print profiling report if enabled
        if config.profile:
            timer.print_report()

        # Generate Unreal scripts if requested
        if config.unreal_import_to_unreal and not getattr(args, 'no_unreal_scripts', False):
            # Create combined twig wrappers for efficient UE import
            from growpy.io.usd.assembly_export import create_combined_twig_usda

            instances_dir = output_dir / "Instances"
            if instances_dir.exists():
                combined = create_combined_twig_usda(
                    instances_dir, include_static=config.export_static
                )
                if combined:
                    logger.info(
                        "Created %d combined twig files for UE import",
                        len(combined),
                    )

            # Load forest data for tree positions
            try:
                forest_data = pd.read_csv(csv_path)
                # Ensure fid column exists
                if "fid" not in forest_data.columns:
                    forest_data["fid"] = range(1, len(forest_data) + 1)
            except Exception as e:
                logger.warning("Could not load CSV for position data: %s", e)
                forest_data = None

            import_script = generate_unreal_import_script(
                output_dir,
                config.unreal_project_path,
                forest_data=forest_data,
                export_tree_ids=export_tree_ids,
                include_static=config.export_static,
            )

            cleanup_script = generate_unreal_cleanup_script(
                output_dir,
                config.unreal_project_path,
                dry_run=True,  # Default to dry-run mode for safety
            )

            logger.info("\n%s", "=" * 60)
            logger.info("UNREAL SCRIPTS GENERATED")
            logger.info("%s", "=" * 60)
            logger.info("Import script: %s", import_script)
            logger.info("Cleanup script: %s", cleanup_script)
            logger.info("\nTo import trees to Unreal Engine:")
            logger.info("1. Open import_forest.py in VSCode")
            logger.info("2. Right-click > 'Execute Python File in Unreal'")
            logger.info("\nTo cleanup assets:")
            logger.info("1. Open clean_assets.py in VSCode")
            logger.info("2. Review DRY_RUN setting (True = preview, False = delete)")
            logger.info("3. Right-click > 'Execute Python File in Unreal'")
            logger.info("\nRequirements:")
            logger.info("- Unreal Engine must be running")
            logger.info("- USD Importer plugin enabled")
            logger.info("- Editor Scripting Utilities plugin enabled")

        # Pipeline completion summary (always visible, even in quiet mode)
        total_time = timer.get_total_time() if timer.enabled else 0
        skip_dirs = {"unreal_scripts", "Instances", "helios"}
        tree_count = len(list(output_dir.glob(f"*/**/*_assembly*{config.usd_ext}"))) if output_dir.exists() else 0
        species_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name not in skip_dirs] if output_dir.exists() else []
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


if __name__ == "__main__":
    main()
