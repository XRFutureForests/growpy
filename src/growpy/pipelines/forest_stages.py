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
from collections.abc import Callable

import bpy  # noqa: F401  (required; generate_forest_stages runs Grove via bpy)
import pandas as pd
from tqdm import tqdm

from growpy import (
    GrowPyConfig,
    create_forest,
)
from growpy.config.paths import _find_species_row, radius_label
from growpy.config.preset_overrides import (
    PresetOverrides,
    load_target_dbh_from_preset,
    predict_dbh_from_height_model,
)
from growpy.config.quality import get_quality_preset
from growpy.core.forest import simulate_forest_growth_with_snapshots
from growpy.io.forest_export import export_individual_trees  # noqa: F401
from growpy.io.usd.assembly_export import export_tree_as_nanite_assembly
from growpy.io.usd.preview import (
    generate_export_control_image as _generate_export_control_image,
)
from growpy.io.usd.preview import generate_icon_image as _generate_icon_image
from growpy.io.usd.preview import generate_preview_image as _generate_preview_image
from growpy.io.usd.tree_export import (
    derive_static_from_skeletal as _derive_static_from_skeletal,
)
from growpy.io.usd.tree_export import (
    get_twig_usd_map_for_species,
)
from growpy.io.usd.tree_export import (
    handle_bone_limit_error as _handle_bone_limit_error,
)
from growpy.io.usd.tree_export import is_bone_limit_error as _is_bone_limit_error
from growpy.pipelines.tree_export_context import TreeExportContext
from growpy.utils.allometry import correction_weight, get_height_dbh_model
from growpy.utils.export_naming import (
    format_dbh_for_filename,
    format_density_for_filename,
    format_height_for_filename,
)
from growpy.utils.naming import filename_safe_species_slug
from growpy.utils.profiling import ProfileTimer

GROWTH_CYCLE_LIMIT = 10
SMOOTH_ITERATIONS = 10

logger = logging.getLogger(__name__)


def _load_species_max_heights(species_names: list[str]) -> dict[str, float]:
    """Resolve each species' milestone ceiling (m) from the authored lookup table.

    ``tree_asset_lookup.csv``'s ``Max Height`` column is the single source of
    truth: it is what defines the dataset (see
    ``dataset_csv_planner._get_dataset_species``) and therefore what the stage
    count must follow.

    This used to derive the ceiling from the simulated growth model instead,
    which produced the wrong stage count for 10 of 11 dataset species. The
    growth models are bounded by ``[growth_models] max_height`` (20 m), so their
    Chapman-Richards asymptotes either pinned at the 5x guard and fell back to
    the observed ~20 m -- truncating Douglas fir to 4 stages instead of 9 -- or,
    where the fit did converge, ran away from the authored value entirely
    (Scots pine: 55 m, i.e. 11 stages, for a species authored at 30 m).

    Species missing from the lookup table are omitted, leaving them with no
    ceiling (they run to plateau or the cycle cap).
    """
    from growpy.config.paths import _find_species_row

    result: dict[str, float] = {}
    for species in species_names:
        try:
            row = _find_species_row(species)
        except ValueError:
            logger.warning(
                "No lookup entry for %s -- no height ceiling applied", species
            )
            continue

        max_height = row.get("Max Height")
        if max_height is None or pd.isna(max_height):
            logger.warning(
                "%s has no Max Height in tree_asset_lookup.csv -- "
                "no height ceiling applied",
                species,
            )
            continue

        result[species] = float(max_height)
    return result


def _warn_uncaptured_milestones(
    milestone_map: dict,
    species_max_height: dict[str, float],
    interval: float,
    max_cycles: int,
) -> None:
    """Warn when a species failed to capture every milestone up to its ceiling.

    Falling short is silent otherwise -- the run simply exports fewer stages --
    so a species that outgrows the cycle cap looks identical to one that was
    never meant to go higher. Cycles needed is roughly ceiling / growth rate,
    where the realized rate ranges about 0.23-0.55 m/cycle across the dataset
    species, so a shortfall usually means ``[forest] growth_cycle_limit`` is
    too low rather than anything being wrong with the species.
    """
    if not species_max_height:
        return

    captured: dict[str, set] = {}
    for species_snapshots in milestone_map.values():
        for species_name, tree_milestones in species_snapshots.items():
            captured.setdefault(species_name, set()).update(tree_milestones.values())

    for species, ceiling in sorted(species_max_height.items()):
        expected = set()
        m = interval
        while m <= ceiling:
            expected.add(m)
            m += interval
        missing = sorted(expected - captured.get(species, set()))
        if missing:
            logger.warning(
                "%s reached only %.0fm of its %.0fm target: %d stage(s) missing "
                "(%s). Raise [forest] growth_cycle_limit (currently %d) or lower "
                "Max Height for this species.",
                species,
                max(captured.get(species, {0.0})),
                ceiling,
                len(missing),
                ", ".join(f"{h:.0f}m" for h in missing),
                max_cycles,
            )


def _write_species_info(
    species_dir: Path, species_name: str, species_clean: str
) -> None:
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


def resolve_target_dbh(
    ctx: TreeExportContext,
    cycle: int,
    h_dbh_model_cache: dict[str, dict[str, float] | None],
    target_dbh_cache: dict[str, list],
    csv_dbh_map: dict[int, float],
) -> None:
    """Resolve this tree's target DBH from height-DBH allometry (species-level,
    memoized in the caller-owned caches) with CSV DBH as the highest-priority
    override.

    Sets ctx.target_dbh_m, ctx.dbh_from_csv, and a provisional ctx.filename_dbh
    (compute_radial_scale() may adjust the latter further once radial_scale is
    known).
    """
    filename_dbh = ctx.grove_dbh
    target_dbh_m = None
    if ctx.species_name not in h_dbh_model_cache:
        # Allometry artifact first (simulation-free, radius-invariant); the
        # seed.json calibration block is a fallback for presets that have not
        # been regenerated yet.
        h_dbh_model_cache[ctx.species_name] = get_height_dbh_model(
            ctx.species_name, ctx.cfg.get_preset_path(ctx.species_name)
        )
        if not h_dbh_model_cache[ctx.species_name]:
            target_dbh_cache[ctx.species_name] = load_target_dbh_from_preset(
                ctx.cfg.get_preset_path(ctx.species_name)
            )
    sp_h_dbh_model = h_dbh_model_cache[ctx.species_name]
    if sp_h_dbh_model and ctx.height > 0:
        target_dbh_m = predict_dbh_from_height_model(ctx.height, sp_h_dbh_model)
        filename_dbh = target_dbh_m
    elif target_dbh_cache.get(ctx.species_name):
        cidx = min(cycle - 1, len(target_dbh_cache[ctx.species_name]) - 1)
        if cidx >= 0:
            target_dbh_m = target_dbh_cache[ctx.species_name][cidx]
            filename_dbh = target_dbh_m

    # CSV DBH override: when the input CSV specifies a non-zero DBH, use that
    # as the target instead of the yield table value.
    csv_dbh_for_tree = csv_dbh_map.get(ctx.fid)
    dbh_from_csv = False
    if csv_dbh_for_tree and csv_dbh_for_tree > 0:
        target_dbh_m = csv_dbh_for_tree
        filename_dbh = csv_dbh_for_tree
        dbh_from_csv = True

    ctx.target_dbh_m = target_dbh_m
    ctx.dbh_from_csv = dbh_from_csv
    ctx.filename_dbh = filename_dbh


def compute_radial_scale(ctx: TreeExportContext) -> None:
    """Post-hoc radial scaling toward the height-DBH allometry target.

    Sets ctx.radial_scale and adjusts ctx.filename_dbh so the filename
    reflects the actually-exported mesh after clamping.
    """
    radial_scale = 1.0
    if (
        ctx.cfg.export_dbh_from_allometry
        and ctx.target_dbh_m
        and ctx.grove_dbh > 0.001
    ):
        radial_scale = ctx.target_dbh_m / ctx.grove_dbh
        if ctx.dbh_from_csv:
            radial_scale = max(0.1, min(radial_scale, 5.0))
        else:
            radial_scale = max(0.5, min(radial_scale, 2.0))
            # Below the yield table's own height range the model is
            # extrapolating; fade the correction out and leave Grove's
            # pipe-model diameter alone for saplings.
            w = correction_weight(ctx.species_name, ctx.height)
            if w < 1.0:
                radial_scale = 1.0 + (radial_scale - 1.0) * w

    # Use the actual DBH after clamped radial scaling for the filename, so the
    # filename reflects what the exported mesh actually shows.
    if radial_scale != 1.0 and ctx.grove_dbh > 0.001:
        ctx.filename_dbh = ctx.grove_dbh * radial_scale

    ctx.radial_scale = radial_scale


def export_assembly(ctx: TreeExportContext) -> None:
    """Export this tree+variant as a Nanite skeletal/static USD assembly.

    Sets ctx.usd_path, ctx.export_success, and ctx.twig_placements (captured
    for derive_static()). Re-raises bone-limit ValueErrors after logging,
    same as before extraction.
    """
    ctx.usd_path = ctx.tree_dir / f"{ctx.file_prefix}_assembly{ctx.cfg.usd_ext}"
    ctx.twig_placements = {}
    try:
        ctx.export_success = export_tree_as_nanite_assembly(
            model=ctx.model,
            skeleton=ctx.skeleton if ctx.use_skeletal else None,
            bones_info=ctx.bones_info if ctx.use_skeletal else None,
            output_path=ctx.usd_path,
            species_name=ctx.species_name,
            tree_id=None,
            twig_usd_paths=ctx.twig_usd_map,
            include_twigs=True,
            use_skeletal_mesh=ctx.use_skeletal,
            use_static_mesh=ctx.use_static_only,
            include_grove_attributes=ctx.include_grove_attributes,
            validate=not ctx.skip_validation,
            timer=ctx.timer,
            stems_file_suffix=ctx.dims_suffix,
            radial_scale=ctx.radial_scale,
            twig_density=ctx.twig_density,
            twig_placements_out=ctx.twig_placements,
            instances_dir=ctx.instances_dir,
        )
    except ValueError as e:
        if _is_bone_limit_error(e):
            _handle_bone_limit_error(e)
        raise


def write_wind_json(ctx: TreeExportContext) -> None:
    """Generate DynamicWind JSON for Unreal import (skeletal exports only)."""
    if not (ctx.use_skeletal and ctx.cfg.unreal_generate_wind_data):
        return
    from growpy.io.unreal.wind_json import generate_wind_json

    stems_base = f"{ctx.species_clean}_{ctx.dims_suffix}"
    wind_json_path = ctx.tree_dir / f"{ctx.file_prefix}_stems_unreal_wind.json"
    try:
        with ctx.timer.track("generate_wind_json"):
            generate_wind_json(
                tree_usd_path=ctx.tree_dir
                / f"{stems_base}_stems_skeletal{ctx.cfg.usd_ext}",
                skeleton=ctx.skeleton,
                bones_info=ctx.bones_info,
                output_path=wind_json_path,
            )
    except Exception as wind_error:
        logger.warning(
            "Failed to generate wind JSON for %s fid=%d: %s",
            ctx.species_name,
            ctx.fid,
            wind_error,
        )
        logger.debug("Wind JSON traceback:", exc_info=True)


def write_pve_json(ctx: TreeExportContext) -> None:
    """Generate PVE preset JSON for Unreal import (skeletal exports only,
    unless the pipeline was asked to skip it)."""
    if not (ctx.use_skeletal and not ctx.skip_pve_json):
        return
    from growpy.io.unreal.pve_grove_mapper import generate_pve_from_grove

    pve_json_path = ctx.tree_dir / f"{ctx.file_prefix}_stems_unreal_pve.json"
    pve_config_dir = Path("data/assets/pve_configs")
    try:
        with ctx.timer.track("generate_pve_json"):
            generate_pve_from_grove(
                grove=ctx.grove,
                output_path=pve_json_path,
                species_name=ctx.species_name,
                tree_index=ctx.tree_idx,
                model=ctx.model,
                skeleton=ctx.skeleton,
                bones_info=ctx.bones_info,
                verbose=True,
                pve_config_dir=pve_config_dir,
            )
    except Exception as pve_error:
        logger.warning(
            "Failed to generate PVE preset JSON for %s fid=%d: %s",
            ctx.species_name,
            ctx.fid,
            pve_error,
        )
        logger.debug("PVE JSON traceback:", exc_info=True)


def write_previews(ctx: TreeExportContext) -> None:
    """Generate the preview image and export-control image for this tree."""
    stems_base = f"{ctx.species_clean}_{ctx.dims_suffix}"
    preview_bounds = _generate_preview_image(
        ctx.tree_dir, ctx.species_clean, ctx.file_prefix, ctx.skeleton, ctx.timer
    )
    _generate_export_control_image(
        ctx.tree_dir,
        ctx.species_clean,
        ctx.file_prefix,
        ctx.timer,
        view_bounds=preview_bounds,
        stems_file_base=stems_base,
    )


def write_icons(ctx: TreeExportContext) -> None:
    """Generate front/side/top icon images for this tree."""
    for _view in ("front", "side", "top"):
        _generate_icon_image(
            ctx.tree_dir, ctx.file_prefix, ctx.skeleton, ctx.timer, view=_view
        )


def derive_static(ctx: TreeExportContext) -> None:
    """Derive a static (non-skeletal) mesh variant, when both are enabled.

    Sets ctx.static_path (falsy when the gate doesn't apply or derivation
    produced nothing).
    """
    if not (ctx.use_skeletal and ctx.cfg.export_static):
        return
    ctx.static_path = _derive_static_from_skeletal(
        tree_dir=ctx.tree_dir,
        species_clean=ctx.species_clean,
        species_name=ctx.species_name,
        tree_id=None,
        model=ctx.model,
        twig_usd_map=ctx.twig_usd_map,
        skip_validation=ctx.skip_validation,
        stems_suffix=ctx.dims_suffix,
        twig_placements=ctx.twig_placements or None,
        instances_dir=ctx.instances_dir,
    )

# Post-assembly stage registry: (name, gate, stage_fn, once_per_tree).
#
# `gate(ctx)` decides whether the stage runs at all -- False logs a debug
# skip and moves on. `once_per_tree` marks stages that must run only for the
# first density variant (variant_idx == 0) rather than once per variant --
# see the once_per_tree check in generate_forest_stages() below (XRFF-290).
# Assembly itself isn't in this list: its result gates every stage after it,
# so generate_forest_stages() calls it directly (see below).
StageGate = Callable[[TreeExportContext], bool]
StageFn = Callable[[TreeExportContext], None]
STAGES: list[tuple[str, StageGate, StageFn, bool]] = [
    ("wind_json", lambda c: c.cfg.unreal_generate_wind_data, write_wind_json, True),
    ("pve_json", lambda c: not c.skip_pve_json, write_pve_json, True),
    ("preview", lambda c: c.cfg.export_previews, write_previews, True),
    ("icons", lambda c: c.cfg.export_icons, write_icons, True),
    ("static_derive", lambda c: c.cfg.export_static, derive_static, True),
]




def generate_forest_stages(
    forest_data: pd.DataFrame,
    output_dir: Path,
    config: GrowPyConfig,
    quality: str = "high",
    height_interval: float | None = None,
    growth_cycle_limit: int | None = None,
    plateau_cycles: int | None = None,
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

    Growth runs cycle by cycle and a stage is captured whenever a tree crosses
    the next height milestone (e.g. every 5m). No growth model is consulted to
    predict which cycle that will be, so how fast a species reaches a height
    does not affect which stages are produced -- only how long it takes.

    CSV Format (requires height column):
        fid,species,x,y,z,height
        1,Norway spruce,0,0,0,35.0

    Args:
        forest_data: Trees to build (requires columns: species, x, y, height).
            Either config-derived dataset job rows or a real spatial layout --
            see growpy.cli.generate_forest._resolve_forest_data.
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

    # Validate the caller-supplied frame. Height is required: it is what the
    # milestone ceiling is capped against.
    required_columns = ["x", "y", "species", "height"]
    missing_cols = [col for col in required_columns if col not in forest_data.columns]
    if missing_cols:
        logger.error("Missing required columns: %s", missing_cols)
        logger.error("  Multi-stage mode requires height to bound milestones")
        return

    forest_data = forest_data.copy()
    if "fid" not in forest_data.columns:
        forest_data["fid"] = range(1, len(forest_data) + 1)
    if "z" not in forest_data.columns:
        forest_data["z"] = 0.0

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
    quality_params["density_variants"] = config.get_density_variants()

    # Apply skeleton overrides (allows simplified skeleton with ultra mesh)
    if skeleton_overrides:
        for key, value in skeleton_overrides.items():
            quality_params[key] = value
        logger.info("[Skeleton Overrides] Applied: %s", skeleton_overrides)

    # Build species-to-grove mapping for PVE JSON generation
    species_grove_map: dict[str, Any] = {}
    for grove_obj, sp_name, _tc, _fids, *_r in forest:
        species_grove_map[sp_name] = grove_obj

    # Per-species height ceiling from the authored Max Height in the lookup
    # table. Bounds milestone capture so a species stops once it reaches its
    # own target height rather than running to the global cycle cap.
    species_max_height = _load_species_max_heights(
        list(forest_data["species"].unique())
    )
    if species_max_height:
        logger.info(
            "  Per-species height ceilings: %s",
            ", ".join(f"{sp} {h:.1f}m" for sp, h in sorted(species_max_height.items())),
        )

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
            species_max_height=species_max_height,
            plateau_cycles=plateau_cycles if plateau_cycles is not None else 10,
        )

    # A species that never reaches its ceiling silently produces fewer stages,
    # which is how the Douglas fir shortfall went unnoticed. Report it.
    _warn_uncaptured_milestones(
        milestone_map, species_max_height, effective_interval, global_max_cycles
    )

    if not snapshots:
        logger.error("No snapshots captured during simulation")
        return

    # Clean stale exports (only subdirectories that this CSV will write to)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Ensure shared instances directory exists (don't wipe -- other species may share it)
    instances_dir.mkdir(parents=True, exist_ok=True)
    has_radius_col = "surround_radius" in forest_data.columns
    for sp in forest_data["species"].unique():
        sp_dir_name = (
            "".join(c for c in sp if c.isalnum() or c in (" ", "-", "_"))
            .strip()
            .replace(" ", "_")
            .lower()
        )
        sp_dir = output_dir / sp_dir_name
        if has_radius_col:
            for radius in forest_data.loc[
                forest_data["species"] == sp, "surround_radius"
            ].unique():
                radius = float(radius) if pd.notna(radius) else 0.0
                sub = sp_dir / radius_label(radius)
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

            for tree_idx, (
                model,
                skeleton,
                bones_info,
                height,
                _dbh,
                variant_models,
            ) in enumerate(tree_data_list):
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
                    tree_surround_radius = (
                        float(tree_row["surround_radius"])
                        if "surround_radius" in tree_row.index
                        and pd.notna(tree_row.get("surround_radius"))
                        else 0.0
                    )
                else:
                    fid = tree_idx + 1
                    tree_twig_density = None
                    tree_surround_radius = 0.0

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
                species_clean = filename_safe_species_slug(species_name)
                # Use milestone height for clean filenames (e.g., h04m, h08m)
                # In height-threshold mode, the milestone is the exact threshold
                # the tree crossed. In legacy mode, use actual height.
                height_for_filename = cycle_milestones.get(tree_idx, height)
                height_str = format_height_for_filename(height_for_filename)
                grove_dbh = _dbh if _dbh else 0.0

                # Shared per-tree work (independent of density variant)
                twig_usd_map = get_twig_usd_map_for_species(
                    species_name, config, prefer_skeletal=True, prefer_static=False
                )
                try:
                    model.triangulate()
                except Exception:
                    logger.warning("Model triangulation failed for %s", species_name)

                use_skeletal = config.export_skeletal
                use_static_only = not use_skeletal and config.export_static

                ctx = TreeExportContext(
                    cfg=config,
                    species_name=species_name,
                    species_clean=species_clean,
                    fid=fid,
                    tree_idx=tree_idx,
                    height=height,
                    grove_dbh=grove_dbh,
                    skeleton=skeleton,
                    bones_info=bones_info,
                    twig_usd_map=twig_usd_map,
                    instances_dir=instances_dir,
                    timer=timer,
                    grove=species_grove_map.get(species_name),
                    use_skeletal=use_skeletal,
                    use_static_only=use_static_only,
                    skip_validation=skip_validation,
                    include_grove_attributes=include_grove_attributes,
                    skip_pve_json=quality_params.get("skip_pve_json", False),
                )
                resolve_target_dbh(
                    ctx, cycle, h_dbh_model_cache, target_dbh_cache, csv_dbh_map
                )
                compute_radial_scale(ctx)

                dbh_str = format_dbh_for_filename(ctx.filename_dbh)
                dims_suffix = f"{height_str}_{dbh_str}"
                ctx.dims_suffix = dims_suffix

                # Build export iterations: one per density variant, or single default
                if density_variants:
                    export_iterations = [
                        (vname, vcfg["twig_density"], variant_models.get(vname, model))
                        for vname, vcfg in density_variants
                    ]
                else:
                    export_iterations = [(None, tree_twig_density, model)]

                for variant_idx, (
                    variant_name,
                    effective_twig_density,
                    effective_model,
                ) in enumerate(export_iterations):
                    ctx.variant_name = variant_name
                    ctx.variant_idx = variant_idx
                    ctx.twig_density = effective_twig_density
                    ctx.model = effective_model

                    # Build output directory and filename prefix
                    if has_radius_col:
                        radius_lbl = radius_label(tree_surround_radius)
                        tree_dir = output_dir / species_clean / radius_lbl
                        density_str = (
                            variant_name
                            if variant_name
                            else format_density_for_filename(effective_twig_density)
                        )
                        individual_short = radius_lbl
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
                    ctx.tree_dir = tree_dir
                    ctx.file_prefix = file_prefix

                    if species_clean not in _species_info_written:
                        _write_species_info(
                            tree_dir.parent, species_name, species_clean
                        )
                        _species_info_written.add(species_clean)

                    # Export as Nanite Assembly
                    with timer.track("stage_assembly"):
                        export_assembly(ctx)

                    if ctx.export_success:
                        exported_files.append(str(ctx.usd_path))
                        logger.info("  Exported: %s", ctx.usd_path.name)

                        # Once-per-tree stages (wind/PVE/previews/icons/static)
                        # only run for the first density variant.
                        for stage_name, gate, stage_fn, once_per_tree in STAGES:
                            if once_per_tree and variant_idx != 0:
                                continue
                            if not gate(ctx):
                                logger.debug("stage %s skipped (gate)", stage_name)
                                continue
                            with timer.track(f"stage_{stage_name}"):
                                stage_fn(ctx)
                            if stage_name == "static_derive" and ctx.static_path:
                                exported_files.append(ctx.static_path)
                    else:
                        logger.warning(
                            "  Export failed for tree %d (%s) at cycle %d (h=%.1fm)",
                            fid,
                            species_name,
                            cycle,
                            height,
                        )

    logger.info("\nExported %d tree stage files", len(exported_files))
