#!/usr/bin/env python3
"""
Forest generation using GrowPy with twig placement and color support.

This script provides a forest simulation workflow:
1. Load CSV with tree positions, species, heights
2. Calculate growth cycles from height data using pre-computed models
3. Create multi-species forest with light competition
4. Export to USD with multiple LOD levels
5. Transform tree meshes from Y-up to Z-up coordinate system
6. Add species-specific twig instances using Grove's face-based primvar system
7. Apply species-specific colors for natural appearance

Features:
- Automatic coordinate system transformation (Y-up -> Z-up)
- Grove-compatible twig placement using TwigEnd, TwigSide, TwigUpward primvars
- Species-specific twig asset lookup and assignment
- Species-specific color settings for bark, branches, and leaves
- Enhanced error handling and progress tracking
- Optimized for Blender and other Z-up applications
"""
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from growpy import (
    GrowPyConfig,
    apply_species_color_settings,
    build_lod_models,
    calculate_growth_cycles_from_height,
    create_forest,
    save_tree_to_usd,
    save_tree_to_usd_with_twigs,
    can_species_have_twigs,
    simulate_forest_growth,
    get_model_attributes
)

try:
    from pxr import Gf, Usd, UsdGeom, Vt
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False

try:
    from growpy.twig import add_twigs_to_tree
    TWIG_INTEGRATION_AVAILABLE = True
except ImportError:
    TWIG_INTEGRATION_AVAILABLE = False
    add_twigs_to_tree = None


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


# Text-based approach removed - now using only USD-based approach


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
    Add twig instances to a USD tree file using the USD-based twig system.
    This function uses the updated twig module with proper Z-up transformation
    and species-specific twig assignment.
    """
    if TWIG_INTEGRATION_AVAILABLE and add_twigs_to_tree is not None:
        # Use the main enhanced twig function from the twig module
        return add_twigs_to_tree(usd_file_path, species_name, config)
    else:
        print(f"  ⚠️  Twig integration not available for {species_name}")
        return False


def main():
    """Forest generation workflow using Grove API with twig placement and color support."""
    print("GrowPy Forest Generator with Grove API Integration")
    print("   - Grove model building with comprehensive parameters")
    print("   - Species-specific color settings for natural appearance")
    print("   - Working twig placement with Grove face-based system")
    print("   - Automatic Y-up -> Z-up coordinate transformation")
    print("   - Multi-LOD export with full Grove attribute preservation")
    print("=" * 70)

    # Fixed paths - no command line arguments needed
    csv_path = (
        Path(__file__).parent.parent.parent.parent
        / "data"
        / "input"
        / "illustration_gis.csv"
    )
    output_dir = (
        Path(__file__).parent.parent.parent.parent / "data" / "output" / csv_path.stem
    )

    if not csv_path.exists():
        print(f"[ERROR] CSV file not found: {csv_path}")
        return 1

    # Load forest data
    print(f"\n[CHART] Loading forest data")
    forest_data = pd.read_csv(csv_path)
    forest_data["height"] /= 4
    forest_data["x"] *=2
    forest_data["y"] *=2
    print(f"[OK] Loaded {len(forest_data)} trees")
    print(f"  Species: {forest_data['species'].nunique()}")

    # Calculate growth cycles using pre-computed models
    print(f"\n[CALC] Calculating growth cycles")
    calculate_growth_cycles_from_height(forest_data)
    max_cycles = int(forest_data["growth_cycles"].max())
    print(f"[OK] Max growth cycles: {max_cycles}")

    # Create forest
    print(f"\n[TREE] Creating multi-species forest")
    forest = create_forest(forest_data)
    print(f"[OK] Created {len(forest)} species groves")

    # Simulate growth with light competition
    print(f"\n[SPROUT] Simulating growth ({max_cycles} cycles)")

    # Create a custom simulation function with progress tracking
    if max_cycles > 0:
        with tqdm(total=max_cycles, desc="Growth cycles", unit="cycle") as pbar:
            simulate_forest_growth_with_progress(forest, max_cycles, pbar)

    print(f"[OK] Growth simulation complete")

    # Create organized output folder structure
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subfolders for better organization
    base_dir = output_dir / "base"
    twigs_dir = output_dir / "twigs"
    
    base_dir.mkdir(parents=True, exist_ok=True)
    twigs_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[FOLDER] Created organized output structure:")
    print(f"  • Main output: {output_dir}")
    print(f"  • Trees without twigs: {base_dir}")
    print(f"  • Trees with twigs: {twigs_dir}")
    
    config = GrowPyConfig()
    lod_configs = config.get_lod_configs()
    
    # Configure export options
    print("\n[CONFIG] Configuring export options")
    print("  [RULER] Standard trees: Base models + twig enhancement + color application")
    
    export_standard = True   # Always export standard trees and organize by twig status
    
    total_exported = 0
    successful_twigs = 0

    # Export standard trees if requested
    standard_export_tasks = []
    if export_standard:
        print(f"\n[DISK] Exporting USD models with intelligent twig placement and color application")
        print(f"   [FOLDER] Files saved directly to correct folders based on twig availability")
        
        # Calculate total number of models to export for progress tracking
        total_models = 0
        export_tasks = []

        for grove, species_name, tree_count in forest:
            species_clean = species_name.replace(" ", "").replace("-", "_")
            lod_models = build_lod_models(grove, lod_configs)

            # Check if this species can have twigs
            has_twigs = can_species_have_twigs(species_name, config)
            print(f"[TREE] {species_name}: {'✅ Twigs available' if has_twigs else '❌ No twigs'}")

            for lod_name, models in lod_models.items():
                for i, model in enumerate(models):
                    filename = f"{species_clean}_{lod_name}_{i:03d}.usda"
                    # Use a base path for the filename, actual directory will be determined by save function
                    base_path = output_dir / filename
                    export_tasks.append(
                        (
                            model,
                            base_path,
                            species_clean,
                            lod_name,
                            i,
                            species_name,
                        )
                    )
                    total_models += 1

        # Export with progress bar and intelligent placement
        with tqdm(total=total_models, desc="Exporting USD with twigs and colors", unit="model") as pbar:
            for model, base_path, species, lod_name, index, species_name in export_tasks:
                # Apply species-specific color settings
                apply_species_color_settings(model, species_name, config)
                
                # Save to correct directory based on twig availability
                actual_path = save_tree_to_usd_with_twigs(
                    model, base_path, species_name, config, 
                    base_dir, twigs_dir
                )
                
                # Update export task with actual path for tracking
                export_tasks[export_tasks.index((model, base_path, species, lod_name, index, species_name))] = (
                    model, actual_path, species, lod_name, index, species_name
                )
                
                total_exported += 1
                pbar.update(1)
                pbar.set_postfix(
                    {"species": species, "lod": lod_name, "exported": total_exported}
                )
        
        standard_export_tasks = export_tasks
        
        # Count files in each folder for summary
        base_count = len(list(base_dir.glob("*.usda")))
        twigs_count = len(list(twigs_dir.glob("*.usda")))
        successful_twigs = twigs_count  # Number of files that got twigs and were moved
        
        print(f"[OK] Exported {total_exported} USD models with intelligent placement")
        print(f"[FOLDER] File organization results:")
        print(f"  • {base_count} base models in base/ (without twig instances)")
        print(f"  • {twigs_count} enhanced models in twigs/ (with twig instances)")

    print(f"\n[CHECK] Forest generation complete!")
    print(f"[CHART] Summary:")
    print(f"  • {total_exported} USD tree models exported")
    if export_standard:
        standard_count = len(standard_export_tasks) if standard_export_tasks else 0
        base_count = len(list(base_dir.glob("*.usda")))
        twigs_count = len(list(twigs_dir.glob("*.usda")))
        print(f"    - {base_count} base models without twigs (in base/)")
        print(f"    - {twigs_count} enhanced models with twigs (in twigs/)")
    print(f"  • {successful_twigs} models successfully enhanced with twigs")
    print(f"  • {len(forest)} different species processed")
    print(f"  • Output directory: {output_dir}")
    print(f"    - Trees without twigs: {base_dir}")
    print(f"    - Trees with twigs: {twigs_dir}")

    if successful_twigs > 0:
        print(f"\n[GLOBE] Enhanced Twig Features:")
        print(
            f"  • Tree meshes automatically transformed from Y-up to Z-up coordinate system"
        )
        print(f"  • Twigs positioned using Grove's face-based primvar system")
        print(f"  • Random twig variation assignment for natural appearance")
        print(f"  • Species-specific twig asset lookup and assignment")
        print(f"  • Compatible with Blender and other Z-up applications")
    
    print(f"\n[COLOR] Enhanced Color Features:")
    print(f"  • Species-specific color settings for bark, branches, and leaves")
    print(f"  • Natural wood brown fallback colors for undefined species")
    print(f"  • Color integration with Grove model system")

    print(f"\n[LIGHT] Enhanced Usage Notes:")
    print(f"  • Trees without twigs (base/): Initial tree models without twig instances")
    print(f"  • Trees with twigs (twigs/): Final rendering trees with twig instances")
    print(f"  • All exports include proper Grove attributes and color settings")
    print(f"  • Working twig placement preserves Grove's face-based system")
    print(f"  • Z-up coordinate system ensures compatibility with major 3D software")
    print(f"  • Enhanced workflow: base/ for base models, twigs/ for final rendering")
    print(f"  • Organized folder structure within input CSV named directory")

    return 0


if __name__ == "__main__":
    sys.exit(main())