#!/usr/bin/env python3
"""
Forest generation with USD export and optional Unreal Engine import script generation.

Generates multi-species forests from CSV data with configurable quality settings.
Can generate standalone Unreal Python scripts for importing trees via VSCode extension.

Quick Start:
    # Generate forest (creates both skeletal and static mesh assemblies)
    # Output: aspen_tree_0000_skeletal_nanite_assembly.usda + aspen_tree_0000_static_nanite_assembly.usda
    python src/growpy/cli/generate_forest.py --quality high --growth-cycle-limit 3

    # Generate forest and create Unreal import script
    python src/growpy/cli/generate_forest.py --quality high --import-to-unreal

    # Or specify a different CSV file
    python src/growpy/cli/generate_forest.py my_forest.csv --quality high --import-to-unreal

Common Flags:
    --quality {ultra,high,medium,low,performance}  Quality preset (default: ultra)
    --growth-cycle-limit INT                       Max growth cycles (default: 10)
    --height-scale FLOAT                           Tree height scale (default: 1.0)
    --output-dir PATH                              Output directory
    --import-to-unreal                             Generate Unreal import script
    --unreal-project-path PATH                     Unreal destination (default: /Game/GrowPy/Trees)

Assembly Types (both created by default):
    skeletal: Skeletal mesh assemblies with animation support (no materials/textures)
              - Supports skeletal animation for wind and growth
              - Smaller file size
              - Reference: species_tree_####_skeletal_nanite_assembly.usda

    static:   Static mesh assemblies with materials and textures (no animation)
              - Full PBR materials from The Grove 2.2
              - Better visual quality
              - Reference: species_tree_####_static_nanite_assembly.usda

Full Documentation:
    See docs/archive/cli-reference.md for complete flag reference and examples

Usage:
    python src/growpy/cli/generate_forest.py [csv_file] --quality high --output-dir data/output/forest --growth-cycle-limit 5 --import-to-unreal
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
SMOOTH_ITERATIONS = 3  # Recommended: 10-20 iterations for natural smoothing

from growpy import (
    TREE_EXPORT_AVAILABLE,
    GrowPyConfig,
    calculate_growth_cycles_from_height,
    create_forest,
    get_config,
    simulate_forest_growth,
)
from growpy.config.quality import get_quality_preset


def _export_single_tree_from_forest(args: tuple) -> list:
    """Export all trees from an already-simulated grove (forest simulation phase).

    This exports trees directly from a grove that was already simulated with inter-species
    light competition. No re-simulation is performed - this is significantly faster than
    the old approach of recreating and re-simulating each tree individually.

    Args:
        args: Tuple of (start_idx, grove_instance, species_name, output_dir, quality_params)
              start_idx is the base tree number for sequential numbering

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

    (start_idx, grove, species, output_dir, quality_params, mesh_type) = args

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
            # Use sequential numbering: start_idx + model_idx
            tree_num = start_idx + model_idx
            tree_name = f"{species_clean}_tree_{tree_num:04d}"

            # Use appropriate twig type based on mesh_type
            use_skeletal = mesh_type == "skeletal"
            use_static = mesh_type == "static"

            # Add mesh type suffix to assembly filename to prevent overwriting
            mesh_suffix = "skeletal" if use_skeletal else "static"
            usd_path = species_dir / f"{tree_name}_{mesh_suffix}_nanite_assembly.usda"

            twig_usd_map = get_twig_usd_map_for_species(
                species, config, prefer_skeletal=use_skeletal, prefer_static=use_static
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

                # Generate PVE preset JSON (for both skeletal and static meshes)
                from growpy.io.pve_grove_mapper import generate_pve_from_grove

                pve_json_path = species_dir / f"{tree_name}_PVEPreset.json"
                try:
                    generate_pve_from_grove(
                        grove=grove,
                        output_path=pve_json_path,
                        species_name=species,
                        tree_index=model_idx,
                        verbose=False,
                    )
                except Exception as pve_error:
                    print(
                        f"Warning: Failed to generate PVE preset JSON for {tree_name}: {pve_error}"
                    )

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
    generate_pve_json: bool = False,
) -> list:
    """Export trees directly from already-simulated forest groves (no re-simulation).

    Each tree is exported from the grove that was already simulated with inter-species
    light competition in the forest simulation phase. This is significantly faster than
    re-simulating individual trees.

    Exports as Nanite Assembly USD files (.usda format) with both skeletal and static mesh types.
    Optionally also generates PVE preset JSON files for use in Unreal's Procedural Vegetation Editor.

    Args:
        forest: List of (grove, species_name, tree_count) from create_forest() + simulate_forest_growth()
        forest_data: DataFrame with tree data including species, growth_cycles
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality_params: Quality parameters dict
        mesh_type: Ignored - both skeletal and static are always created
        generate_pve_json: If True, also generate PVE preset JSON for each tree

    Returns:
        List of exported file paths
    """
    exported_files = []

    # Build tree export tasks from forest groves
    # Each grove contains multiple trees for that species, export all at once
    # Trees are numbered per-species (starting at 0) since each species has its own folder
    grove_tasks = []

    for grove, species_name, tree_count in forest:
        # Create two tasks per grove - one for skeletal, one for static
        # start_idx=0 for each grove since trees are numbered within species folder
        grove_tasks.append(
            (0, grove, species_name, output_dir, quality_params, "skeletal")
        )
        grove_tasks.append(
            (0, grove, species_name, output_dir, quality_params, "static")
        )

    # Always use sequential processing (bpy/USD not compatible with multiprocessing)
    for task in tqdm(grove_tasks, desc="Exporting groves"):
        result = _export_single_tree_from_forest(task)
        if result:
            exported_files.extend([Path(p) for p in result])

    # Generate PVE preset JSON files if requested
    if generate_pve_json:
        try:
            from growpy.io.pve_preset_json import generate_pve_preset_json

            pve_dir = output_dir / "pve_presets"
            pve_dir.mkdir(parents=True, exist_ok=True)

            for grove, species_name, tree_count in tqdm(
                forest, desc="Generating PVE presets"
            ):
                species_clean = (
                    "".join(
                        c for c in species_name if c.isalnum() or c in (" ", "-", "_")
                    )
                    .strip()
                    .replace(" ", "_")
                    .lower()
                )

                species_pve_dir = pve_dir / species_clean
                species_pve_dir.mkdir(parents=True, exist_ok=True)

                # Generate JSON for each tree in the grove
                for tree_idx in range(tree_count):
                    tree_name = f"{species_clean}_tree_{tree_idx:04d}"
                    json_path = species_pve_dir / f"{tree_name}.json"

                    generate_pve_preset_json(
                        grove=grove,
                        species_name=tree_name,
                        output_path=json_path,
                        tree_index=tree_idx,
                    )
                    exported_files.append(json_path)

            print(f"\nPVE preset JSONs saved to: {pve_dir}")
        except Exception as e:
            print(f"Warning: PVE JSON generation failed: {e}")

    return exported_files


def generate_forest_exports(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    quality: str = "high",
    growth_cycle_limit: Optional[int] = None,
    mesh_type: str = "skeletal",
    generate_pve_json: bool = False,
) -> None:
    """Generate forest from CSV data and export as Nanite Assembly USD files.

    Exports as .usda format with both skeletal and static mesh structures for Unreal Engine.
    Optionally also generates PVE preset JSON files.

    Args:
        csv_path: Path to CSV file with forest data
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality: Quality preset name ('ultra', 'high', 'medium', 'low', 'performance')
        growth_cycle_limit: Maximum growth cycles per tree (default: GROWTH_CYCLE_LIMIT)
        mesh_type: Ignored - both skeletal and static are always created
        generate_pve_json: If True, also generate PVE preset JSON for each tree
    """
    # Use defaults if not specified
    if growth_cycle_limit is None:
        growth_cycle_limit = GROWTH_CYCLE_LIMIT
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

    # Scale growth cycles if max exceeds growth_cycle_limit
    max_growth_cycles = forest_data["growth_cycles"].max()
    if max_growth_cycles > growth_cycle_limit:
        scale_factor = growth_cycle_limit / max_growth_cycles
        forest_data["growth_cycles"] = (
            forest_data["growth_cycles"] * scale_factor
        ).astype(int)
        forest_data["growth_cycles"] = forest_data["growth_cycles"].clip(lower=1)
    else:
        # Apply height scale only if not scaling growth cycles
        forest_data["height"] /= height_scale

    try:
        forest = create_forest(forest_data)
        max_cycles = forest_data["growth_cycles"].max()
        # Smoothing is applied automatically during simulation:
        # 1. smooth_minimal() - Fixes ugly kinks on thick branches
        # 2. smooth() - Reduces sharp corner angles (SMOOTH_ITERATIONS times)
        # 3. weigh_and_bend() - Re-calculates branch positions with smoothed angles
        simulate_forest_growth(forest, max_cycles, smooth_iterations=SMOOTH_ITERATIONS)
    except Exception as e:
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get quality settings
    quality_params = get_quality_preset(quality)

    # Hardcode skeleton parameters
    quality_params["skeleton_bias"] = 0.5
    quality_params["skeleton_connected"] = True

    # CRITICAL: Force clean export for Nanite compatibility
    # Materials, textures, and masks cause import failures with skeletal Nanite assemblies
    quality_params["clean_export"] = True

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
            generate_pve_json=generate_pve_json,
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
                            print(f"✓ Removed empty directory: {{CLEANUP_PATH}}")
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

    # Use a different CSV file with custom output directory
    python src/growpy/cli/generate_forest.py my_forest.csv --output-dir data/output/my_forest --quality ultra --growth-cycle-limit 15

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
        "--generate-pve-json",
        action="store_true",
        help="Generate PVE preset JSON files for Procedural Vegetation Editor in Unreal",
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
        generate_forest_exports(
            csv_path,
            args.output_dir,
            config,
            args.quality,
            args.growth_cycle_limit,
            mesh_type="skeletal",  # Ignored - both skeletal and static are created
            generate_pve_json=args.generate_pve_json,
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
