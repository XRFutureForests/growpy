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
HEIGHT_SCALE = 1
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
from growpy.io.preview import generate_preview_image as _generate_preview_image
from growpy.io.preview import (
    generate_export_control_image as _generate_export_control_image,
)
from growpy.io.preview import generate_icon_image as _generate_icon_image
from growpy.io.unreal_scripts import (
    generate_unreal_cleanup_script,
    generate_unreal_import_script,
)
from growpy.utils.profiling import ProfileTimer, get_timer, init_profiler

logger = logging.getLogger(__name__)


def _handle_bone_limit_error(error: ValueError) -> None:
    """Print actionable guidance for bone limit errors and exit."""
    logger.error("\nERROR: %s", error)
    logger.error(
        "\nTo reduce bone count, try one or more of:\n"
        "  CLI arguments:\n"
        "    --skeleton-reduce 0.6    (skip thin branches, most effective, range 0.0-1.0)\n"
        "    --skeleton-length 3.0    (merge nodes into longer bones, range 0.0-5.0)\n"
        "    --quality performance    (use a lower quality preset)\n"
        "  Config (growpy.toml [forest.skeleton]):\n"
        "    reduce = 0.6\n"
        "    length = 3.0"
    )
    raise SystemExit(1) from error


def _is_bone_limit_error(error: ValueError) -> bool:
    """Check if a ValueError is about exceeding Unreal's bone limit."""
    msg = str(error)
    return "bones" in msg and "limit" in msg


def _compute_max_cycles_for_species(forest_data, config, cycle_limit=None):
    """Compute maximum simulation cycles needed per species.

    Uses growth models to predict how many cycles are needed to reach the
    maximum height in the forest data. Returns a conservative estimate
    to ensure all trees (including slow-growing open-grown ones) have
    enough cycles to reach their target milestones.

    Args:
        forest_data: DataFrame with species and height columns
        config: GrowPyConfig instance
        cycle_limit: Optional max cycle cap

    Returns:
        max_cycles: Maximum cycle count needed across all species
    """
    import math

    import joblib

    max_cycles = 1
    for species in forest_data["species"].unique():
        growth_model_path = config.get_growth_model_path(species)
        model_path = growth_model_path / "growth_model.pkl"
        model = joblib.load(model_path)
        max_height = forest_data[forest_data["species"] == species]["height"].max()
        predicted = max(1, math.ceil(float(model.predict([[max_height]])[0])))
        if cycle_limit:
            predicted = min(predicted, cycle_limit)
        logger.info("  %s: max_height=%.1fm -> ~%d cycles", species, max_height, predicted)
        max_cycles = max(max_cycles, predicted)

    return max_cycles


def _derive_static_from_skeletal(
    tree_dir: Path,
    species_clean: str,
    species_name: str,
    tree_id,
    model,
    twig_usd_map: dict,
    skip_validation: bool = False,
    stems_suffix: str = "",
    twig_placements=None,
    instances_dir: Path | None = None,
) -> str | None:
    """Derive a static mesh assembly from an existing skeletal one.

    Strips skeleton prims from a copy of the skeletal stems file,
    then creates a static assembly referencing the stripped stems.
    Returns the static assembly path string, or None on failure.
    """
    from growpy.io.assembly_export import create_assembly
    from growpy.io.tree_export import strip_skeleton_from_usd

    suffix = f"_{stems_suffix}" if stems_suffix else ""
    skeletal_stems = tree_dir / f"{species_clean}{suffix}_stems_skeletal.usda"
    static_stems = tree_dir / f"{species_clean}{suffix}_stems_static.usda"

    if not skeletal_stems.exists():
        logger.warning("Cannot derive static: skeletal stems not found: %s", skeletal_stems)
        return None

    if not strip_skeleton_from_usd(skeletal_stems, static_stems):
        return None

    if twig_placements is None:
        from growpy.core.twig import extract_twig_placements_from_model

        try:
            twig_placements = extract_twig_placements_from_model(model)
        except Exception as e:
            logger.warning("Failed to extract twig placements for static derivation: %s", e)

    static_assembly = tree_dir / f"{species_clean}{suffix}_assembly_static.usda"
    create_assembly(
        tree_usd_path=static_stems,
        output_path=static_assembly,
        species_name=species_name,
        tree_id=tree_id,
        twig_usd_paths=twig_usd_map,
        use_skeletal_mesh=False,
        twig_placements=twig_placements,
        validate=not skip_validation,
        instances_dir=instances_dir,
    )
    return str(static_assembly)


def _export_single_tree_from_forest(args: tuple) -> list:
    """Export all trees from an already-simulated grove (forest simulation phase).

    This exports trees directly from a grove that was already simulated with inter-species
    light competition. No re-simulation is performed - this is significantly faster than
    the old approach of recreating and re-simulating each tree individually.

    Args:
        args: Tuple of (fids, grove_instance, species_name, output_dir, quality_params, mesh_type, verbose, timer, twig_densities, csv_dbh_map, individual_type_map)
              fids is a list of original CSV fid values for each tree in the grove
              verbose is boolean for verbose output
              timer is optional ProfileTimer instance
              twig_densities is a dict mapping fid -> twig_density float (or empty dict)
              csv_dbh_map is a dict mapping fid -> dbh in meters (or empty dict)
              individual_type_map is a dict mapping fid -> individual_type str (or empty dict)

    Returns:
        List of exported file paths
    """
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()

    import gc as _gc_module

    from growpy import get_config
    from growpy.config.preset_overrides import (
        load_height_dbh_model_from_preset,
        load_target_dbh_from_preset,
        predict_dbh_from_height_model,
    )
    from growpy.core.tree import calculate_dbh_at_height, calculate_tree_height
    from growpy.io.assembly_export import export_tree_as_nanite_assembly
    from growpy.io.tree_export import get_twig_usd_map_for_species
    from growpy.utils.profiling import ProfileTimer

    (fids, grove, species, output_dir, quality_params, mesh_type, verbose, timer, twig_densities, csv_dbh_map, individual_type_map) = args

    # Use provided timer or create disabled one
    if timer is None:
        timer = ProfileTimer(enabled=False)

    # Shared twig/foliage instances directory (Megaplant-style)
    instances_dir = output_dir / "Instances"
    instances_dir.mkdir(parents=True, exist_ok=True)

    # Get config in worker process
    config = get_config()

    species_clean = (
        "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
        .strip()
        .replace(" ", "_")
        .replace("-", "_")
        .lower()
    )

    exported: list[str] = []

    try:
        # Export directly from already-simulated grove (from forest simulation phase)
        # This grove was grown with inter-species light competition and is ready to export
        # No re-simulation needed - much faster!
        # Note: Smoothing is applied during simulate_forest_growth(), not here

        # CRITICAL BUILD ORDER: skeleton -> bones -> models
        # 1. Build skeletons first
        with timer.track("build_skeletons"):
            skeletons = grove.build_skeletons(
                quality_params.get("skeleton_connected", True)
            )

        # 2. Tag bone IDs with reduction parameters from quality preset
        # Higher skeleton_length and skeleton_reduce = fewer bones
        # CRITICAL: Unreal Engine has 32,767 bone limit (16-bit signed int)
        # Note: tag_bone_id() takes positional args: (length, reduce, bias, connected)
        with timer.track("tag_bone_id"):
            skeleton_length = quality_params.get("skeleton_length", 2.0)
            skeleton_reduce = quality_params.get("skeleton_reduce", 0.4)
            bones = grove.tag_bone_id(
                skeleton_length,
                skeleton_reduce**2,  # Squared like Grove UI does
                quality_params.get("skeleton_bias", 0.5),
                quality_params.get("skeleton_connected", True),
            )

        # 3. NOW build models (with bone_id attributes already tagged)
        # Cutoff is allowed for skeletal meshes - bone filtering happens during export
        # to ensure skeleton only includes bones referenced by the mesh geometry
        with timer.track("build_models"):
            models = grove.build_models(
                {
                    "resolution": quality_params["resolution"],
                    "resolution_reduce": quality_params["resolution_reduce"],
                    "build_cutoff_age": quality_params["build_cutoff_age"],
                    "build_cutoff_thickness": quality_params["build_cutoff_thickness"],
                    "build_blend": quality_params["build_blend"],
                    "build_end_cap": quality_params["build_end_cap"],
                }
            )

        if not models:
            return exported

        # Slice bones list for each tree in grove
        with timer.track("slice_bones"):
            bones_grouped = [list(g) for k, g in groupby(bones, lambda x: x[0])]
            tree_bones = [
                bones_grouped[i]
                + (bones_grouped[i + 1] if i + 1 < len(bones_grouped) else [])
                for i in range(0, len(bones_grouped), 2)
            ]

        # Build additional model sets for density variants with different cutoffs
        density_variants = config.get_density_variants()
        variant_model_sets: Dict[str, list] = {}
        if density_variants:
            base_cutoff = (
                quality_params["build_cutoff_age"],
                quality_params["build_cutoff_thickness"],
            )
            built_cutoffs: Dict[tuple, list] = {base_cutoff: models}
            for vname, vcfg in density_variants:
                cutoff_key = (
                    vcfg.get("build_cutoff_age", base_cutoff[0]),
                    vcfg.get("build_cutoff_thickness", base_cutoff[1]),
                )
                if cutoff_key not in built_cutoffs:
                    variant_opts = {
                        "resolution": quality_params["resolution"],
                        "resolution_reduce": quality_params["resolution_reduce"],
                        "build_cutoff_age": cutoff_key[0],
                        "build_cutoff_thickness": cutoff_key[1],
                        "build_blend": quality_params["build_blend"],
                        "build_end_cap": quality_params["build_end_cap"],
                    }
                    with timer.track(f"build_models_{vname}"):
                        built_cutoffs[cutoff_key] = grove.build_models(variant_opts)
                variant_model_sets[vname] = built_cutoffs[cutoff_key]

        # Load height-DBH model for post-hoc radial scaling (preferred: height-driven)
        # Falls back to age-indexed target_dbh_curve if model not available
        h_dbh_model = load_height_dbh_model_from_preset(config.get_preset_path(species))
        target_dbh_curve = (
            load_target_dbh_from_preset(config.get_preset_path(species))
            if not h_dbh_model
            else []
        )

        # Export each model/skeleton/bones triplet (each is a separate tree)
        # Process one tree at a time and immediately release memory to reduce peak RAM
        num_trees = len(models)
        export_tree_ids = quality_params.get("export_tree_ids", None)
        for model_idx in range(num_trees):
            # Get current tree's data
            model = models[model_idx]
            skeleton = skeletons[model_idx]
            bones_for_tree = tree_bones[model_idx]

            # Use original CSV fid for naming (with leading zeros)
            tree_fid = fids[model_idx]
            tree_id = f"{tree_fid:04d}"

            # Skip trees not in export filter (they still participated in growth simulation)
            if export_tree_ids is not None and tree_fid not in export_tree_ids:
                # Clear memory for skipped tree
                models[model_idx] = None  # type: ignore[call-overload]
                skeletons[model_idx] = None  # type: ignore[call-overload]
                tree_bones[model_idx] = None  # type: ignore[call-overload]
                del model, skeleton, bones_for_tree
                continue

            # Compute height and DBH
            tree_height_m = 0.0
            grove_dbh_m = 0.0
            if grove.trees and model_idx < len(grove.trees):
                tree_height_m = calculate_tree_height(grove.trees[model_idx])
                grove_dbh_m = calculate_dbh_at_height(grove.trees[model_idx])

            # Use yield table target DBH for filename when available
            # Prefer height-DBH model (allometric, height-driven) over age-indexed curve
            filename_dbh = grove_dbh_m
            target_dbh_m = None
            if h_dbh_model and tree_height_m > 0:
                target_dbh_m = predict_dbh_from_height_model(tree_height_m, h_dbh_model)
                filename_dbh = target_dbh_m
            elif target_dbh_curve:
                cycle_idx = min(grove.age - 1, len(target_dbh_curve) - 1)
                if cycle_idx >= 0:
                    target_dbh_m = target_dbh_curve[cycle_idx]
                    filename_dbh = target_dbh_m

            # CSV DBH override: when the input CSV specifies a non-zero DBH,
            # use that as the target instead of the yield table value
            csv_dbh_for_tree = csv_dbh_map.get(tree_fid)
            dbh_from_csv = False
            if csv_dbh_for_tree and csv_dbh_for_tree > 0:
                target_dbh_m = csv_dbh_for_tree
                filename_dbh = csv_dbh_for_tree
                dbh_from_csv = True

            h_str = format_height_for_filename(tree_height_m)
            d_str = format_dbh_for_filename(filename_dbh)
            dims_suffix = f"{h_str}_{d_str}"

            # Shared per-tree work (independent of density variant)
            use_skeletal = mesh_type == "skeletal"
            use_static = mesh_type == "static"
            mesh_suffix = "skeletal" if use_skeletal else "static"
            individual_type = individual_type_map.get(tree_fid)

            with timer.track("get_twig_usd_map"):
                twig_usd_map = get_twig_usd_map_for_species(
                    species, config, prefer_skeletal=True, prefer_static=False
                )

            tree_radial_scale = 1.0
            if config.calibration_align_dbh and target_dbh_m and grove_dbh_m > 0.001:
                tree_radial_scale = target_dbh_m / grove_dbh_m
                if dbh_from_csv:
                    tree_radial_scale = max(0.1, min(tree_radial_scale, 5.0))
                else:
                    tree_radial_scale = max(0.5, min(tree_radial_scale, 2.0))

            # Build export iterations: one per density variant, or single default
            if density_variants:
                export_iterations = [
                    (vname, vcfg["twig_density"],
                     variant_model_sets.get(vname, models)[model_idx])
                    for vname, vcfg in density_variants
                ]
            else:
                export_iterations = [
                    (None, twig_densities.get(tree_fid), model)
                ]

            for variant_idx, (variant_name, effective_twig_density, effective_model) in enumerate(
                export_iterations
            ):
                # Build output directory and filename prefix
                if individual_type:
                    tree_dir = output_dir / species_clean / individual_type
                    density_str = (
                        variant_name
                        if variant_name
                        else format_density_for_filename(effective_twig_density)
                    )
                    individual_short = (
                        "comp" if "comp" in individual_type else "open"
                    )
                    species_title = (
                        species_clean.replace("_", " ").title().replace(" ", "_")
                    )
                    file_prefix = f"{species_title}_{individual_short}_{dims_suffix}_{density_str}"
                else:
                    tree_dir = output_dir / species_clean / f"tree_{tree_id}"
                    if variant_name:
                        file_prefix = f"{species_clean}_{dims_suffix}_{variant_name}"
                    else:
                        file_prefix = f"{species_clean}_{dims_suffix}"
                tree_dir.mkdir(parents=True, exist_ok=True)
                usd_path = tree_dir / f"{file_prefix}_assembly_{mesh_suffix}.usda"

                with timer.track(f"export_nanite_assembly_{mesh_suffix}"):
                    captured_twig_placements = {}
                    export_success = export_tree_as_nanite_assembly(
                        model=effective_model,
                        skeleton=skeleton if use_skeletal else None,
                        bones_info=bones_for_tree if use_skeletal else None,
                        output_path=usd_path,
                        species_name=species,
                        tree_id=tree_id,
                        twig_usd_paths=twig_usd_map,
                        include_twigs=True,
                        use_skeletal_mesh=use_skeletal,
                        use_static_mesh=use_static,
                        include_grove_attributes=quality_params.get(
                            "include_grove_attributes", False
                        ),
                        validate=not quality_params.get("skip_validation", False),
                        timer=timer,
                        stems_file_suffix=dims_suffix,
                        radial_scale=tree_radial_scale,
                        twig_density=effective_twig_density,
                        twig_placements_out=captured_twig_placements,
                        instances_dir=instances_dir,
                    )

                if export_success:
                    exported.append(str(usd_path))

                    # One-time artifacts: only for first variant
                    if variant_idx == 0:
                        stems_base = f"{species_clean}_{dims_suffix}"
                        # DynamicWind JSON for Unreal import
                        if use_skeletal:
                            from growpy.io.wind_json import generate_wind_json

                            skeletal_usd_path = (
                                tree_dir / f"{stems_base}_stems_skeletal.usda"
                            )
                            wind_json_path = (
                                tree_dir / f"{file_prefix}_stems_unreal_wind.json"
                            )
                            try:
                                with timer.track("generate_wind_json"):
                                    generate_wind_json(
                                        tree_usd_path=skeletal_usd_path,
                                        skeleton=skeleton,
                                        bones_info=bones_for_tree,
                                        output_path=wind_json_path,
                                    )
                            except Exception as wind_error:
                                logger.warning(
                                    "Failed to generate wind JSON for tree %s: %s",
                                    tree_id,
                                    wind_error,
                                )
                                logger.debug("Wind JSON traceback:", exc_info=True)

                        # PVE preset JSON (optional)
                        skip_pve = quality_params.get("skip_pve_json", False)
                        profile_pve = quality_params.get("profile_pve", False)
                        if use_skeletal and not skip_pve:
                            from growpy.io.pve_grove_mapper import generate_pve_from_grove

                            pve_json_path = tree_dir / f"{file_prefix}_stems_unreal_pve.json"
                            pve_config_dir = Path("data/assets/pve_configs")

                            try:
                                with timer.track("generate_pve_json"):
                                    generate_pve_from_grove(
                                        grove=grove,
                                        output_path=pve_json_path,
                                        species_name=species,
                                        tree_index=model_idx,
                                        model=effective_model,
                                        skeleton=skeleton,
                                        bones_info=bones_for_tree,
                                        verbose=True,
                                        pve_config_dir=pve_config_dir,
                                        profile=profile_pve,
                                    )
                            except Exception as pve_error:
                                logger.warning(
                                    "Failed to generate PVE preset JSON for tree %s: %s",
                                    tree_id,
                                    pve_error,
                                )
                                logger.debug("PVE JSON traceback:", exc_info=True)

                        # Derive static mesh from skeletal
                        if use_skeletal and config.export_static:
                            with timer.track("derive_static_from_skeletal"):
                                static_path = _derive_static_from_skeletal(
                                    tree_dir=tree_dir,
                                    species_clean=species_clean,
                                    species_name=species,
                                    tree_id=tree_id,
                                    model=effective_model,
                                    twig_usd_map=twig_usd_map,
                                    skip_validation=quality_params.get(
                                        "skip_validation", False
                                    ),
                                    stems_suffix=dims_suffix,
                                    twig_placements=captured_twig_placements or None,
                                    instances_dir=instances_dir,
                                )
                                if static_path:
                                    exported.append(static_path)

                        # 2D preview image
                        stems_base = f"{species_clean}_{dims_suffix}"
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

            # MEMORY OPTIMIZATION: Clear this tree's data immediately after export
            models[model_idx] = None  # type: ignore[call-overload]
            skeletons[model_idx] = None  # type: ignore[call-overload]
            tree_bones[model_idx] = None  # type: ignore[call-overload]
            del model, skeleton, bones_for_tree
            _gc_module.collect()

        # Clear remaining references
        del models, skeletons, tree_bones

    except ValueError as e:
        if _is_bone_limit_error(e):
            _handle_bone_limit_error(e)
        raise

    except Exception as e:
        logger.error("Export failed for grove: %s", e, exc_info=True)

    return exported


def export_individual_trees(
    forest: list,
    forest_data: pd.DataFrame,
    output_dir: Path,
    config: GrowPyConfig,
    quality_params: dict,
    mesh_type: str = "skeletal",
    verbose: bool = False,
    timer: Optional["ProfileTimer"] = None,
) -> list:
    """Export trees directly from already-simulated forest groves (no re-simulation).

    Each tree is exported from the grove that was already simulated with inter-species
    light competition in the forest simulation phase. This is significantly faster than
    re-simulating individual trees.

    Export types are controlled by config flags (export_skeletal, export_static).
    When both are enabled, static is derived from skeletal by stripping skeleton prims.

    Args:
        forest: List of (grove, species_name, tree_count, fid_list) from create_forest() + simulate_forest_growth()
        forest_data: DataFrame with tree data including species, growth_cycles
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality_params: Quality parameters dict
        mesh_type: Ignored - export types determined by config flags
        verbose: Print detailed progress information
        timer: Optional ProfileTimer for tracking execution times

    Returns:
        List of exported file paths
    """
    from growpy import get_config
    from growpy.utils.profiling import ProfileTimer

    if timer is None:
        timer = ProfileTimer(enabled=False)

    cfg = get_config()
    exported_files = []

    # Build tree export tasks from forest groves
    # Each grove contains multiple trees for that species, export all at once
    # Trees are named using their original CSV fid values
    grove_tasks = []

    # Build per-tree twig_density map from input CSV (if column exists)
    twig_density_map: Dict[int, float] = {}
    if "twig_density" in forest_data.columns:
        for _, row in forest_data.iterrows():
            val = row["twig_density"]
            if pd.notna(val):
                twig_density_map[int(row["fid"])] = float(val)

    # Build per-tree CSV DBH map (fid -> dbh in meters) for custom diameter scaling.
    # When a tree has dbh > 0 in the CSV, that value overrides the yield table target.
    csv_dbh_map: Dict[int, float] = {}
    if "dbh" in forest_data.columns:
        for _, row in forest_data.iterrows():
            val = row["dbh"]
            if pd.notna(val) and float(val) > 0:
                csv_dbh_map[int(row["fid"])] = float(val) / 100.0  # cm -> m

    # Build per-tree individual_type map for dataset naming
    individual_type_map: Dict[int, str] = {}
    if "individual_type" in forest_data.columns:
        for _, row in forest_data.iterrows():
            val = row["individual_type"]
            if pd.notna(val) and str(val).strip():
                individual_type_map[int(row["fid"])] = str(val).strip()

    for grove, species_name, tree_count, fids in forest:
        if cfg.export_skeletal:
            # Skeletal task; static derivation happens inline when both enabled
            grove_tasks.append(
                (
                    fids,
                    grove,
                    species_name,
                    output_dir,
                    quality_params,
                    "skeletal",
                    verbose,
                    timer,
                    twig_density_map,
                    csv_dbh_map,
                    individual_type_map,
                )
            )
        elif cfg.export_static:
            # Static-only: generate directly (no skeletal to derive from)
            grove_tasks.append(
                (
                    fids,
                    grove,
                    species_name,
                    output_dir,
                    quality_params,
                    "static",
                    verbose,
                    timer,
                    twig_density_map,
                    csv_dbh_map,
                    individual_type_map,
                )
            )

    # Always use sequential processing (bpy/USD not compatible with multiprocessing)
    for task_idx, task in enumerate(tqdm(grove_tasks, desc="Exporting groves")):
        _fids, _grove, _species, _outdir, _qp, _mesh_type, _verbose, _timer, _td, _dbh, _it = task
        species_short = _species.replace(" ", "_").lower()
        track_name = f"grove_export ({species_short} {_mesh_type})"
        with timer.track(track_name):
            result = _export_single_tree_from_forest(task)
            if result:
                exported_files.extend([Path(p) for p in result])

        # MEMORY OPTIMIZATION: Clear grove reference after export to free RAM
        # The grove object holds all simulation data which is no longer needed
        grove_tasks[task_idx] = None  # type: ignore[call-overload]

    # PVE JSON generation now happens inline during tree export
    # No separate batch generation needed

    return exported_files


from growpy.utils.export_naming import (  # noqa: E402
    format_dbh_for_filename,
    format_density_for_filename,
    format_height_for_filename,
)


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
    from growpy.io.assembly_export import export_tree_as_nanite_assembly
    from growpy.io.tree_export import get_twig_usd_map_for_species
    from growpy.utils.profiling import ProfileTimer

    if timer is None:
        timer = ProfileTimer(enabled=False)

    # Clear twig file copy cache at start of export session
    from growpy.io.assembly_export import clear_twig_copy_cache

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

    # Calculate growth cycles from height using growth models
    with timer.track("calculate_growth_cycles"):
        try:
            calculate_growth_cycles_from_height(forest_data)
        except Exception as e:
            logger.error("Could not calculate growth cycles from height: %s", e)
            logger.error(
                "  Ensure growth models exist (run create_growth_models.py first)"
            )
            return

        # Cap each tree's cycles individually at the limit
        if growth_cycle_limit is not None:
            forest_data["growth_cycles"] = forest_data["growth_cycles"].clip(
                upper=growth_cycle_limit, lower=1
            )

    # Compute max simulation cycles and height interval
    effective_interval = height_interval if height_interval is not None else 5.0
    limit = growth_cycle_limit if growth_cycle_limit is not None else None

    logger.info("\nComputing max cycles per species:")
    global_max_cycles = _compute_max_cycles_for_species(
        forest_data, config, cycle_limit=limit,
    )

    if global_max_cycles < 1:
        logger.error("No valid cycles could be computed")
        return

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
    logger.info("  Max simulation cycles: %d", global_max_cycles)
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
    for cycle, species_snapshots in tqdm(snapshots.items(), desc="Exporting stages"):
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
                    tree_max_cycles = int(tree_row["growth_cycles"])
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
                    tree_max_cycles = global_max_cycles
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

                # Skip this snapshot if cycle exceeds tree's calculated max
                if cycle > tree_max_cycles:
                    continue

                # In height-threshold mode, only export trees that triggered
                # a milestone crossing at this cycle. The milestone_map tells
                # us which tree_idx crossed which milestone height.
                cycle_milestones = milestone_map.get(cycle, {}).get(species_name, {})
                if milestone_map:
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
                # Use milestone height for clean filenames (e.g., h05m, h10m)
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

                dbh_str = format_dbh_for_filename(filename_dbh)
                dims_suffix = f"{height_str}_{dbh_str}"

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

                    usd_path = tree_dir / f"{file_prefix}_assembly.usda"

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
    from growpy.io.assembly_export import clear_twig_copy_cache

    clear_twig_copy_cache()

    # Use defaults if not specified
    if growth_cycle_limit is None:
        growth_cycle_limit = GROWTH_CYCLE_LIMIT
    if smooth_iterations is None:
        smooth_iterations = SMOOTH_ITERATIONS
    height_scale = HEIGHT_SCALE  # Hardcoded height scale

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

        # Cap growth cycles to growth_cycle_limit if they exceed it
        max_growth_cycles = forest_data["growth_cycles"].max()
        if max_growth_cycles > growth_cycle_limit:
            scale_factor = growth_cycle_limit / max_growth_cycles
            forest_data["growth_cycles"] = (
                forest_data["growth_cycles"] * scale_factor
            ).astype(int)
            forest_data["growth_cycles"] = forest_data["growth_cycles"].clip(lower=1)

            # CRITICAL: Recalculate delays after scaling cycles
            # Without this, delays can exceed the total simulation cycles,
            # preventing trees from growing entirely
            max_cycles_after_scaling = forest_data["growth_cycles"].max()
            forest_data["delay"] = (
                max_cycles_after_scaling - forest_data["growth_cycles"]
            )
        else:
            # Use calculated cycles (based on height) if they're within the limit
            # Apply height scale only if not scaling growth cycles
            forest_data["height"] /= height_scale

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
            from growpy.io.obj_export import export_forest_obj

            with timer.track("obj_export"):
                export_forest_obj(
                    output_dir=output_dir,
                    csv_path=csv_path,
                    generate_scene_xml=config.helios_helios_scene,
                    individual_obj=config.helios_individual_obj,
                    up_axis=config.helios_obj_up_axis,
                    timer=timer,
                )

        # Print profiling report if enabled
        if config.profile:
            timer.print_report()

        # Generate Unreal scripts if requested
        if config.unreal_import_to_unreal:
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
        tree_count = len(list(output_dir.glob("*/tree_*/*_assembly*.usda"))) if output_dir.exists() else 0
        species_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name != "unreal_scripts"] if output_dir.exists() else []
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
