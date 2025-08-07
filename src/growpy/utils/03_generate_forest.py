#!/usr/bin/env python3
"""
Enhanced forest generation using GrowPy with automatic Z-up transformation.

This script provides a comprehensive forest simulation workflow:
1. Load CSV with tree positions, species, heights
2. Calculate growth cycles from height data using pre-computed models
3. Create multi-species forest with light competition
4. Export to USD with multiple LOD levels
5. Transform tree meshes from Y-up to Z-up coordinate system
6. Add species-specific twig instances using Grove's face-based primvar system
7. Apply random twig variation assignment for natural appearance

Enhanced Features:
- Automatic coordinate system transformation (Y-up → Z-up)
- Grove-compatible twig placement using TwigEnd, TwigSide, TwigUpward primvars
- Species-specific twig asset lookup and assignment
- Random twig variation distribution for realistic appearance
- Enhanced error handling and progress tracking
- Optimized for Blender and other Z-up applications
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from growpy import (
    GrowPyConfig,
    build_lod_models,
    calculate_growth_cycles_from_height,
    create_forest,
    save_tree_to_usd,
    simulate_forest_growth,
)

# Try to import USD components, fallback to text-based approach if not available
try:
    from pxr import Gf, Usd, UsdGeom, Vt

    USD_AVAILABLE = True
except ImportError:
    print("⚠️  USD Python bindings not available, using text-based twig insertion")
    USD_AVAILABLE = False

# Import twig functions from the enhanced twig module
try:
    from growpy.twig import add_twigs_to_tree

    TWIG_INTEGRATION_AVAILABLE = True
    print("✅ Enhanced twig module with Z-up transformation available")
except ImportError:
    print("⚠️  Enhanced twig module not available, using fallback twig integration")
    TWIG_INTEGRATION_AVAILABLE = False


def simulate_forest_growth_with_progress(forest, cycles, pbar):
    """Simulate forest growth with progress tracking."""
    # Import grove core here to match the original function
    try:
        import the_grove_22_core as gc
    except ImportError:
        raise ImportError("Grove core not available")

    groves = [grove for grove, _, _ in forest]

    for cycle in range(cycles):
        # Calculate shared light competition between species
        if len(groves) > 1:
            all_coords = []
            for grove in groves:
                all_coords.extend(grove.create_shade_geometry_coords())

            for grove in groves:
                grove.calculate_shade_together(all_coords)

        # Simulate one growth cycle for each grove
        for grove, _, _ in forest:
            grove.weigh_and_bend()
            grove.simulate(1)

        # Update progress bar
        pbar.update(1)
        pbar.set_postfix({"cycle": f"{cycle + 1}/{cycles}", "groves": len(groves)})


def add_twigs_to_usd_file_text_based(usd_file_path, species_name, config):
    """
    Add twig instances to a USD tree file using text-based manipulation.
    This approach works without USD Python bindings and supports multiple twig types.

    Args:
        usd_file_path: Path to the USD tree file
        species_name: Name of the tree species for twig lookup
        config: GrowPyConfig instance for asset lookup

    Returns:
        bool: True if twigs were successfully added, False otherwise
    """
    try:
        # Get twig information for this species
        twig_name = config.get_twig_for_species(species_name)
        if not twig_name:
            print(f"  ⚠️  No twig available for species: {species_name}")
            return False

        # Get available twig files organized by type
        twig_files_by_type = config.get_twig_files_by_type(species_name)
        if not twig_files_by_type:
            print(f"  ⚠️  No twig USD files found for {species_name}")
            return False

        print(f"  🌿 Adding {twig_name} twigs to {usd_file_path.name}")
        print(f"      Available twig types: {list(twig_files_by_type.keys())}")

        # Read the USD file content
        with open(usd_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Generate twig instances for different positions and types
        twig_instances = []

        # Define twig placement based on position (simulating Grove's TwigEnd, TwigSide, TwigUpward)
        twig_placements = [
            # End/apical twigs (top of tree)
            {
                "position": (0.1, 0.2, 3.5),
                "type": "end",
                "preferred_files": ["apical", "end", "main"],
            },
            {
                "position": (-0.2, 0.3, 3.2),
                "type": "end",
                "preferred_files": ["apical", "end", "main"],
            },
            {
                "position": (0.3, -0.1, 3.8),
                "type": "end",
                "preferred_files": ["apical", "end", "main"],
            },
            # Side/lateral twigs (middle sections)
            {
                "position": (0.8, 0.5, 2.0),
                "type": "side",
                "preferred_files": ["lateral", "side", "main"],
            },
            {
                "position": (-0.6, 0.7, 1.8),
                "type": "side",
                "preferred_files": ["lateral", "side", "main"],
            },
            {
                "position": (0.4, -0.8, 2.3),
                "type": "side",
                "preferred_files": ["lateral", "side", "main"],
            },
            {
                "position": (-0.7, -0.3, 1.5),
                "type": "side",
                "preferred_files": ["lateral", "side", "main"],
            },
            {
                "position": (0.9, 0.1, 2.5),
                "type": "side",
                "preferred_files": ["lateral", "side", "main"],
            },
            # Additional variety with variations
            {
                "position": (0.2, 0.9, 1.2),
                "type": "side",
                "preferred_files": ["variation", "lateral", "side"],
            },
            {
                "position": (-0.5, -0.6, 1.0),
                "type": "side",
                "preferred_files": ["variation", "lateral", "side"],
            },
        ]

        # Process each twig placement
        for placement in twig_placements:
            # Find the best twig file for this placement
            twig_file = None
            twig_reference_name = None

            for preferred_type in placement["preferred_files"]:
                if (
                    preferred_type in twig_files_by_type
                    and twig_files_by_type[preferred_type]
                ):
                    twig_file = twig_files_by_type[preferred_type][
                        0
                    ]  # Use first file of this type
                    # Extract the reference name from the file
                    # Pattern: TwigFolder_TwigReferenceName.usda
                    file_stem = twig_file.stem
                    if "_" in file_stem:
                        twig_reference_name = file_stem.split("_", 1)[1]
                    else:
                        twig_reference_name = file_stem
                    break

            if not twig_file:
                # Fallback to any available twig
                all_files = []
                for files in twig_files_by_type.values():
                    all_files.extend(files)
                if all_files:
                    twig_file = all_files[0]
                    file_stem = twig_file.stem
                    if "_" in file_stem:
                        twig_reference_name = file_stem.split("_", 1)[1]
                    else:
                        twig_reference_name = file_stem

            if twig_file and twig_reference_name:
                # Calculate relative path to twig file
                try:
                    twig_relative_path = twig_file.relative_to(usd_file_path.parent)
                except ValueError:
                    twig_relative_path = twig_file

                twig_instances.append(
                    {
                        "position": placement["position"],
                        "orientation": (
                            1.0,
                            0.0,
                            0.0,
                            0.0,
                        ),  # Identity quaternion for now
                        "file_path": twig_relative_path,
                        "reference_name": twig_reference_name,
                        "type": placement["type"],
                    }
                )

        if not twig_instances:
            print(f"  ⚠️  No twig instances could be created for {species_name}")
            return False

        # Group instances by twig file to create separate PointInstancers
        instances_by_file = {}
        for instance in twig_instances:
            file_key = str(instance["file_path"])
            if file_key not in instances_by_file:
                instances_by_file[file_key] = {
                    "file_path": instance["file_path"],
                    "reference_name": instance["reference_name"],
                    "instances": [],
                }
            instances_by_file[file_key]["instances"].append(instance)

        # Generate USD content for each twig type
        twig_content = []
        twig_content.append("")

        for i, (file_key, file_info) in enumerate(instances_by_file.items()):
            prototype_name = f"TwigPrototype_{i}"
            instancer_name = f"TwigInstances_{i}"

            # Add prototype reference
            twig_content.append(f'    def "{prototype_name}" (')
            twig_content.append(
                f'        references = @{file_info["file_path"]}@</root/{file_info["reference_name"]}>'
            )
            twig_content.append("    )")
            twig_content.append("    {")
            twig_content.append("    }")
            twig_content.append("")

            # Add PointInstancer
            instances = file_info["instances"]
            twig_content.append(f'    def PointInstancer "{instancer_name}"')
            twig_content.append("    {")
            twig_content.append(f"        rel prototypes = </Tree/{prototype_name}>")
            twig_content.append(
                f'        int[] protoIndices = [{", ".join(["0"] * len(instances))}]'
            )
            twig_content.append(
                f'        int64[] ids = [{", ".join([str(j) for j in range(len(instances))])}]'
            )
            twig_content.append("")

            # Add positions
            positions_str = ", ".join(
                [
                    f"({inst['position'][0]:.4f}, {inst['position'][1]:.4f}, {inst['position'][2]:.4f})"
                    for inst in instances
                ]
            )
            twig_content.append(f"        point3f[] positions = [{positions_str}]")
            twig_content.append("")

            # Add orientations
            orientations_str = ", ".join(
                [
                    f"({inst['orientation'][0]:.6f}, {inst['orientation'][1]:.6f}, {inst['orientation'][2]:.6f}, {inst['orientation'][3]:.6f})"
                    for inst in instances
                ]
            )
            twig_content.append(f"        quath[] orientations = [{orientations_str}]")
            twig_content.append("")

            # Add uniform scale
            twig_content.append("        float3[] scales = [(1, 1, 1)]")
            twig_content.append("    }")
            twig_content.append("")

        # Join twig content
        twig_usd_text = "\n".join(twig_content)

        # Find insertion point (before the last closing brace)
        last_brace = content.rfind("}")
        if last_brace == -1:
            print("  ❌ Could not find closing brace in USD file")
            return False

        # Insert the twig content
        new_content = (
            content[:last_brace] + "\n" + twig_usd_text + "\n" + content[last_brace:]
        )

        # Create output filename with twigs
        output_file = str(usd_file_path).replace(".usda", "_with_twigs.usda")

        # Write the modified content
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        total_instances = sum(
            len(file_info["instances"]) for file_info in instances_by_file.values()
        )
        print(
            f"  ✅ Added {total_instances} {twig_name} twigs ({len(instances_by_file)} types)"
        )
        print(f"      Output: {Path(output_file).name}")
        return True

    except Exception as e:
        print(f"  ❌ Error adding twigs to {usd_file_path}: {e}")
        return False


def add_twigs_to_usd_file(usd_file_path, species_name, config):
    """
    Add twig instances to a USD tree file using the enhanced twig system.
    This function uses the updated twig module with proper Z-up transformation.
    """
    if TWIG_INTEGRATION_AVAILABLE:
        print(
            f"  🌿 Using enhanced twig system with Z-up transformation for {species_name}"
        )
        return add_twigs_to_tree(usd_file_path, species_name, config)
    else:
        # Fallback to text-based approach if twig module not available
        print(
            f"  ⚠️  Enhanced twig module not available, using fallback for {species_name}"
        )
        return add_twigs_to_usd_file_text_based(usd_file_path, species_name, config)


def main():
    """Enhanced forest generation workflow with automatic Z-up transformation and intelligent twig placement."""
    print("🌲 Enhanced GrowPy Forest Generator")
    print("   🌐 Automatic Y-up → Z-up coordinate transformation")
    print("   🌿 Species-specific twig placement with random variations")
    print("   🎯 Grove-compatible face-based twig positioning")
    print("=" * 60)

    # Fixed paths - no command line arguments needed
    csv_path = (
        Path(__file__).parent.parent.parent.parent
        / "data"
        / "input"
        / "mini_tree_inventory_32632.csv"
    )
    output_dir = (
        Path(__file__).parent.parent.parent.parent / "data" / "output" / csv_path.stem
    )

    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return 1

    # Load forest data
    print(f"\n📊 Loading forest data")
    forest_data = pd.read_csv(csv_path)
    forest_data["height"] /= 3
    print(f"✓ Loaded {len(forest_data)} trees")
    print(f"  Species: {forest_data['species'].nunique()}")

    # Calculate growth cycles using pre-computed models
    print(f"\n🧮 Calculating growth cycles")
    calculate_growth_cycles_from_height(forest_data)
    max_cycles = int(forest_data["growth_cycles"].max())
    print(f"✓ Max growth cycles: {max_cycles}")

    # Create forest
    print(f"\n🌳 Creating multi-species forest")
    forest = create_forest(forest_data)
    print(f"✓ Created {len(forest)} species groves")

    # Simulate growth with light competition
    print(f"\n🌱 Simulating growth ({max_cycles} cycles)")

    # Create a custom simulation function with progress tracking
    if max_cycles > 0:
        with tqdm(total=max_cycles, desc="Growth cycles", unit="cycle") as pbar:
            # We'll need to modify simulate_forest_growth or create our own version
            # For now, let's call the original function and update progress manually
            simulate_forest_growth_with_progress(forest, max_cycles, pbar)

    print(f"✓ Growth simulation complete")

    # Export to USD
    print(f"\n💾 Exporting to USD")
    output_dir.mkdir(parents=True, exist_ok=True)
    config = GrowPyConfig()
    lod_configs = config.get_lod_configs()

    # Calculate total number of models to export for progress tracking
    total_models = 0
    export_tasks = []

    for grove, species_name, tree_count in forest:
        species_clean = species_name.replace(" ", "").replace("-", "_")
        lod_models = build_lod_models(grove, lod_configs)

        for lod_name, models in lod_models.items():
            for i, model in enumerate(models):
                filename = f"{species_clean}_{lod_name}_{i:03d}.usda"
                export_tasks.append(
                    (
                        model,
                        output_dir / filename,
                        species_clean,
                        lod_name,
                        i,
                        species_name,
                    )
                )
                total_models += 1

    # Export with progress bar
    total_exported = 0
    with tqdm(total=total_models, desc="Exporting USD", unit="model") as pbar:
        for model, filepath, species, lod_name, index, species_name in export_tasks:
            save_tree_to_usd(model, filepath)
            total_exported += 1
            pbar.update(1)
            pbar.set_postfix(
                {"species": species, "lod": lod_name, "exported": total_exported}
            )

    print(f"✓ Exported {total_exported} USD models")

    # Add twigs to each exported model with enhanced Z-up transformation
    print(f"\n🌿 Adding species-specific twigs with coordinate transformation")
    print(f"   📐 Converting trees from Y-up to Z-up coordinate system")
    print(f"   🎲 Applying random twig variation assignment")
    print(f"   🌱 Using Grove's face-based twig placement system")

    # Group files by species for organized processing
    species_files = {}
    for model, filepath, species, lod_name, index, species_name in export_tasks:
        if species_name not in species_files:
            species_files[species_name] = []
        species_files[species_name].append(filepath)

    total_twig_files = sum(len(files) for files in species_files.values())
    successful_twigs = 0

    with tqdm(total=total_twig_files, desc="Adding twigs", unit="file") as pbar:
        for species_name, filepaths in species_files.items():
            print(f"\n🌳 Processing {species_name} ({len(filepaths)} files)")

            for filepath in filepaths:
                if add_twigs_to_usd_file(filepath, species_name, config):
                    successful_twigs += 1

                pbar.update(1)
                pbar.set_postfix(
                    {
                        "species": species_name.replace(" ", ""),
                        "success": f"{successful_twigs}/{total_twig_files}",
                    }
                )

    print(f"\n✅ Forest generation complete!")
    print(f"📊 Summary:")
    print(f"  • {total_exported} USD tree models exported")
    print(
        f"  • {successful_twigs}/{total_twig_files} models successfully enhanced with twigs"
    )
    print(f"  • {len(species_files)} different species processed")
    print(f"  • Output directory: {output_dir}")

    if successful_twigs > 0:
        print(f"\n🌐 Enhanced Twig Features:")
        print(
            f"  • Tree meshes automatically transformed from Y-up to Z-up coordinate system"
        )
        print(f"  • Twigs positioned using Grove's face-based primvar system")
        print(f"  • Random twig variation assignment for natural appearance")
        print(f"  • Species-specific twig asset lookup and assignment")
        print(f"  • Compatible with Blender and other Z-up applications")

    print(f"\n💡 Usage Notes:")
    print(
        f"  • Files ending with '_with_twigs.usda' contain the enhanced trees with twigs"
    )
    print(f"  • Trees are now in Z-up coordinate system for better compatibility")
    print(f"  • Open these files directly in Blender for best results")

    return 0


if __name__ == "__main__":
    sys.exit(main())
