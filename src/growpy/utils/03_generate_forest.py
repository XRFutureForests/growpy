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
    from growpy.twig import add_twigs_to_tree, add_twigs_to_tree_text_based

    TWIG_INTEGRATION_AVAILABLE = True
    print("✅ Enhanced twig module with Z-up transformation available")
except ImportError:
    print("⚠️  Enhanced twig module not available, using fallback twig integration")
    TWIG_INTEGRATION_AVAILABLE = False
    add_twigs_to_tree = None
    add_twigs_to_tree_text_based = None


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
    This approach works without USD Python bindings but now uses the enhanced
    twig module's text-based approach for consistent behavior.

    Args:
        usd_file_path: Path to the USD tree file
        species_name: Name of the tree species for twig lookup
        config: GrowPyConfig instance for asset lookup

    Returns:
        bool: True if twigs were successfully added, False otherwise
    """
    try:
        # Import the enhanced text-based twig function
        from growpy.twig import add_twigs_to_tree_text_based

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

        # Use the enhanced text-based approach from twig module
        return add_twigs_to_tree_text_based(
            usd_file_path, species_name, config, twig_files_by_type
        )

    except Exception as e:
        print(f"  ❌ Error adding twigs to {usd_file_path}: {e}")
        return False


def detect_species_from_filename(filename, fallback_species="Silver fir"):
    """
    Detect tree species from filename.

    Args:
        filename: Name of the USD file (e.g., "SilverFir_lod0_001.usda")
        fallback_species: Default species to use if detection fails

    Returns:
        str: Detected species name
    """
    filename_lower = filename.lower()

    # Common species mappings from filename patterns to full species names
    species_mappings = {
        "silverfir": "Silver fir",
        "silver_fir": "Silver fir",
        "pacificsilver": "Pacific Silver Fir",
        "pacific_silver": "Pacific Silver Fir",
        "scots_pine": "Scots Pine",
        "scotspine": "Scots Pine",
        "douglas_fir": "Douglas Fir",
        "douglasfir": "Douglas Fir",
        "norway_spruce": "Norway Spruce",
        "norwayspruce": "Norway Spruce",
        "european_beech": "European Beech",
        "europeanbeech": "European Beech",
        "oak": "Oak",
        "birch": "Birch",
        "maple": "Maple",
        "alder": "Alder",
    }

    # Check each mapping pattern
    for pattern, species_name in species_mappings.items():
        if pattern in filename_lower:
            return species_name

    return fallback_species


def add_twigs_to_usd_file(usd_file_path, species_name, config):
    """
    Add twig instances to a USD tree file using the enhanced twig system.
    This function uses the updated twig module with proper Z-up transformation
    and species-specific twig assignment.
    """
    if TWIG_INTEGRATION_AVAILABLE and add_twigs_to_tree is not None:
        print(
            f"  🌿 Using enhanced twig system with Z-up transformation for {species_name}"
        )
        # Use the main enhanced twig function from the twig module
        return add_twigs_to_tree(usd_file_path, species_name, config)
    else:
        # Fallback to text-based approach if twig module not available
        print(
            f"  ⚠️  Enhanced twig module not available, using fallback for {species_name}"
        )
        if add_twigs_to_tree_text_based is not None:
            # Get twig files for the enhanced text-based approach
            twig_files_by_type = config.get_twig_files_by_type(species_name)
            if twig_files_by_type:
                return add_twigs_to_tree_text_based(
                    usd_file_path, species_name, config, twig_files_by_type
                )

        # Ultimate fallback to the original method
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

            # Verify twig availability for this species
            twig_name = config.get_twig_for_species(species_name)
            if twig_name:
                print(f"     🌿 Using twig: {twig_name}")
                twig_files_by_type = config.get_twig_files_by_type(species_name)
                if twig_files_by_type:
                    print(
                        f"     📁 Available twig types: {list(twig_files_by_type.keys())}"
                    )
                    total_twig_files_available = sum(
                        len(files) for files in twig_files_by_type.values()
                    )
                    print(
                        f"     🔢 Total twig variation files: {total_twig_files_available}"
                    )
                else:
                    print(f"     ⚠️  No twig files found for {species_name}")
            else:
                print(f"     ⚠️  No twig mapping found for {species_name}")

            for filepath in filepaths:
                # Double-check species detection from filename
                detected_species = detect_species_from_filename(
                    filepath.name, species_name
                )
                if detected_species != species_name:
                    print(
                        f"     🔍 Species override: {species_name} → {detected_species} (from filename)"
                    )
                    final_species = detected_species
                else:
                    final_species = species_name

                if add_twigs_to_usd_file(filepath, final_species, config):
                    successful_twigs += 1

                pbar.update(1)
                pbar.set_postfix(
                    {
                        "species": final_species.replace(" ", ""),
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
