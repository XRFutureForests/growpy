#!/usr/bin/env python3
"""
Forest generation with USD export and optional Unreal Engine import script generation.

Generates multi-species forests from CSV data with configurable quality settings.
Can generate standalone Unreal Python scripts for importing trees via VSCode extension.
Creates both skeletal (animation-ready) and static (material-rich) Nanite assemblies.

Quick Start (copy-paste ready with all defaults shown):
    # Full forest generation with all flags (recommended for production)
    python src/growpy/cli/generate_forest.py data/input/test.csv --quality ultra --growth-cycle-limit 10 --smooth-iterations 10 --output-dir data/output/forest --preset-override drop_decay=0.1

    # Generate with Unreal import script for one-click import
    python src/growpy/cli/generate_forest.py data/input/test.csv --quality medium --growth-cycle-limit 100 --smooth-iterations 10 --output-dir data/output/forest --import-to-unreal --unreal-project-path /Game/GrowPy/Trees --preset-override drop_decay=0.1

    # Include Grove metadata for debugging/analysis (age, mass, vigor - increases size ~70%)
    python src/growpy/cli/generate_forest.py data/input/test.csv --quality ultra --growth-cycle-limit 10 --smooth-iterations 10 --output-dir data/output/forest --include-grove-attributes

    # Fast preview (lower quality, fewer cycles)
    python src/growpy/cli/generate_forest.py data/input/test.csv --quality medium --growth-cycle-limit 5 --smooth-iterations 5 --output-dir data/output/forest

    # Prevent tree death at high cycle counts by reducing decay
    python src/growpy/cli/generate_forest.py data/input/test.csv --quality ultra --growth-cycle-limit 100 --preset-override drop_decay=0.1

Common Flags:
    [csv_file]                                     Input CSV with tree positions (default: data/input/test.csv)
                                                   Required columns: x, y, species, height; Optional: z (defaults to 0)

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

    -v, --verbose                                  Enable verbose output for PVE preset generation

Note: PVE preset JSON files are always generated automatically for each tree

Assembly Types (both created by default):
    skeletal: Skeletal mesh assemblies with animation support
              - Minimal export: geometry and skeleton only (no materials/textures)
              - Grove attributes disabled by default (use --include-grove-attributes to enable)
              - Supports skeletal animation for wind and growth
              - Smaller file size
              - Reference: species_tree_####_skeletal_nanite_assembly.usda

    static:   Static mesh assemblies with materials and textures (no animation)
              - Full PBR materials from The Grove 2.2
              - Grove attributes disabled by default (use --include-grove-attributes to enable)
              - Better visual quality for static placement
              - Reference: species_tree_####_static_nanite_assembly.usda

Output:
    data/output/forest/{species}/                         Per-species directories
    data/output/forest/{species}/*_skeletal_nanite_assembly.usda  Skeletal assemblies
    data/output/forest/{species}/*_static_nanite_assembly.usda    Static assemblies
    data/output/forest/{species}/*_pve_preset.json        PVE configuration files
    data/output/forest/unreal_import_trees.py             Unreal import script (if --import-to-unreal)

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
from typing import Optional

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


def _export_single_tree_from_forest(args: tuple) -> list:
    """Export all trees from an already-simulated grove (forest simulation phase).

    This exports trees directly from a grove that was already simulated with inter-species
    light competition. No re-simulation is performed - this is significantly faster than
    the old approach of recreating and re-simulating each tree individually.

    Args:
        args: Tuple of (fids, grove_instance, species_name, output_dir, quality_params, mesh_type, verbose)
              fids is a list of original CSV fid values for each tree in the grove
              verbose is boolean for verbose output

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

    (fids, grove, species, output_dir, quality_params, mesh_type, verbose) = args

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
        # Note: Smoothing is applied during simulate_forest_growth(), not here

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
            # Use original CSV fid for naming (with leading zeros)
            tree_fid = fids[model_idx]
            tree_name = f"{species_clean}_tree_{tree_fid:04d}"

            # Use appropriate twig type based on mesh_type
            use_skeletal = mesh_type == "skeletal"
            use_static = mesh_type == "static"

            # Add mesh type suffix to assembly filename to prevent overwriting
            mesh_suffix = "skeletal" if use_skeletal else "static"
            usd_path = species_dir / f"{tree_name}_{mesh_suffix}_nanite_assembly.usda"

            # CRITICAL: Always use skeletal twigs for both skeletal and static assemblies
            # Static twig variants don't exist, and skeletal twigs work as point instances
            # in both assembly types (assembly type only affects tree mesh, not twig references)
            twig_usd_map = get_twig_usd_map_for_species(
                species, config, prefer_skeletal=True, prefer_static=False
            )

            # Export as Nanite Assembly with specified mesh type
            export_success = export_tree_as_nanite_assembly(
                model=model,
                skeleton=skeleton if use_skeletal else None,
                bones_info=bones_for_tree if use_skeletal else None,
                output_path=usd_path,
                species_name=species,
                twig_usd_paths=twig_usd_map,
                include_twigs=True,
                use_skeletal_mesh=use_skeletal,
                use_static_mesh=use_static,
                include_grove_attributes=quality_params.get(
                    "include_grove_attributes", False
                ),
            )

            if export_success:
                exported.append(str(usd_path))

                # Generate wind JSON for skeletal meshes
                if use_skeletal and skeleton and bones_for_tree:
                    from growpy.io.wind_json import generate_wind_json

                    wind_json_path = species_dir / f"{tree_name}_DynamicWind.json"
                    try:
                        generate_wind_json(
                            tree_usd_path=str(usd_path),
                            skeleton=skeleton,
                            bones_info=bones_for_tree,
                            output_path=str(wind_json_path),
                        )
                    except Exception as wind_error:
                        print(
                            f"Warning: Failed to generate wind JSON for {tree_name}: {wind_error}"
                        )

                # Generate PVE preset JSON - ALWAYS (no flag needed)
                # Only generate once per tree (skeletal mesh export, not static)
                if use_skeletal:
                    from growpy.io.pve_grove_mapper import generate_pve_from_grove

                    # Use Unreal PVE naming convention: species_tree_####.json (using fid)
                    pve_variation_name = f"{species_clean}_tree_{tree_fid:04d}.json"
                    pve_json_path = species_dir / pve_variation_name
                    pve_config_dir = Path("data/assets/pve_configs")
                    try:
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
                        )
                    except Exception as pve_error:
                        import traceback

                        print(
                            f"Warning: Failed to generate PVE preset JSON for {tree_name}: {pve_error}"
                        )
                        if verbose:
                            traceback.print_exc()

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
    mesh_type: str = "skeletal",
    verbose: bool = False,
) -> list:
    """Export trees directly from already-simulated forest groves (no re-simulation).

    Each tree is exported from the grove that was already simulated with inter-species
    light competition in the forest simulation phase. This is significantly faster than
    re-simulating individual trees.

    Exports as Nanite Assembly USD files (.usda format) with both skeletal and static mesh types.
    Also generates PVE preset JSON files for use in Unreal's Procedural Vegetation Editor.

    Args:
        forest: List of (grove, species_name, tree_count, fid_list) from create_forest() + simulate_forest_growth()
        forest_data: DataFrame with tree data including species, growth_cycles
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality_params: Quality parameters dict
        mesh_type: Ignored - both skeletal and static are always created
        verbose: Print detailed progress information

    Returns:
        List of exported file paths
    """
    exported_files = []

    # Build tree export tasks from forest groves
    # Each grove contains multiple trees for that species, export all at once
    # Trees are named using their original CSV fid values
    grove_tasks = []

    for grove, species_name, tree_count, fids in forest:
        # Create two tasks per grove - one for skeletal, one for static
        # Pass fids list so each tree can be named with its original CSV fid
        grove_tasks.append(
            (fids, grove, species_name, output_dir, quality_params, "skeletal", verbose)
        )
        grove_tasks.append(
            (fids, grove, species_name, output_dir, quality_params, "static", verbose)
        )

    # Always use sequential processing (bpy/USD not compatible with multiprocessing)
    for task in tqdm(grove_tasks, desc="Exporting groves"):
        result = _export_single_tree_from_forest(task)
        if result:
            exported_files.extend([Path(p) for p in result])

    # PVE JSON generation now happens inline during tree export
    # No separate batch generation needed

    return exported_files


def generate_forest_exports(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    quality: str = "high",
    growth_cycle_limit: Optional[int] = None,
    smooth_iterations: Optional[int] = None,
    mesh_type: str = "skeletal",
    include_grove_attributes: bool = False,
    verbose: bool = False,
    preset_overrides: Optional[PresetOverrides] = None,
) -> None:
    """Generate forest from CSV data and export as Nanite Assembly USD files.

    Exports as .usda format with both skeletal and static mesh structures for Unreal Engine.
    Also generates PVE preset JSON files for each tree.

    Args:
        csv_path: Path to CSV file with forest data
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality: Quality preset name ('ultra', 'high', 'medium', 'low', 'performance')
        growth_cycle_limit: Maximum growth cycles per tree (default: GROWTH_CYCLE_LIMIT)
        smooth_iterations: Number of smoothing iterations for branches (default: SMOOTH_ITERATIONS)
                          Higher values (10-20) produce smoother branches, 0 disables smoothing
        mesh_type: Ignored - both skeletal and static are always created
        include_grove_attributes: If True, include Grove metadata in USD files (increases size ~70%, minimal_export always True for skeletal)
        verbose: Print detailed progress information
        preset_overrides: Optional PresetOverrides for dynamic parameter adjustment during simulation
    """
    # Use defaults if not specified
    if growth_cycle_limit is None:
        growth_cycle_limit = GROWTH_CYCLE_LIMIT
    if smooth_iterations is None:
        smooth_iterations = SMOOTH_ITERATIONS
    height_scale = HEIGHT_SCALE  # Hardcoded height scale

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

        # Z column will be added by create_forest if missing

    except Exception as e:
        return

    try:
        calculate_growth_cycles_from_height(forest_data)
    except Exception:
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
        forest_data["delay"] = max_cycles_after_scaling - forest_data["growth_cycles"]
    else:
        # Use calculated cycles (based on height) if they're within the limit
        # Apply height scale only if not scaling growth cycles
        forest_data["height"] /= height_scale

    try:
        forest = create_forest(forest_data)
        max_cycles = forest_data["growth_cycles"].max()
        # Smoothing is applied automatically during simulation:
        # 1. smooth_minimal() - Fixes ugly kinks on thick branches
        # 2. smooth() - Reduces sharp corner angles (smooth_iterations times)
        # 3. weigh_and_bend() - Re-calculates branch positions with smoothed angles
        simulate_forest_growth(
            forest,
            max_cycles,
            smooth_iterations=smooth_iterations,
            preset_overrides=preset_overrides,
        )
    except Exception as e:
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get quality settings
    quality_params = get_quality_preset(quality)

    # Hardcode skeleton parameters
    quality_params["skeleton_bias"] = 0.5
    quality_params["skeleton_connected"] = True

    # CRITICAL: Force minimal export for Nanite compatibility
    # Skeletal meshes: geometry + skeleton only (no materials/textures/attributes)
    # Grove attributes can be optionally added via include_grove_attributes flag
    quality_params["minimal_export"] = True

    # Include Grove attributes if requested (adds ~70% file size to skeletal meshes)
    quality_params["include_grove_attributes"] = include_grove_attributes

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

        # mesh_type parameter ignored - both skeletal and static are always created
        export_individual_trees(
            forest,
            forest_data,
            output_dir,
            config,
            quality_params,
            mesh_type="skeletal",  # Ignored - both types are created
            verbose=verbose,
        )

    except Exception:
        # Silently fail - export is optional
        pass


def generate_unreal_import_script(
    output_dir: Path,
    project_path: str = "/Game/GrowPy/Trees",
) -> Path:
    """
    Generate a standalone Unreal Python script for importing forest USD files.

    This script can be executed directly in Unreal Engine using:
    - VSCode Unreal Python extension (right-click > Execute in Unreal)
    - Unreal Editor Python console
    - Command line

    Args:
        output_dir: Directory containing exported USD files
        project_path: Unreal project Content path

    Returns:
        Path to generated script file
    """
    # Create unreal_scripts directory in output
    script_dir = output_dir / "unreal_scripts"
    script_dir.mkdir(exist_ok=True)

    script_path = script_dir / "import_forest.py"

    # Find all Nanite Assembly USD files
    nanite_files = list(output_dir.glob("**/*nanite_assembly.usda")) + list(
        output_dir.glob("**/*nanite_assembly.usd")
    )

    # Generate script content with forward slashes to avoid Unicode escape errors
    script_path_str = str(script_path).replace("\\", "/")

    script_content = f'''"""
Unreal Engine script to import GrowPy forest - Auto-generated

Execute this script in Unreal Engine:
1. Right-click this file in VSCode > "Execute Python File in Unreal"
2. Or from Unreal Python console: exec(open(r'{script_path_str}').read())
"""

import unreal

print("=" * 60)
print("GrowPy Forest Import to Unreal Engine")
print("=" * 60)

# Import configuration
IMPORT_PATH = "{project_path}"

print(f"Destination: {{IMPORT_PATH}}")
print(f"Found {len(nanite_files)} Nanite Assembly USD files\\n")

# Get asset tools
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

imported_count = 0
failed_count = 0

'''

    # Add import task for each USD file, organized by species
    for usd_file in nanite_files:
        usd_path = str(usd_file.resolve()).replace("\\", "/")
        asset_name = usd_file.stem

        # Get species name from parent directory (e.g., "european_beech")
        species_folder = usd_file.parent.name
        # Convert to title case for Unreal folder name (e.g., "EuropeanBeech")
        species_display = "".join(
            word.capitalize() for word in species_folder.split("_")
        )

        # Extract tree number (e.g., "0000" from "european_beech_tree_0000_nanite_assembly")
        tree_number = (
            asset_name.split("_tree_")[1].split("_")[0]
            if "_tree_" in asset_name
            else asset_name
        )

        script_content += f"""
# Import {asset_name} to {species_display} folder (tree #{tree_number})
try:
    unreal.log("Importing {asset_name}...")
    
    # Import directly to species folder with custom asset path to avoid nested folders
    species_dest = IMPORT_PATH + "/{species_display}"
    
    # Create import task
    import_task = unreal.AssetImportTask()
    import_task.filename = "{usd_path}"
    import_task.destination_path = species_dest
    import_task.automated = True
    import_task.save = True
    import_task.replace_existing = True
    
    # Configure USD import options
    options = unreal.UsdStageImportOptions()
    options.import_actors = False
    options.import_geometry = True
    options.import_materials = True
    
    import_task.options = options
    
    # Execute import
    asset_tools.import_asset_tasks([import_task])
    
    # Check results
    if import_task.imported_object_paths:
        imported_count += 1
        unreal.log("✓ Imported tree_{tree_number} to {{species_dest}}")
    else:
        failed_count += 1
        unreal.log_warning("✗ Failed to import {asset_name}")
except Exception as e:
    failed_count += 1
    unreal.log_error(f"✗ Error importing {asset_name}: {{e}}")
"""

    script_content += """

print("")
print("=" * 60)
print(f"Import complete: {imported_count} succeeded, {failed_count} failed")
print("=" * 60)

if failed_count > 0:
    unreal.log_warning("Some imports failed. Check that USD Importer plugin is enabled.")
else:
    print(f"\\nAssets imported to Content Browser: {IMPORT_PATH}")
    print("Trees are ready to place in level or use with PCG")
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

        generate_forest_exports(
            csv_path,
            args.output_dir,
            config,
            args.quality,
            args.growth_cycle_limit,
            args.smooth_iterations,
            mesh_type="skeletal",  # Ignored - both skeletal and static are created
            include_grove_attributes=args.include_grove_attributes,
            verbose=args.verbose,
            preset_overrides=preset_overrides,
        )

        # Generate Unreal scripts if requested
        if args.import_to_unreal:
            import_script = generate_unreal_import_script(
                args.output_dir,
                args.unreal_project_path,
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
