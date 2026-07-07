"""Cross-format export orchestration for already-simulated forest groves.

This module sits at the `io/` top level (sibling to `usd/`, `unreal/`, and
`helios/`) because the per-tree export pipeline crosses sub-package boundaries:
it produces USD meshes/assemblies, Unreal wind JSON, Unreal PVE configs, and
preview images from a single grove instance.

Public entry point:
    export_individual_trees(forest, forest_data, output_dir, config, ...)
        Iterate over groves and export each one as a sequence of trees.

Internal worker:
    _export_single_tree_from_forest(args)
        Export all trees from one already-simulated grove.

Both functions were extracted verbatim from `cli/generate_forest.py` (Phase 2
of the io/cli restructure). See `docs/architecture/generate-forest-refactoring-plan.md`.
"""

from __future__ import annotations

import logging
from itertools import groupby
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from tqdm import tqdm

if TYPE_CHECKING:
    from ..config import GrowPyConfig
    from ..utils.profiling import ProfileTimer

logger = logging.getLogger(__name__)


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
              twig_densities is a dict mapping fid -> twig_density scale factor (or empty dict)
              csv_dbh_map is a dict mapping fid -> dbh in meters (or empty dict)
              individual_type_map is a dict mapping fid -> individual_type str (or empty dict)

    Returns:
        List of exported file paths
    """
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()

    import gc as _gc_module

    from .. import get_config
    from ..config.preset_overrides import (
        load_height_dbh_model_from_preset,
        load_target_dbh_from_preset,
        predict_dbh_from_height_model,
    )
    from ..core.tree import calculate_dbh_at_height, calculate_tree_height
    from ..utils.export_naming import (
        format_dbh_for_filename,
        format_density_for_filename,
        format_height_for_filename,
    )
    from ..utils.profiling import ProfileTimer
    from .unreal.unreal_scripts import (  # noqa: F401  (imported for parity with prior module)
        generate_unreal_cleanup_script,
        generate_unreal_import_script,
    )
    from .usd.assembly_export import export_tree_as_nanite_assembly
    from .usd.preview import (
        generate_export_control_image as _generate_export_control_image,
    )
    from .usd.preview import generate_icon_image as _generate_icon_image
    from .usd.preview import generate_preview_image as _generate_preview_image
    from .usd.tree_export import (
        derive_static_from_skeletal,
        get_twig_usd_map_for_species,
        handle_bone_limit_error,
        is_bone_limit_error,
    )

    (
        fids,
        grove,
        species,
        output_dir,
        quality_params,
        mesh_type,
        verbose,
        timer,
        twig_densities,
        csv_dbh_map,
        individual_type_map,
    ) = args

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
        variant_model_sets: dict[str, list] = {}
        if density_variants:
            base_cutoff = (
                quality_params["build_cutoff_age"],
                quality_params["build_cutoff_thickness"],
            )
            built_cutoffs: dict[tuple, list] = {base_cutoff: models}
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

            # Use the actual DBH after clamped radial scaling for the filename,
            # so the filename reflects what the exported mesh actually shows.
            if tree_radial_scale != 1.0 and grove_dbh_m > 0.001:
                filename_dbh = grove_dbh_m * tree_radial_scale

            h_str = format_height_for_filename(tree_height_m)
            d_str = format_dbh_for_filename(filename_dbh)
            dims_suffix = f"{h_str}_{d_str}"

            # Build export iterations: one per density variant, or single default
            if density_variants:
                export_iterations = [
                    (
                        vname,
                        vcfg["twig_density"],
                        variant_model_sets.get(vname, models)[model_idx],
                    )
                    for vname, vcfg in density_variants
                ]
            else:
                export_iterations = [(None, twig_densities.get(tree_fid), model)]

            for variant_idx, (
                variant_name,
                effective_twig_density,
                effective_model,
            ) in enumerate(export_iterations):
                # Build output directory and filename prefix
                if individual_type:
                    tree_dir = output_dir / species_clean / individual_type
                    density_str = (
                        variant_name
                        if variant_name
                        else format_density_for_filename(effective_twig_density)
                    )
                    individual_short = "surr" if "surr" in individual_type else "open"
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
                usd_path = (
                    tree_dir / f"{file_prefix}_assembly_{mesh_suffix}{config.usd_ext}"
                )

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
                            from .unreal.wind_json import generate_wind_json

                            skeletal_usd_path = (
                                tree_dir
                                / f"{stems_base}_stems_skeletal{config.usd_ext}"
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
                            from .unreal.pve_grove_mapper import generate_pve_from_grove

                            pve_json_path = (
                                tree_dir / f"{file_prefix}_stems_unreal_pve.json"
                            )
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
                                static_path = derive_static_from_skeletal(
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
                            tree_dir,
                            species_clean,
                            file_prefix,
                            timer,
                            view_bounds=preview_bounds,
                            stems_file_base=stems_base,
                        )
                        _generate_icon_image(tree_dir, file_prefix, skeleton, timer)

            # MEMORY OPTIMIZATION: Clear this tree's data immediately after export
            models[model_idx] = None  # type: ignore[call-overload]
            skeletons[model_idx] = None  # type: ignore[call-overload]
            tree_bones[model_idx] = None  # type: ignore[call-overload]
            del model, skeleton, bones_for_tree
            _gc_module.collect()

        # Clear remaining references
        del models, skeletons, tree_bones

    except ValueError as e:
        if is_bone_limit_error(e):
            handle_bone_limit_error(e)
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
    timer: ProfileTimer | None = None,
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
    from .. import get_config
    from ..utils.log import is_verbose
    from ..utils.profiling import ProfileTimer

    if timer is None:
        timer = ProfileTimer(enabled=False)

    cfg = get_config()
    exported_files = []

    # Build tree export tasks from forest groves
    # Each grove contains multiple trees for that species, export all at once
    # Trees are named using their original CSV fid values
    grove_tasks = []

    # Build per-tree twig_density scale map from input CSV (if column exists).
    # CSV twig_density is a multiplier applied to the TOML export_twig_density base.
    # e.g. TOML base=0.8, CSV scale=0.5 -> effective density = 0.4
    twig_density_map: dict[int, float] = {}
    if "twig_density" in forest_data.columns:
        for _, row in forest_data.iterrows():
            val = row["twig_density"]
            if pd.notna(val):
                twig_density_map[int(row["fid"])] = float(val)

    # Build per-tree CSV DBH map (fid -> dbh in meters) for custom diameter scaling.
    # When a tree has dbh > 0 in the CSV, that value overrides the yield table target.
    csv_dbh_map: dict[int, float] = {}
    if "dbh" in forest_data.columns:
        for _, row in forest_data.iterrows():
            val = row["dbh"]
            if pd.notna(val) and float(val) > 0:
                csv_dbh_map[int(row["fid"])] = float(val) / 100.0  # cm -> m

    # Build per-tree individual_type map for dataset naming
    individual_type_map: dict[int, str] = {}
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
    for task_idx, task in enumerate(
        tqdm(grove_tasks, desc="Exporting groves", disable=not is_verbose())
    ):
        (
            _fids,
            _grove,
            _species,
            _outdir,
            _qp,
            _mesh_type,
            _verbose,
            _timer,
            _td,
            _dbh,
            _it,
        ) = task
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

    return exported_files
