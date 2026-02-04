#!/usr/bin/env python3
"""
Forest generation with USD export and optional Unreal Engine import script generation.

Generates multi-species forests from CSV data with configurable quality settings.
Can generate standalone Unreal Python scripts for importing trees via VSCode extension.
Creates skeletal (animation-ready) Nanite assemblies by default, with optional static assemblies.

Two Export Modes:
    1. Height-based (default): Trees grown to target heights specified in CSV
    2. Multi-stage: Multiple tree models at different growth cycles from single positions

Quick Start (copy-paste ready with all defaults shown):
    # Full forest generation with all flags (recommended for production)



Common Flags:
    [csv_file]                                     Input CSV with tree positions (default: data/input/test.csv)
                                                   Height mode: x, y, species, height; Optional: z
                                                   Multi-stage mode: x, y, species, cycle_interval, max_cycles

    --quality {ultra,high,medium,low,performance}  Quality preset affecting resolution and detail (default: ultra)
                                                   - ultra: 32 vertices, max detail, hero trees
                                                   - high: 24 vertices, high detail, featured trees
                                                   - medium: 16 vertices, balanced quality/performance
                                                   - low: 12 vertices, background trees
                                                   - performance: 8 vertices, distant trees, minimal detail

    --growth-cycle-limit INT                       Maximum growth cycles per tree (default: 10, range: 1-125)
                                                   Effect: Trees exceeding this are scaled down proportionally
                                                   Higher values = more detailed branch structure but slower export

    --smooth-iterations INT                        Branch smoothing iterations (default: 10, range: 0-20)
                                                   Effect: Reduces sharp angles in branch geometry
                                                   Higher values = smoother, more organic branches
                                                   Set to 0 to disable smoothing (raw simulation output)

    --output-dir PATH                              Output directory (default: data/output/forest)
                                                   Creates species subdirectories automatically

    --import-to-unreal                             Generate Unreal Python import script for VSCode extension
                                                   Creates unreal_import_trees.py and unreal_cleanup_trees.py

    --unreal-project-path PATH                     Unreal content path (default: /Game/GrowPy/Trees)
                                                   Base directory for imported assets in Unreal Content Browser

    --include-grove-attributes                     Include Grove metadata in USD files (default: disabled)
                                                   Adds age, mass, vigor, etc. attributes for analysis
                                                   Effect: Increases USD file size by ~70%

    --profile                                      Enable profiling to track execution time of each step
                                                   Prints detailed timing report showing bottlenecks
                                                   Useful for identifying slow processing steps

    -v, --verbose                                  Enable verbose output for PVE preset generation

Skeleton Simplification Flags (independent of mesh quality):
    Use these to reduce bone count while keeping ultra mesh resolution.
    Critical for Unreal Engine's 32,767 bone limit.
    Both parameters independently reduce bone count - use whichever fits your needs.

    --skeleton-length FLOAT                        Merge nodes along branches into longer bones (0.0-5.0)
                                                   Higher values create fewer, longer bones along branch length.
                                                   - 0.1 = one bone per node (ultra default, most bones)
                                                   - 2.0 = balanced (medium default)
                                                   - 4.0 = very long bones (performance default, fewest bones)

    --skeleton-reduce FLOAT                        Skip thin side branches entirely (0.0-1.0)
                                                   Higher values filter out more thin branches from having any bones.
                                                   This is typically the most effective for reducing bone count.
                                                   - 0.1 = keep all branches (ultra default, most bones)
                                                   - 0.4 = skip thin branches (medium default)
                                                   - 0.8 = only thick main branches (performance default, fewest bones)

    --skeleton-bias FLOAT                          Bone distribution bias (0.0-1.0, default: 0.5)
                                                   0.0 = more bones near trunk
                                                   1.0 = more bones near branch tips

    --skeleton-connected {true,false}              Use connected bone chains (default: true)
                                                   true = connected chains (required by some programs, more bones)
                                                   false = floating bones (fewer bones)

    Example: Ultra mesh with simplified skeleton
        python src/growpy/cli/generate_forest.py --quality ultra --skeleton-reduce 0.5

Multi-Stage Export Flags (generate trees at different growth stages):
    --cycle-interval INT                           Export trees every N cycles (e.g., 10 = cycles 10, 20, 30...)
                                                   Enables multi-stage mode. Required for multi-stage export.

    --max-cycles INT                               Optional cap on maximum cycles (default: use height-derived cycles)
                                                   Each tree's max cycles is calculated from its height.

    CSV Format (same as height mode - height column required):
        fid,species,x,y,z,height
        1,Norway spruce,0,0,0,15.0

    How it works:
        1. Height is converted to cycles using pre-trained growth models
        2. Each tree gets snapshots at [interval, 2*interval, ...] up to its calculated cycles
        3. Shorter trees get fewer snapshots than taller trees

    Example usage:
        python src/growpy/cli/generate_forest.py data/input/test.csv --cycle-interval 10

    Output naming includes metadata for easy selection:
        norway_spruce_c030_h12m5_d32cm.usda
        Format: {species}_c{cycle:03d}_h{meters}m{tenths}_d{dbh_cm}cm

Tree Selection Flags:
    --export-trees IDs                             Comma-separated list of tree fids to export
                                                   Example: --export-trees 1,2,5
                                                   Other trees still participate in growth simulation for
                                                   correct light competition, but only specified trees are exported.
                                                   Useful for exporting only trees of interest (e.g., central tree
                                                   growing under competition without exporting all competitors).
                                                   If not specified, all trees are exported.

Performance Flags (skip optional generation steps):
    --skip-pve-json                                Skip PVE preset JSON generation (saves ~3% export time)
                                                   PVE presets only needed for Unreal Procedural Vegetation Editor

    --skip-validation                              Skip assembly validation (saves ~5-10% export time)

    --include-static                               Also generate static mesh assemblies (disabled by default)
                                                   Static meshes have full PBR materials but no animation
                                                   Saves ~7% export time when disabled

    --fast                                         Fast mode: skip PVE JSON, validation, and static meshes
                                                   Equivalent to --skip-pve-json --skip-validation

    Note: DynamicWind data is exported as separate JSON files (*_DynamicWind.json)
          Import in Unreal using ImportDynamicWindSkeletalDataFromFile after USD import

Preset Override Flags (prevent tree death at high cycle counts):
    --longevity-mode                               Apply pre-configured overrides to prevent tree death
                                                   Sets drop_decay=0.1, drop_weak=0.1, etc.
                                                   Use this if trees "die" at high growth cycles

    --preset-override PARAM=VALUE                  Override a preset parameter with fixed value
                                                   Example: --preset-override drop_decay=0.1
                                                   Can be specified multiple times

    Common parameters to override:
        drop_decay      Rate of dead branch decay (0.0-1.0, lower = less decay)
        drop_weak       Rate of weak branch dropping (0.0-1.0, lower = keep more)
        drop_shaded     Rate of shaded branch dropping (0.0-1.0)
        drop_obsolete   Rate of obsolete branch dropping (0.0-1.0)

    Note: For cycle-based interpolation, use _curve definitions in seed.json files.
          See docs/grove-preset-reference.md for format details.

Assembly Types:
    skeletal (default): Skeletal mesh assemblies with animation support
              - Minimal export: geometry and skeleton only (no materials/textures)
              - Grove attributes disabled by default (use --include-grove-attributes to enable)
              - Supports skeletal animation for wind and growth
              - Smaller file size

    static (--include-static): Static mesh assemblies with materials and textures (no animation)
              - Full PBR materials from The Grove 2.2
              - Grove attributes disabled by default (use --include-grove-attributes to enable)
              - Better visual quality for static placement

Output:
    Height mode:
        data/output/forest/{species}/tree_####/                           Per-tree directories
        data/output/forest/{species}/tree_####/{species}.usda             Nanite assembly
        data/output/forest/{species}/tree_####/{species}_{tree_id}_skeletal.usda  Tree mesh with skeleton

    Multi-stage mode:
        data/output/forest/{species}/tree_####/{species}_c{cycle}_h{height}_d{dbh}.usda
        Example: data/output/forest/norway_spruce/tree_0001/norway_spruce_c030_h12m5_d32cm.usda

Note:
    Run prepare_assets.py and convert_twigs.py first to prepare species assets.
    This is Step 4 (final step) of the pipeline.

Full Documentation:
    See docs/archive/cli-reference.md for complete flag reference and examples

Usage:
    python src/growpy/cli/generate_forest.py [csv_file] [options]
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

    exported = []

    try:
        # Export directly from already-simulated grove (from forest simulation phase)
        # This grove was grown with inter-species light competition and is ready to export
        # No re-simulation needed - much faster!
        # Note: Smoothing is applied during simulate_forest_growth(), not here

        # CRITICAL BUILD ORDER: skeleton -> bones -> models
        # 1. Build skeletons first
        with timer.track("build_skeletons", parent="grove_export"):
            skeletons = grove.build_skeletons()

        # 2. Tag bone IDs with reduction parameters from quality preset
        # Higher skeleton_length and skeleton_reduce = fewer bones
        # CRITICAL: Unreal Engine has 32,767 bone limit (16-bit signed int)
        # Note: tag_bone_id() takes positional args: (length, reduce, bias, connected)
        with timer.track("tag_bone_id", parent="grove_export"):
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
        with timer.track("build_models", parent="grove_export"):
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
        with timer.track("slice_bones", parent="grove_export"):
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
            tree_name = f"{species_clean}_tree_{tree_id}"

            # Skip trees not in export filter (they still participated in growth simulation)
            if export_tree_ids is not None and tree_fid not in export_tree_ids:
                # Clear memory for skipped tree
                models[model_idx] = None
                skeletons[model_idx] = None
                tree_bones[model_idx] = None
                del model, skeleton, bones_for_tree
                continue

            # Use appropriate twig type based on mesh_type
            use_skeletal = mesh_type == "skeletal"
            use_static = mesh_type == "static"

            # Create tree-specific subfolder with tree ID
            # Assembly uses species name (shared), tree mesh uses tree_id (unique)
            mesh_suffix = "skeletal" if use_skeletal else "static"
            tree_dir = output_dir / species_clean / f"tree_{tree_id}"
            tree_dir.mkdir(parents=True, exist_ok=True)
            usd_path = tree_dir / f"{species_clean}.usda"

            # CRITICAL: Always use skeletal twigs for both skeletal and static assemblies
            # Static twig variants don't exist, and skeletal twigs work as point instances
            # in both assembly types (assembly type only affects tree mesh, not twig references)
            with timer.track("get_twig_usd_map", parent="grove_export"):
                twig_usd_map = get_twig_usd_map_for_species(
                    species, config, prefer_skeletal=True, prefer_static=False
                )

            # Export as Nanite Assembly with specified mesh type
            # tree_id in prim name ensures unique Unreal assets
            with timer.track(
                f"export_nanite_assembly_{mesh_suffix}", parent="grove_export"
            ):
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

                    # Path to the skeletal USD file (tree mesh with skeleton)
                    skeletal_usd_path = (
                        tree_dir / f"{species_clean}_{tree_id}_skeletal.usda"
                    )
                    wind_json_name = f"{tree_name}_DynamicWind.json"
                    wind_json_path = tree_dir / wind_json_name
                    try:
                        with timer.track("generate_wind_json", parent="grove_export"):
                            generate_wind_json(
                                tree_usd_path=skeletal_usd_path,
                                skeleton=skeleton,
                                bones_info=bones_for_tree,
                                output_path=wind_json_path,
                            )
                    except Exception as wind_error:
                        import traceback

                        print(
                            f"Warning: Failed to generate wind JSON for {tree_name}: {wind_error}"
                        )
                        if verbose:
                            traceback.print_exc()

                # Generate PVE preset JSON (optional, skip with --skip-pve-json)
                # Only generate once per tree (skeletal mesh export, not static)
                skip_pve = quality_params.get("skip_pve_json", False)
                profile_pve = quality_params.get("profile_pve", False)
                if use_skeletal and not skip_pve:
                    from growpy.io.pve_grove_mapper import generate_pve_from_grove

                    # Use Unreal PVE naming convention: species_tree_####.json (using fid)
                    pve_variation_name = f"{tree_name}.json"
                    pve_json_path = tree_dir / pve_variation_name
                    pve_config_dir = Path("data/assets/pve_configs")

                    try:
                        with timer.track("generate_pve_json", parent="grove_export"):
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
                        import traceback

                        print(
                            f"Warning: Failed to generate PVE preset JSON for {tree_name}: {pve_error}"
                        )
                        if verbose:
                            traceback.print_exc()

            # MEMORY OPTIMIZATION: Clear this tree's data immediately after export
            # This releases large mesh/skeleton data before processing next tree
            models[model_idx] = None
            skeletons[model_idx] = None
            tree_bones[model_idx] = None
            del model, skeleton, bones_for_tree
            _gc_module.collect()

        # Clear remaining references
        del models, skeletons, tree_bones

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
    mesh_type: str = "skeletal",
    verbose: bool = False,
    timer: Optional["ProfileTimer"] = None,
) -> list:
    """Export trees directly from already-simulated forest groves (no re-simulation).

    Each tree is exported from the grove that was already simulated with inter-species
    light competition in the forest simulation phase. This is significantly faster than
    re-simulating individual trees.

    By default, only skeletal mesh assemblies are generated. Static mesh assemblies
    are only generated if quality_params['include_static'] is True.

    Args:
        forest: List of (grove, species_name, tree_count, fid_list) from create_forest() + simulate_forest_growth()
        forest_data: DataFrame with tree data including species, growth_cycles
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality_params: Quality parameters dict (include_static=True enables static mesh generation)
        mesh_type: Ignored - mesh types are determined by include_static in quality_params
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
        # Only create static mesh task if explicitly requested (--include-static)
        if quality_params.get("include_static", False):
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
        with timer.track("grove_export"):
            result = _export_single_tree_from_forest(task)
            if result:
                exported_files.extend([Path(p) for p in result])

        # MEMORY OPTIMIZATION: Clear grove reference after export to free RAM
        # The grove object holds all simulation data which is no longer needed
        grove_tasks[task_idx] = None

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
    max_cycles: Optional[int] = None,
    growth_cycle_limit: Optional[int] = None,
    smooth_iterations: Optional[int] = None,
    include_grove_attributes: bool = False,
    verbose: bool = False,
    preset_overrides: Optional[PresetOverrides] = None,
    timer: Optional["ProfileTimer"] = None,
    skip_pve_json: bool = False,
    include_static: bool = False,
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
        {species}_c{cycle:03d}_{height}_{dbh}.usda
        e.g., norway_spruce_c030_h12m5_d32cm.usda

    Args:
        csv_path: Path to CSV file with forest data (requires: species, x, y, height)
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality: Quality preset name
        cycle_interval: Export every N cycles (default: 10)
        max_cycles: Cap maximum cycles (default: use height-derived cycles)
        growth_cycle_limit: Scale down cycles if they exceed this limit (like height mode)
        smooth_iterations: Number of smoothing iterations for branches
        include_grove_attributes: If True, include Grove metadata in USD files
        verbose: Print detailed progress information
        preset_overrides: Optional PresetOverrides for dynamic parameter adjustment
        timer: Optional ProfileTimer for tracking execution times
        skip_pve_json: If True, skip PVE preset JSON generation
        include_static: If True, also generate static mesh assemblies
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
        if verbose:
            print("Error: Tree export not available (missing dependencies)")
        return

    if not csv_path.exists():
        if verbose:
            print(f"Error: CSV file not found: {csv_path}")
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
                if verbose:
                    print(f"Error: Missing required columns: {missing_cols}")
                    print(
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
        if verbose:
            print(f"Error loading CSV: {e}")
        return

    # Calculate growth cycles from height using growth models
    with timer.track("calculate_growth_cycles"):
        try:
            calculate_growth_cycles_from_height(forest_data)
        except Exception as e:
            if verbose:
                print(f"Error: Could not calculate growth cycles from height: {e}")
                print(
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
    # CLI max_cycles can further cap if specified
    if max_cycles is not None:
        global_max_cycles = min(global_max_cycles, max_cycles)

    snapshot_cycles = list(
        range(effective_interval, global_max_cycles + 1, effective_interval)
    )

    print(f"\n{'='*60}")
    print("MULTI-STAGE FOREST GENERATION")
    print(f"{'='*60}")
    print(f"  Trees: {len(forest_data)}")
    print(
        f"  Height range: {forest_data['height'].min():.1f}m - {forest_data['height'].max():.1f}m"
    )
    print(f"  Cycle range: {forest_data['growth_cycles'].min()} - {global_max_cycles}")
    print(f"  Interval: {effective_interval}")
    print(f"  Snapshots: {len(snapshot_cycles)} stages {snapshot_cycles}")
    print(f"{'='*60}")

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
    quality_params["include_static"] = include_static
    quality_params["skip_validation"] = skip_validation
    quality_params["export_tree_ids"] = export_tree_ids

    # Apply skeleton overrides (allows simplified skeleton with ultra mesh)
    if skeleton_overrides:
        for key, value in skeleton_overrides.items():
            quality_params[key] = value
        if verbose:
            print(f"[Skeleton Overrides] Applied: {skeleton_overrides}")

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
        if verbose:
            print("Error: No snapshots captured during simulation")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Export each snapshot
    print(f"\n{'='*60}")
    print(f"PHASE 3: EXPORTING STAGES ({len(snapshots)} cycles)")
    print(f"{'='*60}")

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
                assembly_name = f"{species_clean}_c{cycle:03d}_{height_str}_{dbh_str}"
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

                if export_success:
                    exported_files.append(str(usd_path))
                    if verbose:
                        print(f"  Exported: {usd_path.name}")

    print(f"\nExported {len(exported_files)} tree stage files")


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
    include_static: bool = False,
    skip_validation: bool = False,
    skeleton_overrides: Optional[Dict[str, Any]] = None,
    export_tree_ids: Optional[set] = None,
) -> None:
    """Generate forest from CSV data and export as Nanite Assembly USD files.

    By default, only skeletal mesh assemblies are generated (optimized for wind animation).
    Static mesh assemblies can be optionally generated with include_static=True.

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
        include_static: If True, also generate static mesh assemblies (disabled by default, saves ~7% time)
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
        if verbose:
            print("Error: Tree export not available (missing dependencies)")
        return

    if not csv_path.exists():
        if verbose:
            print(f"Error: CSV file not found: {csv_path}")
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
                if verbose:
                    print(f"Error: Missing required columns: {missing_cols}")
                return

            # Z column will be added by create_forest if missing

    except Exception as e:
        if verbose:
            print(f"Error loading CSV: {e}")
        return

    with timer.track("calculate_growth_cycles"):
        try:
            calculate_growth_cycles_from_height(forest_data)
        except Exception as e:
            if verbose:
                print(f"Warning: Could not calculate growth cycles from height: {e}")
                print("  Using default: growth_cycles=10, delay=0")
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
        if verbose:
            print(f"Error creating/simulating forest: {e}")
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
        if verbose:
            print(f"[Skeleton Overrides] Applied: {skeleton_overrides}")

    # CRITICAL: Force minimal export for Nanite compatibility
    # Skeletal meshes: geometry + skeleton only (no materials/textures/attributes)
    # Grove attributes can be optionally added via include_grove_attributes flag
    quality_params["minimal_export"] = True

    # Include Grove attributes if requested (adds ~70% file size to skeletal meshes)
    quality_params["include_grove_attributes"] = include_grove_attributes

    # Skip optional JSON generation (passed via quality_params for simplicity)
    # Note: DynamicWind JSON is always generated for skeletal meshes
    quality_params["skip_pve_json"] = skip_pve_json
    quality_params["include_static"] = include_static
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

    except Exception as e:
        if verbose:
            print(f"Warning: Export failed: {e}")


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
    # Structure: species/tree_0001/{species}.usda (assembly references {species}_{tree_id}_skeletal.usda)
    nanite_files = list(output_dir.glob("*/tree_*/*.usda")) + list(
        output_dir.glob("*/tree_*/*.usd")
    )

    # Filter to only include assembly files (exclude tree mesh and twig files)
    # Tree mesh files have _skeletal or _static suffix
    # Twig files contain "twig" in the name
    # Assembly files include cycle/height metadata but NOT _skeletal/_static suffix
    nanite_files = [
        f
        for f in nanite_files
        if not f.stem.endswith("_skeletal")
        and not f.stem.endswith("_static")
        and "twig" not in f.stem.lower()
    ]

    # Group trees by species (parent of tree_XXXX folder)
    trees_by_species = {}
    for usd_file in nanite_files:
        # Structure: species_dir/tree_XXXX/assembly.usda
        tree_folder = usd_file.parent
        species_folder = tree_folder.parent
        species_name = species_folder.name

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
            tree_folder = usd_file.parent.name
            tree_number = (
                tree_folder.replace("tree_", "")
                if tree_folder.startswith("tree_")
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
        "--growth-cycle-limit",
        type=int,
        default=GROWTH_CYCLE_LIMIT,
        help=f"Maximum growth cycles per tree (default: {GROWTH_CYCLE_LIMIT}). Trees exceeding this will be scaled down proportionally",
    )
    parser.add_argument(
        "--smooth-iterations",
        type=int,
        default=SMOOTH_ITERATIONS,
        help=f"Number of branch smoothing iterations (default: {SMOOTH_ITERATIONS}, range: 0-20). Higher values produce smoother branches with less sharp angles. Set to 0 to disable smoothing",
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
        help="Generate Unreal Python script for importing trees (execute in Unreal via VSCode extension)",
    )
    parser.add_argument(
        "--unreal-project-path",
        type=str,
        default="/Game/GrowPy/Trees",
        help="Unreal project Content path for imports (default: /Game/GrowPy/Trees)",
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
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode: skip PVE JSON, validation, and static mesh generation",
    )
    parser.add_argument(
        "--include-static",
        action="store_true",
        help="Generate static mesh assemblies in addition to skeletal (disabled by default)",
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
        "--max-cycles",
        type=int,
        default=None,
        help="Maximum cycles for multi-stage export. Overrides CSV max_cycles column if present.",
    )
    parser.add_argument(
        "--export-trees",
        type=str,
        default=None,
        help="Comma-separated list of tree IDs (fid) to export. Other trees still participate in growth simulation but are not exported. Example: --export-trees 1,2,5",
    )

    args = parser.parse_args()

    # Initialize profiler
    timer = init_profiler(enabled=args.profile)

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

        # Build preset overrides from CLI arguments
        preset_overrides = None
        if args.longevity_mode:
            preset_overrides = LONGEVITY_OVERRIDES
            print(
                "\n[Longevity Mode] Using pre-configured overrides to prevent tree death:"
            )
            print(f"  Static: {preset_overrides.static_overrides}")
        elif args.preset_override:
            preset_overrides = create_overrides_from_args(
                static_args=args.preset_override,
            )
            print(f"\n[Preset Overrides] Static: {preset_overrides.static_overrides}")

        # Handle --fast flag (skip pve json, validation, and static meshes)
        # Note: DynamicWind JSON is always generated for skeletal meshes
        skip_pve_json = args.skip_pve_json or args.fast
        skip_validation = args.skip_validation or args.fast
        # Static meshes disabled by default, enable with --include-static
        # --fast also disables static (redundant since already default, but explicit)
        include_static = args.include_static and not args.fast

        # Parse --export-trees filter
        export_tree_ids = None
        if args.export_trees:
            try:
                export_tree_ids = set(
                    int(x.strip()) for x in args.export_trees.split(",")
                )
                print(
                    f"\n[Export Filter] Only exporting trees with fid: {sorted(export_tree_ids)}"
                )
            except ValueError:
                print(
                    f"Error: --export-trees must be comma-separated integers, got: {args.export_trees}"
                )
                return

        # Build skeleton overrides from CLI args (allows simplified skeleton with ultra mesh)
        skeleton_overrides = {}
        if args.skeleton_length is not None:
            skeleton_overrides["skeleton_length"] = args.skeleton_length
        if args.skeleton_reduce is not None:
            skeleton_overrides["skeleton_reduce"] = args.skeleton_reduce
        if args.skeleton_bias is not None:
            skeleton_overrides["skeleton_bias"] = args.skeleton_bias
        if args.skeleton_connected is not None:
            skeleton_overrides["skeleton_connected"] = (
                args.skeleton_connected.lower() == "true"
            )
        skeleton_overrides = skeleton_overrides if skeleton_overrides else None

        # Detect cycle-based mode via CLI args (--cycle-interval enables multi-stage mode)
        is_cycle_mode = args.cycle_interval is not None

        with timer.track("total_forest_generation"):
            if is_cycle_mode:
                # Multi-stage export mode: generate trees at different growth stages
                generate_forest_stages(
                    csv_path,
                    args.output_dir,
                    config,
                    args.quality,
                    cycle_interval=args.cycle_interval,
                    max_cycles=args.max_cycles,
                    growth_cycle_limit=args.growth_cycle_limit,
                    smooth_iterations=args.smooth_iterations,
                    include_grove_attributes=args.include_grove_attributes,
                    verbose=args.verbose,
                    preset_overrides=preset_overrides,
                    timer=timer,
                    skip_pve_json=skip_pve_json,
                    include_static=include_static,
                    skip_validation=skip_validation,
                    skeleton_overrides=skeleton_overrides,
                    export_tree_ids=export_tree_ids,
                )
            else:
                # Standard height-based export mode
                generate_forest_exports(
                    csv_path,
                    args.output_dir,
                    config,
                    args.quality,
                    args.growth_cycle_limit,
                    args.smooth_iterations,
                    include_grove_attributes=args.include_grove_attributes,
                    verbose=args.verbose,
                    preset_overrides=preset_overrides,
                    timer=timer,
                    skip_pve_json=skip_pve_json,
                    include_static=include_static,
                    skip_validation=skip_validation,
                    skeleton_overrides=skeleton_overrides,
                    export_tree_ids=export_tree_ids,
                )

        # Print profiling report if enabled
        if args.profile:
            timer.print_report()

        # Generate Unreal scripts if requested
        if args.import_to_unreal:
            # Load forest data for tree positions
            try:
                forest_data = pd.read_csv(csv_path)
                # Ensure fid column exists
                if "fid" not in forest_data.columns:
                    forest_data["fid"] = range(1, len(forest_data) + 1)
            except Exception as e:
                print(f"Warning: Could not load CSV for position data: {e}")
                forest_data = None

            import_script = generate_unreal_import_script(
                args.output_dir,
                args.unreal_project_path,
                forest_data=forest_data,
                export_tree_ids=export_tree_ids,
            )

            cleanup_script = generate_unreal_cleanup_script(
                args.output_dir,
                args.unreal_project_path,
                dry_run=True,  # Default to dry-run mode for safety
            )

            print("\n" + "=" * 60)
            print("UNREAL SCRIPTS GENERATED")
            print("=" * 60)
            print(f"Import script: {import_script}")
            print(f"Cleanup script: {cleanup_script}")
            print("\nTo import trees to Unreal Engine:")
            print("1. Open import_forest.py in VSCode")
            print("2. Right-click > 'Execute Python File in Unreal'")
            print("\nTo cleanup assets:")
            print("1. Open clean_assets.py in VSCode")
            print("2. Review DRY_RUN setting (True = preview, False = delete)")
            print("3. Right-click > 'Execute Python File in Unreal'")
            print("\nRequirements:")
            print("- Unreal Engine must be running")
            print("- USD Importer plugin enabled")
            print("- Editor Scripting Utilities plugin enabled")

    except Exception:
        # Silently fail - allows script to be used in various contexts
        pass


if __name__ == "__main__":
    main()
