"""Pipeline A: multi-stage forest generation with height-based snapshots.

Extracted from `cli/generate_forest.py`. This module holds pure pipeline
orchestration: it simulates forest growth and exports trees at height-interval
milestones. The CLI front-end (`growpy.cli.generate_forest`) parses arguments
and calls `generate_forest_stages()`.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

import bpy  # noqa: F401  (required; generate_forest_stages runs Grove via bpy)
import pandas as pd
from tqdm import tqdm

from growpy import (
    GrowPyConfig,
    create_forest,
)
from growpy.config.paths import _find_species_row
from growpy.config.preset_overrides import PresetOverrides
from growpy.config.quality import get_quality_preset
from growpy.core.forest import simulate_forest_growth_with_snapshots
from growpy.io.forest_export import export_individual_trees  # noqa: F401
from growpy.io.usd.preview import (
    generate_export_control_image as _generate_export_control_image,
)
from growpy.io.usd.preview import generate_icon_image as _generate_icon_image
from growpy.io.usd.preview import generate_preview_image as _generate_preview_image
from growpy.io.usd.tree_export import (
    derive_static_from_skeletal as _derive_static_from_skeletal,
)
from growpy.io.usd.tree_export import (
    handle_bone_limit_error as _handle_bone_limit_error,
)
from growpy.io.usd.tree_export import is_bone_limit_error as _is_bone_limit_error
from growpy.utils.export_naming import (
    format_dbh_for_filename,
    format_density_for_filename,
    format_height_for_filename,
)
from growpy.utils.profiling import ProfileTimer

GROWTH_CYCLE_LIMIT = 10
SMOOTH_ITERATIONS = 10

logger = logging.getLogger(__name__)


def _write_species_info(species_dir: Path, species_name: str, species_clean: str) -> None:
    """Write species_info.json with GBIF taxon key and taxonomy to species output dir."""
    try:
        row = _find_species_row(species_name, use_gbif=False)
        gbif_key = row.get("GBIF Key")
        if gbif_key and not (isinstance(gbif_key, float) and gbif_key != gbif_key):
            gbif_key = int(gbif_key)
        else:
            gbif_key = None
        info = {
            "common_name": row.get("Common Name", species_name),
            "standardized_name": species_clean,
            "scientific_name": row.get("Scientific Name", ""),
            "gbif_taxon_key": gbif_key,
        }
    except (ValueError, KeyError):
        info = {
            "common_name": species_name,
            "standardized_name": species_clean,
            "scientific_name": "",
            "gbif_taxon_key": None,
        }
    out_path = species_dir / "species_info.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    logger.debug("Species info: %s", out_path)


def generate_forest_stages(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    quality: str = "high",
    height_interval: float | None = None,
    growth_cycle_limit: int | None = None,
    smooth_iterations: int | None = None,
    include_grove_attributes: bool = False,
    verbose: bool = False,
    preset_overrides: PresetOverrides | None = None,
    timer: ProfileTimer | None = None,
    skip_pve_json: bool = False,
    skip_validation: bool = False,
    skeleton_overrides: dict[str, Any] | None = None,
    export_tree_ids: set | None = None,
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
    from growpy.utils.log import is_verbose
    from growpy.utils.profiling import ProfileTimer

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
    effective_max_height = (
        config.forest_max_height if config.forest_max_height > 0 else 0.0
    )
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
    species_grove_map: dict[str, Any] = {}
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
    h_dbh_model_cache: dict[str, dict[str, float] | None] = {}
    target_dbh_cache: dict[str, list] = {}

    # Build per-tree CSV DBH map (fid -> dbh in meters) for custom diameter scaling
    csv_dbh_map: dict[int, float] = {}
    if "dbh" in forest_data.columns:
        for _, row in forest_data.iterrows():
            val = row["dbh"]
            if pd.notna(val) and float(val) > 0:
                csv_dbh_map[int(row["fid"])] = float(val) / 100.0  # cm -> m

    density_variants = config.get_density_variants()
    if density_variants and "twig_density" in forest_data.columns:
        logger.info("Density variants active -- CSV twig_density column ignored")

    exported_files = []
    _species_info_written: set = set()
    for cycle, species_snapshots in tqdm(
        snapshots.items(), desc="Exporting stages", disable=not is_verbose()
    ):
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
                        if "twig_density" in tree_row.index
                        and pd.notna(tree_row.get("twig_density"))
                        else None
                    )
                    tree_individual_type = (
                        str(tree_row["individual_type"]).strip()
                        if "individual_type" in tree_row.index
                        and pd.notna(tree_row.get("individual_type"))
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
                            file_prefix = (
                                f"{species_clean}_{dims_suffix}_{variant_name}"
                            )
                        else:
                            file_prefix = f"{species_clean}_{dims_suffix}"
                    tree_dir.mkdir(parents=True, exist_ok=True)

                    if species_clean not in _species_info_written:
                        _write_species_info(
                            tree_dir.parent, species_name, species_clean
                        )
                        _species_info_written.add(species_clean)

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
                            if use_skeletal and config.unreal_generate_wind_data:
                                from growpy.io.unreal.wind_json import (
                                    generate_wind_json,
                                )

                                wind_json_path = (
                                    tree_dir / f"{file_prefix}_stems_unreal_wind.json"
                                )
                                try:
                                    with timer.track("generate_wind_json"):
                                        generate_wind_json(
                                            tree_usd_path=tree_dir
                                            / f"{stems_base}_stems_skeletal{config.usd_ext}",
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
                                from growpy.io.unreal.pve_grove_mapper import (
                                    generate_pve_from_grove,
                                )

                                pve_json_path = (
                                    tree_dir / f"{file_prefix}_stems_unreal_pve.json"
                                )
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
                                tree_dir,
                                species_clean,
                                file_prefix,
                                timer,
                                view_bounds=preview_bounds,
                                stems_file_base=stems_base,
                            )
                            for _view in ("front", "side", "top"):
                                _generate_icon_image(
                                    tree_dir, file_prefix, skeleton, timer, view=_view
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
