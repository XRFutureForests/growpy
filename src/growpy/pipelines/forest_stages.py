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
from collections.abc import Callable
from pathlib import Path
from typing import Any

import bpy  # noqa: F401  (required; generate_forest_stages runs Grove via bpy)
import pandas as pd

from growpy import (
    GrowPyConfig,
    create_forest,
)
from growpy.config.paths import _find_species_row, get_data_directory, radius_label
from growpy.config.preset_overrides import (
    PresetOverrides,
    load_target_dbh_from_preset,
    predict_dbh_from_height_model,
)
from growpy.config.quality import get_quality_preset
from growpy.core.forest import simulate_forest_growth_with_snapshots
from growpy.core.twig import extract_twig_placements_from_model
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
    run_max_height: float = 0.0,
    tree_radius_labels: dict[str, list[float]] | None = None,
) -> None:
    """Warn when a species failed to capture every milestone up to its ceiling.

    Falling short is silent otherwise -- the run simply exports fewer stages --
    so a species that outgrows the cycle cap looks identical to one that was
    never meant to go higher. Cycles needed is roughly ceiling / growth rate,
    where the realized rate ranges about 0.23-0.55 m/cycle across the dataset
    species, so a shortfall usually means ``[forest] growth_cycle_limit`` is
    too low rather than anything being wrong with the species.

    Checked per surround-radius tree, not pooled across a species' variants:
    milestones reached by the least-competed tree (typically r00) used to
    mask a denser variant (r08/r16) plateauing early under Grove's own
    shading dynamics, so a shortfall specific to one radius went unreported
    as long as any other radius for that species reached the ceiling.

    ``run_max_height`` clips the ceiling to this run's configured height cap
    (``[forest] max_height`` / ``--max-height``) when set, so a deliberately
    capped run (e.g. a 25m preview) is not warned about stages above its own
    cap that were never going to be captured. ``tree_radius_labels`` is an
    optional ``{species: [radius_m, ...]}`` (indexed by tree_idx) used to name
    which radius fell short instead of just its tree index.
    """
    if not species_max_height:
        return

    # captured[(species, tree_idx)] -- per-tree, not pooled across radii.
    captured: dict[tuple[str, int], set] = {}
    for species_snapshots in milestone_map.values():
        for species_name, tree_milestones in species_snapshots.items():
            for tree_idx, h in tree_milestones.items():
                captured.setdefault((species_name, tree_idx), set()).add(h)

    tree_idxs_by_species: dict[str, set[int]] = {}
    for species_name, tree_idx in captured:
        tree_idxs_by_species.setdefault(species_name, set()).add(tree_idx)

    for species, ceiling in sorted(species_max_height.items()):
        if run_max_height > 0:
            ceiling = min(ceiling, run_max_height)
        expected = set()
        m = interval
        while m <= ceiling:
            expected.add(m)
            m += interval
        if not expected:
            continue

        radii = tree_radius_labels.get(species) if tree_radius_labels else None
        tree_ids = (
            range(len(radii))
            if radii
            else sorted(tree_idxs_by_species.get(species, set())) or [None]
        )
        for tree_idx in tree_ids:
            reached = captured.get((species, tree_idx), set())
            missing = sorted(expected - reached)
            if not missing:
                continue
            if tree_idx is None:
                label = ""
            elif radii and tree_idx < len(radii):
                label = f" (r{radii[tree_idx]:.0f})"
            else:
                label = f" (tree {tree_idx})"
            logger.warning(
                "%s%s reached only %.0fm of its %.0fm target: %d stage(s) "
                "missing (%s). Raise [forest] growth_cycle_limit (currently "
                "%d), raise plateau_cycles, or lower Max Height for this "
                "species.",
                species,
                label,
                max(reached, default=0.0),
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
    if ctx.cfg.export_dbh_from_allometry and ctx.target_dbh_m and ctx.grove_dbh > 0.001:
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
            precut_model=ctx.precut_model,
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
    pve_config_dir = get_data_directory() / "assets" / "pve_configs"
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
                twig_density=ctx.twig_density if ctx.twig_density is not None else 1.0,
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
    """Generate the 2D preview image for this tree+variant.

    Stashes the resulting view bounds on the context so write_export_control()
    can frame its render identically when both stages run.

    Passes the final twig placements so the preview gets its foliage row. This
    is why the stage is NOT once_per_tree: the branch skeleton is identical
    across density variants, so a once-per-tree preview would show variant 0's
    crown and silently label it as every other variant's.
    """
    ctx.preview_bounds = _generate_preview_image(
        ctx.tree_dir,
        ctx.species_clean,
        ctx.file_prefix,
        ctx.skeleton,
        ctx.timer,
        twig_placements=ctx.twig_placements,
    )


def write_export_control(ctx: TreeExportContext) -> None:
    """Generate the export-control image for this tree.

    Gated separately from write_previews because this is by far the most
    expensive of the image stages -- 15.4% of a full dataset run, roughly 3x
    the preview itself. When previews are disabled ctx.preview_bounds is None
    and the control render picks its own bounds.
    """
    _generate_export_control_image(
        ctx.tree_dir,
        ctx.species_clean,
        ctx.file_prefix,
        ctx.timer,
        view_bounds=ctx.preview_bounds,
        stems_file_base=f"{ctx.species_clean}_{ctx.dims_suffix}",
    )


def write_icons(ctx: TreeExportContext) -> None:
    """Generate front/side/top icon images for this tree.

    Passes twig placements so each view also gets a ``_twigs`` variant. The
    plain icons stay unchanged -- dataset_overview.csv references those.

    When ``ctx.cfg.export_icon_components`` is on, also passes bones_info so
    each view additionally gets separate branches/twigsonly/skeleton/merged
    component files (see generate_icon_image). Off by default -- a
    production run does not pay for these unless asked.
    """
    for _view in ("front", "side", "top"):
        _generate_icon_image(
            ctx.tree_dir,
            ctx.file_prefix,
            ctx.skeleton,
            ctx.timer,
            view=_view,
            twig_placements=ctx.twig_placements,
            bones_info=ctx.bones_info if ctx.use_skeletal else None,
            export_components=ctx.cfg.export_icon_components,
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


def export_obj_direct(ctx: TreeExportContext) -> None:
    """Write this tree+variant directly to Helios++ OBJ/MTL, bypassing
    USD/skeleton/Nanite Assembly entirely (config.export_mode == "helios").

    Sets ctx.usd_path (the produced .obj path -- see TreeExportContext field
    naming, shared with export_assembly()) and ctx.export_success. Wind/PVE
    JSON, previews, icons, and static derivation do not apply in this mode --
    none of that is meaningful for an unskinned LiDAR mesh -- so STAGES
    never runs for a helios-mode tree; see generate_forest_stages().
    """
    from growpy.io.helios.classification import (
        MAX_TREES,
        build_classification_codes,
        build_material_prefix,
    )
    from growpy.io.helios.obj_export import convert_tree_to_obj_direct

    cfg = ctx.cfg
    simplification_ratios = None
    if cfg.helios_simplification_enabled:
        simplification_ratios = cfg.get_simplification_ratios(ctx.species_clean)

    mat_prefix = ""
    classification_codes = None
    if cfg.helios_classification and 1 <= ctx.fid <= MAX_TREES:
        classification_codes = build_classification_codes(ctx.fid)
        mat_prefix = build_material_prefix(ctx.fid)

    obj_path = convert_tree_to_obj_direct(
        model=ctx.model,
        twig_usd_map=ctx.twig_usd_map,
        output_dir=ctx.tree_dir,
        species_name=ctx.species_name,
        tree_id=str(ctx.fid),
        radial_scale=ctx.radial_scale,
        bones_info=ctx.bones_info,
        simplification_ratios=simplification_ratios,
        mat_prefix=mat_prefix,
        classification_codes=classification_codes,
        up_axis=cfg.helios_obj_up_axis,
    )

    ctx.usd_path = obj_path
    ctx.export_success = obj_path is not None


def export_icons_only(ctx: TreeExportContext) -> None:
    """Write icon PNGs directly from the Grove model (config.export_mode ==
    "icons_only"), bypassing USD/Nanite/wind/PVE/previews/export-control
    entirely.

    For parameter-tuning / visual-debugging dataset runs where only the
    branch+twig silhouette matters and the mesh itself is not needed. Twig
    placements come straight from Grove's raw twig arrays -- no density
    adjustment, cutoff recovery, instance cap, or bone remap, since those
    exist only to match what an assembly would instance and there is no
    assembly here to match. bones_info is not passed, so the skeleton overlay
    is skipped too: front/side/top icons plus the branches/twigsonly/merged
    component files, nothing else.

    Sets ctx.export_success. ctx.usd_path stays None -- nothing is added to
    exported_files, matching that no mesh asset exists to hand to Unreal.
    """
    try:
        ctx.twig_placements = extract_twig_placements_from_model(ctx.model)
    except Exception:
        logger.exception("Twig extraction failed for %s", ctx.species_name)
        ctx.twig_placements = {}

    for _view in ("front", "side", "top"):
        _generate_icon_image(
            ctx.tree_dir,
            ctx.file_prefix,
            ctx.skeleton,
            ctx.timer,
            view=_view,
            twig_placements=ctx.twig_placements,
            bones_info=None,
            export_components=True,
        )
    ctx.export_success = True


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
    ("pve_json", lambda c: not c.skip_pve_json, write_pve_json, False),
    # Not once_per_tree: the preview now draws twig positions, which differ per
    # density variant (see write_previews).
    ("preview", lambda c: c.cfg.export_previews, write_previews, False),
    (
        "export_control",
        lambda c: c.cfg.export_control_images,
        write_export_control,
        True,
    ),
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
) -> int:
    """Generate trees at multiple growth stages using height-based milestones.

    Returns the number of milestone stages that the simulation captured but that
    failed to export. Zero means every captured stage reached disk. The caller
    turns a non-zero count into a non-zero exit code -- without that, an export
    failure is a single warning line in a log nobody reads while the process
    still exits 0, `Step 4 [X]: OK` is printed, and the stage is simply missing
    from the dataset. Counting *captured* milestones rather than a fixed matrix
    size is deliberate: a shaded radius legitimately plateaus below 25 m, so a
    static expectation would cry wolf on every run.


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

    Returns:
        Count of captured milestone stages that failed to export (0 = clean).
    """
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
        return 1

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
    icons_only = config.export_mode == "icons_only"
    quality_params["icons_only"] = icons_only
    # Density variants exist to compare assembly instance density -- moot
    # when there is no assembly, and each one is an extra grove.build_models()
    # call icons_only has no use for.
    quality_params["density_variants"] = (
        [] if icons_only else config.get_density_variants()
    )

    # Apply skeleton overrides (allows simplified skeleton with ultra mesh)
    if skeleton_overrides:
        for key, value in skeleton_overrides.items():
            quality_params[key] = value
        logger.info("[Skeleton Overrides] Applied: %s", skeleton_overrides)

    # Optional coarser preset for the tall stages. Mesh cost scales with tree
    # size far faster than visible detail does -- an open-grown silver fir is
    # 4.5M points at h10, 7.0M at h15 and ~23M projected at h25 -- so the top
    # of the ladder can cost more than the rest of the dataset combined while
    # adding branch detail no viewer resolves. Control flags (icons_only,
    # skip_pve_json, density_variants, ...) are carried over unchanged; only
    # the mesh/skeleton keys come from the alternate preset.
    tall_quality_params = None
    tall_quality_threshold = float(config.forest_quality_above_height_threshold or 0.0)
    if config.forest_quality_above_height and tall_quality_threshold > 0:
        tall_quality_params = {
            **quality_params,
            **get_quality_preset(config.forest_quality_above_height),
        }
        # Re-apply the two the caller forces after preset lookup above.
        tall_quality_params["skeleton_bias"] = 0.5
        tall_quality_params["skeleton_connected"] = True
        if skeleton_overrides:
            for key, value in skeleton_overrides.items():
                tall_quality_params[key] = value
        logger.info(
            "Stages at or above %.0fm build with the '%s' preset (res %s -> %s, "
            "cutoff %s -> %s); below that, '%s'",
            tall_quality_threshold,
            config.forest_quality_above_height,
            quality_params.get("resolution"),
            tall_quality_params.get("resolution"),
            quality_params.get("build_cutoff_thickness"),
            tall_quality_params.get("build_cutoff_thickness"),
            quality,
        )

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

    # Stages are exported as the simulation captures them (see _export_cycle),
    # not in a phase of their own -- so there is no total to announce here.
    logger.info("\n%s", "=" * 60)
    logger.info("PHASE 2/3: SIMULATING AND EXPORTING STAGES")
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
    # Counts stages that actually reached disk, so the run can be compared
    # against the milestones the simulation captured and fail if any is missing.
    # Must be bound before _export_cycle below, which declares it nonlocal.
    exported_stage_count = 0

    def _export_cycle(cycle, species_snapshots, milestone_map):
        """Export one captured milestone cycle, then let it be freed.

        Invoked by the simulation as each cycle's models are built (see
        simulate_forest_growth_with_snapshots' on_capture) rather than from
        a phase running after every stage is already in memory: holding
        h05..h25 of an open-grown 25 m conifer at once measured 37 GB and
        died with MemoryError on a 63.5 GB host.
        """
        nonlocal exported_stage_count
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
                precut_model,
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
                if config.export_mode == "icons_only":
                    # No USD twig prototypes to match, no mesh to build --
                    # icons read Grove's arrays directly.
                    twig_usd_map = {}
                else:
                    twig_usd_map = get_twig_usd_map_for_species(
                        species_name, config, prefer_skeletal=True, prefer_static=False
                    )
                if config.export_mode != "icons_only":
                    # Triangulation only matters for the mesh USD export;
                    # icons read Grove's twig/skeleton arrays, not faces.
                    try:
                        model.triangulate()
                    except Exception:
                        logger.warning(
                            "Model triangulation failed for %s", species_name
                        )

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
                if config.export_mode == "icons_only":
                    # No allometry/calibration lookups, no DBH target, no
                    # radial rescale -- the filename and the model both use
                    # exactly what Grove grew.
                    ctx.target_dbh_m = None
                    ctx.dbh_from_csv = False
                    ctx.filename_dbh = grove_dbh
                    ctx.radial_scale = 1.0
                else:
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
                    ctx.precut_model = precut_model

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

                    if config.export_mode == "helios":
                        # Direct OBJ export bypasses USD/Nanite entirely --
                        # none of the STAGES (wind/PVE/previews/icons/static)
                        # apply to an unskinned LiDAR mesh.
                        with timer.track("stage_export_obj_direct"):
                            export_obj_direct(ctx)

                        if ctx.export_success:
                            exported_files.append(str(ctx.usd_path))
                            logger.info("  Exported (OBJ): %s", ctx.usd_path.name)
                        else:
                            logger.warning(
                                "  OBJ export failed for tree %d (%s) at cycle %d (h=%.1fm)",
                                fid,
                                species_name,
                                cycle,
                                height,
                            )
                        continue

                    if config.export_mode == "icons_only":
                        # Icon PNGs straight from the Grove model -- no USD/
                        # Nanite/wind/PVE/previews/export-control, none of
                        # which this mode needs.
                        with timer.track("stage_icons_only"):
                            export_icons_only(ctx)
                        if ctx.export_success:
                            exported_stage_count += 1
                            logger.info("  Icons: %s", ctx.file_prefix)
                        else:
                            logger.warning(
                                "  Icon export failed for tree %d (%s) at "
                                "cycle %d (h=%.1fm)",
                                fid,
                                species_name,
                                cycle,
                                height,
                            )
                        continue

                    # Export as Nanite Assembly
                    with timer.track("stage_assembly"):
                        export_assembly(ctx)

                    if ctx.export_success:
                        if variant_idx == 0:
                            exported_stage_count += 1
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


    # A species that never reaches its ceiling silently produces fewer stages,
    # which is how the Douglas fir shortfall went unnoticed. Report it.
    # Per-radius so a shortfall specific to one surround-radius variant (the
    # heavily-shaded r08/r16, typically) is not masked by a less-competed
    # sibling (r00) reaching the same species' ceiling.
    species_tree_radii: dict[str, list[float]] = {}
    if "surround_radius" in forest_data.columns:
        for sp_name, group in forest_data.groupby("species", sort=False):
            species_tree_radii[sp_name] = [
                float(r) if pd.notna(r) else 0.0 for r in group["surround_radius"]
            ]

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
            on_capture=_export_cycle,
            tall_quality_params=tall_quality_params,
            tall_quality_threshold=tall_quality_threshold,
        )

    _warn_uncaptured_milestones(
        milestone_map,
        species_max_height,
        effective_interval,
        global_max_cycles,
        run_max_height=effective_max_height,
        tree_radius_labels=species_tree_radii,
    )

    # Every milestone the simulation captured is a stage that MUST reach disk.
    # Anything short of that is a silent hole in the dataset, so count it and
    # let the caller fail the run.
    captured_stage_count = sum(
        len(trees)
        for per_species in milestone_map.values()
        for trees in per_species.values()
    )
    logger.info("\nExported %d tree stage files", len(exported_files))

    shortfall = captured_stage_count - exported_stage_count
    if shortfall > 0:
        logger.error(
            "%d of %d captured milestone stage(s) failed to export. The dataset "
            "is INCOMPLETE -- see the 'Export failed' / 'model is None' warnings "
            "above for which trees and cycles.",
            shortfall,
            captured_stage_count,
        )
    else:
        logger.info(
            "All %d captured milestone stage(s) exported", captured_stage_count
        )
    return max(0, shortfall)
