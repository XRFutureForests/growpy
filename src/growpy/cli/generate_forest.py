#!/usr/bin/env python3
"""Generate multi-species forests from CSV with USD export for Unreal Engine.

Step 4 of the pipeline. Defaults from growpy.toml [forest], [export], [unreal].
See docs/cli-reference.md.
"""

import bpy

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

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
    LONGEVITY_OVERRIDES,
    PresetOverrides,
    create_overrides_from_args,
)
from growpy.config.quality import get_quality_preset
from growpy.core.forest import simulate_forest_growth_with_snapshots
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


def _export_single_tree_from_forest(args: tuple) -> list:
    """Export all trees from an already-simulated grove (forest simulation phase).

    This exports trees directly from a grove that was already simulated with inter-species
    light competition. No re-simulation is performed - this is significantly faster than
    the old approach of recreating and re-simulating each tree individually.

    Args:
        args: Tuple of (fids, grove_instance, species_name, output_dir, quality_params, mesh_type, verbose, timer)
              fids is a list of original CSV fid values for each tree in the grove
              verbose is boolean for verbose output
              timer is optional ProfileTimer instance

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
    from growpy.utils.profiling import ProfileTimer

    (fids, grove, species, output_dir, quality_params, mesh_type, verbose, timer) = args

    # Use provided timer or create disabled one
    if timer is None:
        timer = ProfileTimer(enabled=False)

    # Get config in worker process
    config = get_config()

    species_clean = (
        "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
        .strip()
        .replace(" ", "_")
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

            # Use appropriate twig type based on mesh_type
            use_skeletal = mesh_type == "skeletal"
            use_static = mesh_type == "static"

            # Create tree-specific subfolder with tree ID
            mesh_suffix = "skeletal" if use_skeletal else "static"
            tree_dir = output_dir / species_clean / f"tree_{tree_id}"
            tree_dir.mkdir(parents=True, exist_ok=True)
            usd_path = tree_dir / f"{species_clean}_assembly_{mesh_suffix}.usda"

            # CRITICAL: Always use skeletal twigs for both skeletal and static assemblies
            # Static twig variants don't exist, and skeletal twigs work as point instances
            # in both assembly types (assembly type only affects tree mesh, not twig references)
            with timer.track("get_twig_usd_map"):
                twig_usd_map = get_twig_usd_map_for_species(
                    species, config, prefer_skeletal=True, prefer_static=False
                )

            # Export as Nanite Assembly with specified mesh type
            # tree_id in prim name ensures unique Unreal assets
            with timer.track(f"export_nanite_assembly_{mesh_suffix}"):
                export_success = export_tree_as_nanite_assembly(
                    model=model,
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
                )

            if export_success:
                exported.append(str(usd_path))

                # Generate DynamicWind JSON for Unreal import
                # CRITICAL: Unreal currently requires separate JSON import, not USD attributes
                # Use ImportDynamicWindSkeletalDataFromFile in Unreal after USD import
                if use_skeletal:
                    from growpy.io.wind_json import generate_wind_json

                    # Path to the skeletal USD file (stems mesh with skeleton)
                    skeletal_usd_path = (
                        tree_dir / f"{species_clean}_stems_skeletal.usda"
                    )
                    wind_json_path = (
                        tree_dir / f"{species_clean}_stems_unreal_wind.json"
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

                # Generate PVE preset JSON (optional, skip with --skip-pve-json)
                # Only generate once per tree (skeletal mesh export, not static)
                skip_pve = quality_params.get("skip_pve_json", False)
                profile_pve = quality_params.get("profile_pve", False)
                if use_skeletal and not skip_pve:
                    from growpy.io.pve_grove_mapper import generate_pve_from_grove

                    pve_json_path = tree_dir / f"{species_clean}_stems_unreal_pve.json"
                    pve_config_dir = Path("data/assets/pve_configs")

                    try:
                        with timer.track("generate_pve_json"):
                            generate_pve_from_grove(
                                grove=grove,
                                output_path=pve_json_path,
                                species_name=species,
                                tree_index=model_idx,
                                model=model,  # Pass current model (has twigs)
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

            # MEMORY OPTIMIZATION: Clear this tree's data immediately after export
            # This releases large mesh/skeleton data before processing next tree
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

    Both skeletal and static mesh assemblies are always generated.

    Args:
        forest: List of (grove, species_name, tree_count, fid_list) from create_forest() + simulate_forest_growth()
        forest_data: DataFrame with tree data including species, growth_cycles
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality_params: Quality parameters dict
        mesh_type: Ignored - both skeletal and static are always created
        verbose: Print detailed progress information
        timer: Optional ProfileTimer for tracking execution times

    Returns:
        List of exported file paths
    """
    from growpy.utils.profiling import ProfileTimer

    if timer is None:
        timer = ProfileTimer(enabled=False)

    exported_files = []

    # Build tree export tasks from forest groves
    # Each grove contains multiple trees for that species, export all at once
    # Trees are named using their original CSV fid values
    grove_tasks = []

    for grove, species_name, tree_count, fids in forest:
        # Always create skeletal mesh task
        # Pass fids list so each tree can be named with its original CSV fid
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
            )
        )
        # Always create static mesh task (needed for material bindings in OBJ/Helios)
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
            )
        )

    # Always use sequential processing (bpy/USD not compatible with multiprocessing)
    for task_idx, task in enumerate(tqdm(grove_tasks, desc="Exporting groves")):
        _fids, _grove, _species, _outdir, _qp, _mesh_type, _verbose, _timer = task
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


def format_height_for_filename(height_m: float) -> str:
    """Format height in meters for filename: h12m5 = 12.5m.

    Args:
        height_m: Height in meters

    Returns:
        Formatted string like 'h12m5' for 12.5 meters
    """
    meters = int(height_m)
    tenths = int((height_m - meters) * 10)
    return f"h{meters}m{tenths}"


def format_dbh_for_filename(dbh_m: float) -> str:
    """Format DBH in meters for filename: d32cm = 0.32m.

    Args:
        dbh_m: DBH in meters

    Returns:
        Formatted string like 'd32cm' for 32 centimeters
    """
    cm = int(dbh_m * 100)
    return f"d{cm}cm"


def generate_forest_stages(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    quality: str = "high",
    cycle_interval: Optional[int] = None,
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
    """Generate trees at multiple growth stages with height-based cycle calculation.

    This mode exports multiple tree models at different ages from a single tree position,
    with height and DBH encoded in the filename for easy asset selection.

    Height-to-Cycles Conversion:
        - Each tree's target height is converted to growth cycles using pre-trained models
        - Snapshots are exported at cycle intervals up to each tree's calculated max
        - Shorter trees get fewer snapshots than taller trees

    CSV Format (requires height column):
        fid,species,x,y,z,height
        1,Norway spruce,0,0,0,15.0

    Output naming:
        {species}_c{cycle:03d}_{height}_{dbh}_assembly.usda
        e.g., norway_spruce_c030_h12m5_d32cm_assembly.usda

    Args:
        csv_path: Path to CSV file with forest data (requires: species, x, y, height)
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality: Quality preset name
        cycle_interval: Export every N cycles (default: 10)
        growth_cycle_limit: Scale down cycles if they exceed this limit (like height mode)
        smooth_iterations: Number of smoothing iterations for branches
        include_grove_attributes: If True, include Grove metadata in USD files
        verbose: Print detailed progress information
        preset_overrides: Optional PresetOverrides for dynamic parameter adjustment
        timer: Optional ProfileTimer for tracking execution times
        skip_pve_json: If True, skip PVE preset JSON generation
        skip_validation: If True, skip assembly validation
    """
    from growpy.io.assembly_export import export_tree_as_nanite_assembly
    from growpy.io.tree_export import get_twig_usd_map_for_species
    from growpy.utils.profiling import ProfileTimer

    if timer is None:
        timer = ProfileTimer(enabled=False)

    # Clear twig file copy cache at start of export session
    from growpy.io.assembly_export import clear_twig_copy_cache

    clear_twig_copy_cache()

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

        # Apply growth_cycle_limit scaling (same as height-based mode)
        # This scales all tree cycles proportionally to fit within the limit
        if growth_cycle_limit is not None:
            max_growth_cycles = forest_data["growth_cycles"].max()
            if max_growth_cycles > growth_cycle_limit:
                scale_factor = growth_cycle_limit / max_growth_cycles
                forest_data["growth_cycles"] = (
                    forest_data["growth_cycles"] * scale_factor
                ).astype(int)
                forest_data["growth_cycles"] = forest_data["growth_cycles"].clip(
                    lower=1
                )

    # Use CLI interval, calculate max from height-derived cycles (after scaling)
    effective_interval = cycle_interval if cycle_interval is not None else 10
    # Global max is the highest cycles needed (from tallest tree, after limit scaling)
    global_max_cycles = int(forest_data["growth_cycles"].max())

    snapshot_cycles = list(
        range(effective_interval, global_max_cycles + 1, effective_interval)
    )

    logger.info("\n%s", "=" * 60)
    logger.info("MULTI-STAGE FOREST GENERATION")
    logger.info("%s", "=" * 60)
    logger.info("  Trees: %d", len(forest_data))
    logger.info(
        "  Height range: %.1fm - %.1fm",
        forest_data["height"].min(),
        forest_data["height"].max(),
    )
    logger.info(
        "  Cycle range: %d - %d",
        forest_data["growth_cycles"].min(),
        global_max_cycles,
    )
    logger.info("  Interval: %d", effective_interval)
    logger.info("  Snapshots: %d stages %s", len(snapshot_cycles), snapshot_cycles)
    logger.info("%s", "=" * 60)

    # Create forest (groves by species)
    # For cycle mode, we don't use delay - all trees start at cycle 0
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
    quality_params["include_static"] = True
    quality_params["skip_validation"] = skip_validation
    quality_params["export_tree_ids"] = export_tree_ids

    # Apply skeleton overrides (allows simplified skeleton with ultra mesh)
    if skeleton_overrides:
        for key, value in skeleton_overrides.items():
            quality_params[key] = value
        logger.info("[Skeleton Overrides] Applied: %s", skeleton_overrides)

    # Run simulation with snapshots
    with timer.track("simulate_with_snapshots"):
        snapshots = simulate_forest_growth_with_snapshots(
            forest,
            max_cycles=global_max_cycles,
            snapshot_cycles=snapshot_cycles,
            smooth_iterations=smooth_iterations,
            preset_overrides=preset_overrides,
            quality_params=quality_params,
        )

    if not snapshots:
        logger.error("No snapshots captured during simulation")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Export each snapshot
    logger.info("\n%s", "=" * 60)
    logger.info("PHASE 3: EXPORTING STAGES (%d cycles)", len(snapshots))
    logger.info("%s", "=" * 60)

    exported_files = []
    for cycle, species_snapshots in tqdm(snapshots.items(), desc="Exporting stages"):
        for species_name, tree_data_list in species_snapshots.items():
            # Get fids and max cycles for this species from forest data
            species_rows = forest_data[forest_data["species"] == species_name]

            for tree_idx, (model, skeleton, bones_info, height, dbh) in enumerate(
                tree_data_list
            ):
                if model is None:
                    continue

                # Get tree's max cycles from height calculation
                if tree_idx < len(species_rows):
                    tree_row = species_rows.iloc[tree_idx]
                    fid = int(tree_row["fid"])
                    tree_max_cycles = int(tree_row["growth_cycles"])
                else:
                    fid = tree_idx + 1
                    tree_max_cycles = global_max_cycles

                # Skip this snapshot if cycle exceeds tree's calculated max
                if cycle > tree_max_cycles:
                    continue

                # Skip trees not in export filter (they still participated in growth simulation)
                if export_tree_ids is not None and fid not in export_tree_ids:
                    continue

                # Generate filename with metadata
                species_clean = (
                    "".join(
                        c for c in species_name if c.isalnum() or c in (" ", "-", "_")
                    )
                    .strip()
                    .replace(" ", "_")
                    .lower()
                )
                height_str = format_height_for_filename(height)
                dbh_str = format_dbh_for_filename(dbh)
                tree_id = f"{fid:04d}_c{cycle:03d}_{height_str}_{dbh_str}"

                # Create output directory: species/tree_####/
                tree_dir = output_dir / species_clean / f"tree_{fid:04d}"
                tree_dir.mkdir(parents=True, exist_ok=True)

                # Assembly name includes cycle/height/dbh for unique identification
                assembly_name = (
                    f"{species_clean}_c{cycle:03d}_{height_str}_{dbh_str}_assembly"
                )
                usd_path = tree_dir / f"{assembly_name}.usda"

                # Get twig USD paths
                twig_usd_map = get_twig_usd_map_for_species(
                    species_name, config, prefer_skeletal=True, prefer_static=False
                )

                # Triangulate model before export
                try:
                    model.triangulate()
                except Exception:
                    pass

                # Export as Nanite Assembly
                try:
                    export_success = export_tree_as_nanite_assembly(
                        model=model,
                        skeleton=skeleton,
                        bones_info=bones_info,
                        output_path=usd_path,
                        species_name=species_name,
                        tree_id=tree_id,
                        twig_usd_paths=twig_usd_map,
                        include_twigs=True,
                        use_skeletal_mesh=True,
                        use_static_mesh=False,
                        include_grove_attributes=include_grove_attributes,
                        validate=not skip_validation,
                        timer=timer,
                    )
                except ValueError as e:
                    if _is_bone_limit_error(e):
                        _handle_bone_limit_error(e)
                    raise

                if export_success:
                    exported_files.append(str(usd_path))
                    logger.info("  Exported: %s", usd_path.name)

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

    Both skeletal and static mesh assemblies are always generated.
    Static meshes retain material bindings needed for OBJ/Helios export.

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
    quality_params["include_static"] = True
    quality_params["skip_validation"] = skip_validation
    quality_params["profile_pve"] = (
        timer.enabled
    )  # Enable PVE profiling when --profile is set
    quality_params["export_tree_ids"] = export_tree_ids

    try:
        # Twigs are copied to each tree folder by assembly_export
        # No need for species-level bundling

        # mesh_type parameter ignored - both skeletal and static are always created
        with timer.track("export_trees"):
            export_individual_trees(
                forest,
                forest_data,
                output_dir,
                config,
                quality_params,
                mesh_type="skeletal",  # Ignored - both types are created
                verbose=verbose,
                timer=timer,
            )

    except ValueError as e:
        if _is_bone_limit_error(e):
            _handle_bone_limit_error(e)
        raise

    except Exception as e:
        logger.warning("Export failed: %s", e)


def generate_unreal_import_script(
    output_dir: Path,
    project_path: str = "/Game/GrowPy/Trees",
    forest_data: Optional[pd.DataFrame] = None,
    export_tree_ids: Optional[set] = None,
) -> Path:
    """
    Generate a standalone Unreal Python script for importing forest USD files.

    Trees are organized as species/tree_{id}/{species}.usda (assembly)
    Each assembly references {species}_{tree_id}_skeletal.usda (unique tree mesh).
    Assembly filename is same per species (like twigs), tree mesh has unique tree_id.

    This script can be executed directly in Unreal Engine using:
    - VSCode Unreal Python extension (right-click > Execute in Unreal)
    - Unreal Editor Python console
    - Command line

    Args:
        output_dir: Directory containing exported USD files
        project_path: Unreal project Content path
        forest_data: Optional DataFrame with tree positions (must have fid, x, y, z columns)
        export_tree_ids: Optional set of tree IDs to include (if None, includes all)

    Returns:
        Path to generated script file
    """
    # Create unreal_scripts directory in output
    script_dir = output_dir / "unreal_scripts"
    script_dir.mkdir(exist_ok=True)

    script_path = script_dir / "import_forest.py"

    # Find all tree assemblies in species/tree_{id}/ folders
    # Structure: species/tree_0001/{species}_assembly.usda (references {species}_stems_skeletal.usda)
    nanite_files = list(output_dir.glob("*/tree_*/*_assembly.usda")) + list(
        output_dir.glob("*/tree_*/*_assembly.usd")
    )

    # Group trees by species (parent of tree_XXXX folder)
    trees_by_species: Dict[str, list] = {}
    for usd_file in nanite_files:
        # Structure: species_dir/tree_XXXX/assembly.usda
        tree_folder = usd_file.parent
        species_parent = tree_folder.parent
        species_name = species_parent.name

        if species_name not in trees_by_species:
            trees_by_species[species_name] = []
        trees_by_species[species_name].append(usd_file)

    num_species = len(trees_by_species)
    total_trees = len(nanite_files)

    # Build TREE_POSITIONS dictionary from forest_data if provided
    tree_positions_dict = {}
    if forest_data is not None:
        for _, row in forest_data.iterrows():
            fid = int(row["fid"])
            # Skip trees not in export filter
            if export_tree_ids is not None and fid not in export_tree_ids:
                continue
            x = float(row["x"])
            y = float(row["y"])
            z = float(row.get("z", 0.0))  # Default to 0 if z not present
            species = row["species"]
            # Format: "species_####" matching tree folder names
            tree_key = f"{species}_{fid:04d}"
            tree_positions_dict[tree_key] = (x, y, z)

    # Format dictionary as Python code for the script
    tree_positions_code = "TREE_POSITIONS = {\n"
    for tree_key, (x, y, z) in sorted(tree_positions_dict.items()):
        tree_positions_code += f"    '{tree_key}': ({x}, {y}, {z}),\n"
    tree_positions_code += "}\n"

    # Generate script content with forward slashes to avoid Unicode escape errors
    script_path_str = str(script_path).replace("\\", "/")

    script_content = f'''"""
Unreal Engine script to import GrowPy forest - Auto-generated

All trees of each species are imported to the same folder.
Shared twigs are automatically deduplicated (overwritten on each import).

Execute this script in Unreal Engine:
1. Right-click this file in VSCode > "Execute Python File in Unreal"
2. Or from Unreal Python console: exec(open(r'{script_path_str}').read())
"""

import unreal
import gc
import time

print("=" * 60)
print("GrowPy Forest Import to Unreal Engine")
print("=" * 60)

# Import configuration
IMPORT_PATH = "{project_path}"

# Delay between imports to prevent crashes (seconds)
# Increase if you experience crashes
IMPORT_DELAY = 0.5

# Tree positions from CSV (in meters, multiply by 100 for Unreal units)
{tree_positions_code}

print(f"Destination: {{IMPORT_PATH}}")
print(f"Found {num_species} species with {total_trees} trees\\n")

# Get asset tools
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

imported_count = 0
failed_count = 0

'''

    # Generate import code for each species
    for species_folder, species_trees in sorted(trees_by_species.items()):
        # Use original folder name for Unreal path (matches USD file structure)
        species_display = species_folder

        script_content += f"""
# --- {species_folder} ({len(species_trees)} trees) ---
print("Importing {species_folder}...")
"""

        for usd_file in sorted(species_trees):
            usd_path = str(usd_file.resolve()).replace("\\", "/")

            # Extract tree ID from folder name (tree_0001, tree_0002, etc.)
            tree_folder_name = usd_file.parent.name
            tree_number = (
                tree_folder_name.replace("tree_", "")
                if tree_folder_name.startswith("tree_")
                else "0000"
            )

            script_content += f"""
try:
    import_task = unreal.AssetImportTask()
    import_task.filename = "{usd_path}"
    import_task.destination_path = IMPORT_PATH + "/{species_display}"
    import_task.automated = True
    import_task.save = True
    import_task.replace_existing = True
    
    options = unreal.UsdStageImportOptions()
    options.import_actors = False
    options.import_geometry = True
    options.import_materials = True
    # Flatten folder structure - assets by type (Materials, StaticMeshes, etc)
    options.set_editor_property('prim_path_folder_structure', False)
    # Share identical assets (twigs, materials) between trees
    options.set_editor_property('share_assets_for_identical_prims', True)
    # Combine identical material slots
    options.set_editor_property('merge_identical_material_slots', True)
    import_task.options = options
    
    asset_tools.import_asset_tasks([import_task])
    
    if import_task.imported_object_paths:
        imported_count += 1
        print(f"  Imported tree #{tree_number}")
    else:
        failed_count += 1
        unreal.log_warning("Failed to import tree_{tree_number}")
    
    # Cleanup and delay to prevent crashes
    gc.collect()
    unreal.SystemLibrary.collect_garbage()
    time.sleep(IMPORT_DELAY)
    
except Exception as e:
    failed_count += 1
    unreal.log_error(f"Error importing tree_{tree_number}: {{e}}")
"""

    script_content += """

print("")
print("=" * 60)
print(f"Import complete: {imported_count} trees imported, {failed_count} failed")
print("=" * 60)

if failed_count > 0:
    unreal.log_warning("Some imports failed. Check that USD Importer plugin is enabled.")
else:
    print(f"\\nAssets imported to Content Browser: {IMPORT_PATH}")
    print("Each species folder contains trees and shared twigs")
    print("")
    print("=" * 60)
    print("TREE PLACEMENT")
    print("=" * 60)
    print("Trees are exported at origin (0,0,0)")
    print("Use TREE_POSITIONS dictionary to place trees at their CSV coordinates")
    print("")
    print("Example placement code:")
    print("  # Get tree mesh from Content Browser")
    print("  tree_asset = unreal.EditorAssetLibrary.load_asset(IMPORT_PATH + '/species/SK_species_tree_0001')")
    print("  # Get position for this tree")
    print("  pos = TREE_POSITIONS.get('species_0001', (0,0,0))")
    print("  # Place in level")
    print("  actor = unreal.EditorLevelLibrary.spawn_actor_from_object(tree_asset, unreal.Vector(pos[0]*100, pos[1]*100, pos[2]*100))")
    print("")
    print(f"Available tree positions: {len(TREE_POSITIONS)}")
"""

    # Write script file
    script_path.write_text(script_content, encoding="utf-8")

    return script_path


def generate_unreal_cleanup_script(
    output_dir: Path,
    project_path: str = "/Game/GrowPy/Trees",
    dry_run: bool = True,
) -> Path:
    """
    Generate a standalone Unreal Python script for cleaning GrowPy assets.

    Args:
        output_dir: Directory to save cleanup script (same as import script)
        project_path: Unreal project Content path to clean
        dry_run: If True, generates preview-only script

    Returns:
        Path to generated script file
    """
    # Save in same unreal_scripts directory as import script
    script_dir = output_dir / "unreal_scripts"
    script_dir.mkdir(exist_ok=True)

    script_path = script_dir / "clean_assets.py"

    # Generate script content with forward slashes to avoid Unicode escape errors
    script_path_str = str(script_path).replace("\\", "/")

    script_content = f'''"""
Unreal Engine cleanup script for GrowPy assets - Auto-generated

Execute this script in Unreal Engine:
1. Right-click this file in VSCode > "Execute Python File in Unreal"
2. Or from Unreal Python console: exec(open(r'{script_path_str}').read())
"""

import unreal

print("=" * 60)
print("GrowPy Asset Cleanup")
print("=" * 60)

# Cleanup configuration
CLEANUP_PATH = "{project_path}"
DRY_RUN = {str(dry_run)}

print(f"Target path: {{CLEANUP_PATH}} (including all subfolders)")

if DRY_RUN:
    print("\\n*** DRY RUN MODE - No assets will be deleted ***\\n")
else:
    print("\\n*** LIVE MODE - Assets will be permanently deleted ***\\n")

# Get asset registry
asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()

# Find all assets in target path (recursive to include species subfolders)
assets = asset_registry.get_assets_by_path(CLEANUP_PATH, recursive=True)

if not assets:
    print(f"No assets found at {{CLEANUP_PATH}}")
else:
    print(f"Found {{len(assets)}} assets at {{CLEANUP_PATH}}\\n")
    
    if DRY_RUN:
        # Dry run - just list assets
        print("Assets that would be deleted:\\n")
        for asset in assets:
            asset_path = str(asset.package_name)
            asset_name = str(asset.asset_name)
            asset_class = str(asset.asset_class_path.asset_name)
            
            print(f"  {{asset_class}}: {{asset_name}}")
            print(f"    Path: {{asset_path}}")
        
        print("\\n" + "=" * 60)
        print("DRY RUN COMPLETE")
        print("=" * 60)
        print("Set DRY_RUN = False in script to perform actual deletion")
    
    else:
        # Real cleanup - delete assets
        print("Deleting assets...\\n")
        deleted_count = 0
        failed_count = 0
        
        for asset in assets:
            asset_path = str(asset.package_name)
            asset_name = str(asset.asset_name)
            
            try:
                if unreal.EditorAssetLibrary.delete_asset(asset_path):
                    deleted_count += 1
                    unreal.log(f"✓ Deleted {{asset_name}}")
                else:
                    failed_count += 1
                    unreal.log_warning(f"✗ Failed to delete: {{asset_name}}")
            except Exception as e:
                failed_count += 1
                unreal.log_error(f"✗ Error deleting {{asset_name}}: {{e}}")
        
        print("")
        print("=" * 60)
        print(f"Cleanup complete: {{deleted_count}} deleted, {{failed_count}} failed")
        print("=" * 60)
        
        if failed_count > 0:
            unreal.log_warning("Some assets could not be deleted. They may be in use.")
        else:
            print(f"\\nAll assets removed from: {{CLEANUP_PATH}}")
            
            # Try to delete empty folder after assets are removed
            try:
                if unreal.EditorAssetLibrary.does_directory_exist(CLEANUP_PATH):
                    # Check if directory is empty
                    remaining = asset_registry.get_assets_by_path(CLEANUP_PATH, recursive=True)
                    if not remaining:
                        if unreal.EditorAssetLibrary.delete_directory(CLEANUP_PATH):
                            print(f"[OK] Removed empty directory: {{CLEANUP_PATH}}")
                        else:
                            unreal.log_warning(f"Could not remove directory: {{CLEANUP_PATH}}")
            except Exception as e:
                unreal.log_warning(f"Error removing directory: {{e}}")
'''

    # Write script file
    script_path.write_text(script_content, encoding="utf-8")

    return script_path


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
        "--longevity-mode",
        action="store_true",
        help="Apply pre-configured overrides to prevent tree death at high cycle counts (reduces drop_decay, drop_weak, etc.)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output for PVE preset generation",
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

    # Multi-stage export: generate trees at multiple growth stages from a single position
    parser.add_argument(
        "--cycle-interval",
        type=int,
        default=None,
        help="Export trees at cycle intervals (e.g., 10 = export at cycles 10, 20, 30...). "
        "Enables multi-stage mode. Overrides CSV cycle_interval column if present.",
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

    # Configure logging based on verbose flag
    from growpy.utils.log import setup_logging

    setup_logging(verbose=config.verbose)

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
        if config.forest_longevity_mode:
            preset_overrides = LONGEVITY_OVERRIDES
            logger.info(
                "\n[Longevity Mode] Using pre-configured overrides to prevent tree death:"
            )
            logger.info("  Static: %s", preset_overrides.static_overrides)
        elif args.preset_override:
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

        # Detect cycle-based mode (config value already merged with CLI by resolve())
        is_cycle_mode = config.forest_cycle_interval > 0

        with timer.track("total_forest_generation"):
            if is_cycle_mode:
                # Multi-stage export mode: generate trees at different growth stages
                generate_forest_stages(
                    csv_path,
                    output_dir,
                    config,
                    config.forest_quality,
                    cycle_interval=config.forest_cycle_interval,
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

    except Exception as e:
        logger.error("Forest generation failed: %s", e)
        logger.debug("Traceback:", exc_info=True)


if __name__ == "__main__":
    main()
