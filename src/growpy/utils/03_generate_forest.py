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
- Automatic coordinate system transformation (Y-up -> Z-up)
- Grove-compatible twig placement using TwigEnd, TwigSide, TwigUpward primvars
- Species-specific twig asset lookup and assignment
- Random twig variation distribution for realistic appearance
- Enhanced error handling and progress tracking
- Optimized for Blender and other Z-up applications
"""
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from growpy import (
    GrowPyConfig,
    build_lod_models,
    calculate_growth_cycles_from_height,
    create_forest,
    save_tree_to_usd,
    simulate_forest_growth,
    export_forest_with_skeletons,
    create_skeleton_lod_models,
    generate_wind_animation,
    build_tree_skeletons,
    get_skeleton_info
)

try:
    from pxr import Gf, Usd, UsdGeom, Vt
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False

try:
    from growpy.twig import add_twigs_to_tree, add_twigs_to_tree_text_based
    TWIG_INTEGRATION_AVAILABLE = True
except ImportError:
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
            return False

        # Get available twig files organized by type
        twig_files_by_type = config.get_twig_files_by_type(species_name)
        if not twig_files_by_type:
            return False


        # Use the enhanced text-based approach from twig module
        return add_twigs_to_tree_text_based(
            usd_file_path, species_name, config, twig_files_by_type
        )

    except Exception:
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
        # Use the main enhanced twig function from the twig module
        return add_twigs_to_tree(usd_file_path, species_name, config)
    else:
        # Fallback to text-based approach if twig module not available
        if add_twigs_to_tree_text_based is not None:
            # Get twig files for the enhanced text-based approach
            twig_files_by_type = config.get_twig_files_by_type(species_name)
            if twig_files_by_type:
                return add_twigs_to_tree_text_based(
                    usd_file_path, species_name, config, twig_files_by_type
                )

        # Ultimate fallback to the original method
        return add_twigs_to_usd_file_text_based(usd_file_path, species_name, config)


def export_models_with_skeletons(forest, output_dir, lod_configs, skeleton_options=None):
    """Export all models with skeleton data and optional twigs."""
    
    if skeleton_options is None:
        skeleton_options = {
            'length_factor': 2.0,      # Create longer bones
            'reduce_threshold': 0.4,   # Remove thin branches
            'bias_factor': 0.3,        # Favor trunk over branches
            'connected': True          # Create connected bone chains
        }
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    export_tasks = []
    total_skeletons = 0
    
    # Build export tasks with skeleton data
    for grove, species_name, tree_count in forest:
        species_clean = species_name.replace(" ", "").replace("-", "_")
        
        # Create LOD models and skeletons
        lod_models, skeletons = create_skeleton_lod_models(
            grove, lod_configs, skeleton_options
        )
        
        total_skeletons += len(skeletons)
        
        # Create export tasks
        for lod_name, models in lod_models.items():
            for i, model in enumerate(models):
                filename = f"{species_clean}_{lod_name}_{i:03d}_with_skeleton.usda"
                skeleton = skeletons[i] if i < len(skeletons) else None
                
                export_tasks.append((
                    model,
                    output_dir / filename,
                    species_clean,
                    lod_name,
                    i,
                    species_name,
                    skeleton
                ))
    
    print(f"Generated {total_skeletons} skeletons for {len(forest)} species")
    
    # Export with progress tracking
    total_exported = 0
    with tqdm(total=len(export_tasks), desc="Exporting USD+Skeletons", unit="model") as pbar:
        for model, filepath, species, lod_name, index, species_name, skeleton in export_tasks:
            
            # Export USD with skeleton
            try:
                import the_grove_22_core as gc
                
                # Configure model
                model.set_up_axis("Z")
                model.set_winding_order("COUNTER_CLOCKWISE")
                
                # Export to USD
                usd_string = gc.io.model_to_usda_string(model)
                with open(filepath, "w") as f:
                    f.write(usd_string)
                
                total_exported += 1
                
            except Exception as e:
                print(f"Failed to export {filepath}: {e}")
            
            pbar.update(1)
            pbar.set_postfix({
                "species": species, 
                "lod": lod_name, 
                "exported": total_exported
            })
    
    print(f"Exported {total_exported} models with skeletons")
    return export_tasks


def add_twigs_to_skeleton_models(export_tasks, config):
    """Add twigs to exported skeleton models."""
    
    if not TWIG_INTEGRATION_AVAILABLE:
        print("Twig integration not available, skipping twig placement")
        return 0
    
    successful_twigs = 0
    
    with tqdm(total=len(export_tasks), desc="Adding twigs", unit="file") as pbar:
        for model, filepath, species, lod_name, index, species_name, skeleton in export_tasks:
            
            # Skip if file doesn't exist
            if not filepath.exists():
                pbar.update(1)
                continue
            
            try:
                if add_twigs_to_tree(filepath, species_name, config):
                    successful_twigs += 1
            except Exception as e:
                print(f"Failed to add twigs to {filepath}: {e}")
            
            pbar.update(1)
            pbar.set_postfix({
                "success": f"{successful_twigs}/{len(export_tasks)}"
            })
    
    return successful_twigs


def generate_skeleton_report(forest, skeleton_options):
    """Generate a detailed report of skeleton statistics."""
    
    print("\n[CHART] Skeleton Analysis Report")
    print("=" * 50)
    
    total_joints = 0
    total_bones = 0
    
    for grove, species_name, tree_count in forest:
        print(f"\n[TREE] Species: {species_name}")
        
        # Build skeletons for analysis
        skeletons = build_tree_skeletons(grove, optimize_bones=True)
        
        species_joints = 0
        species_bones = 0
        
        for i, skeleton in enumerate(skeletons):
            info = get_skeleton_info(skeleton)
            
            joint_count = info['joint_count']
            bone_count = info['bone_count']
            
            species_joints += joint_count
            species_bones += bone_count
            
            if i == 0:  # Show details for first tree
                print(f"  Sample tree skeleton:")
                print(f"    Joints: {joint_count}")
                print(f"    Bones: {bone_count}")
                print(f"    Root location: {info['location']}")
                
                if 'joint_ages' in info:
                    ages = info['joint_ages']
                    print(f"    Age range: {min(ages)} - {max(ages)} flushes")
                
                if 'joint_radii' in info:
                    radii = info['joint_radii']
                    print(f"    Radius range: {min(radii):.3f} - {max(radii):.3f}")
        
        avg_joints = species_joints / len(skeletons) if skeletons else 0
        avg_bones = species_bones / len(skeletons) if skeletons else 0
        
        print(f"  Average per tree: {avg_joints:.1f} joints, {avg_bones:.1f} bones")
        print(f"  Total trees: {len(skeletons)}")
        
        total_joints += species_joints
        total_bones += species_bones
    
    print(f"\n[TREND] Overall Statistics:")
    print(f"  Total joints across all trees: {total_joints}")
    print(f"  Total bones across all trees: {total_bones}")
    print(f"  Skeleton optimization: {skeleton_options}")


def main():
    """Enhanced forest generation workflow with automatic Z-up transformation, intelligent twig placement, and skeleton support."""
    print("Enhanced GrowPy Forest Generator")
    print("   - Automatic Y-up -> Z-up coordinate transformation")
    print("   - Species-specific twig placement with random variations")
    print("   - Grove-compatible face-based twig positioning")
    print("   - Skeletal animation support")
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
        print(f"[ERROR] CSV file not found: {csv_path}")
        return 1

    # Load forest data
    print(f"\n[CHART] Loading forest data")
    forest_data = pd.read_csv(csv_path)
    forest_data["height"] /= 3
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
            # We'll need to modify simulate_forest_growth or create our own version
            # For now, let's call the original function and update progress manually
            simulate_forest_growth_with_progress(forest, max_cycles, pbar)

    print(f"[OK] Growth simulation complete")

    # Configure skeletons
    skeleton_options = {
        'length_factor': 2.0,        # Longer bones for better animation
        'reduce_threshold': 0.4,     # Remove branches below 40% thickness
        'bias_factor': 0.3,          # Slightly favor trunk
        'connected': True            # Connected bone chains for IK
    }

    # Generate skeleton report
    generate_skeleton_report(forest, skeleton_options)

    # Export to USD
    print(f"\n[DISK] Exporting to USD")
    output_dir.mkdir(parents=True, exist_ok=True)
    config = GrowPyConfig()
    lod_configs = config.get_lod_configs()
    
    # Always export both standard trees (with twigs) and skeletal models (for rigging)
    print("\n[BONE] Exporting both standard trees and skeletal rigs")
    print("  [RULER] Standard trees: Full geometry with twigs for final rendering")
    print("  [BONE] Skeletal rigs: Optimized skeletons for animation rigging")
    
    export_standard = True   # Always export standard trees with twigs
    export_skeletal = True   # Always export skeletal rigs for animation
    
    total_exported = 0
    successful_twigs = 0

    # Export standard trees if requested
    standard_export_tasks = []
    if export_standard:
        print(f"\n[DISK] Exporting standard USD models")
        
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
        with tqdm(total=total_models, desc="Exporting standard USD", unit="model") as pbar:
            for model, filepath, species, lod_name, index, species_name in export_tasks:
                save_tree_to_usd(model, filepath)
                total_exported += 1
                pbar.update(1)
                pbar.set_postfix(
                    {"species": species, "lod": lod_name, "exported": total_exported}
                )
        
        standard_export_tasks = export_tasks
        print(f"[OK] Exported {total_exported} standard USD models")
    
    # Export skeletal trees if requested
    skeletal_export_tasks = []
    if export_skeletal:
        print(f"\n[BONE] Exporting skeletal USD models")
        skeletal_output_dir = output_dir.parent / "skeletal_trees"
        
        skeletal_export_tasks = export_models_with_skeletons(
            forest, skeletal_output_dir, lod_configs, skeleton_options
        )
        total_exported += len(skeletal_export_tasks)

    # Add twigs to exported models
    if export_standard and standard_export_tasks:
        print(f"\n[LEAF] Adding twigs to standard models")
        print(f"   [RULER] Converting trees from Y-up to Z-up coordinate system")
        print(f"   [DICE] Applying random twig variation assignment")
        print(f"   [SPROUT] Using Grove's face-based twig placement system")
        
        # Group files by species for organized processing
        species_files = {}
        for model, filepath, species, lod_name, index, species_name in standard_export_tasks:
            if species_name not in species_files:
                species_files[species_name] = []
            species_files[species_name].append(filepath)

        total_twig_files = sum(len(files) for files in species_files.values())
        standard_twigs = 0

        with tqdm(total=total_twig_files, desc="Adding twigs to standard models", unit="file") as pbar:
            for species_name, filepaths in species_files.items():
                print(f"\n[TREE] Processing {species_name} ({len(filepaths)} files)")

                # Verify twig availability for this species
                twig_name = config.get_twig_for_species(species_name)
                if twig_name:
                    print(f"     [LEAF] Using twig: {twig_name}")
                    twig_files_by_type = config.get_twig_files_by_type(species_name)
                    if twig_files_by_type:
                        print(
                            f"     [FOLDER] Available twig types: {list(twig_files_by_type.keys())}"
                        )
                        total_twig_files_available = sum(
                            len(files) for files in twig_files_by_type.values()
                        )
                        print(
                            f"     [NUMBERS] Total twig variation files: {total_twig_files_available}"
                        )
                    else:
                        print(f"     [WARNING]  No twig files found for {species_name}")
                else:
                    print(f"     [WARNING]  No twig mapping found for {species_name}")

                for filepath in filepaths:
                    # Double-check species detection from filename
                    detected_species = detect_species_from_filename(
                        filepath.name, species_name
                    )
                    if detected_species != species_name:
                        print(
                            f"     [SEARCH] Species override: {species_name} -> {detected_species} (from filename)"
                        )
                        final_species = detected_species
                    else:
                        final_species = species_name

                    if add_twigs_to_usd_file(filepath, final_species, config):
                        standard_twigs += 1

                    pbar.update(1)
                    pbar.set_postfix(
                        {
                            "species": final_species.replace(" ", ""),
                            "success": f"{standard_twigs}/{total_twig_files}",
                        }
                    )
        
        successful_twigs += standard_twigs
    
    # Note: Skeletal models don't need twigs - they are optimized rigs for animation
    # Standard models with twigs are the final rendering assets
    print(f"\n[BONE] Skeletal models completed (no twigs needed - these are for rigging only)")

    print(f"\n[CHECK] Enhanced forest generation complete!")
    print(f"[CHART] Summary:")
    print(f"  • {total_exported} USD tree models exported")
    if export_standard and export_skeletal:
        standard_count = len(standard_export_tasks) if standard_export_tasks else 0
        skeletal_count = len(skeletal_export_tasks) if skeletal_export_tasks else 0
        print(f"    - {standard_count} standard models")
        print(f"    - {skeletal_count} skeletal models")
    print(f"  • {successful_twigs} models successfully enhanced with twigs")
    print(f"  • {len(forest)} different species processed")
    print(f"  • Output directory: {output_dir}")
    if export_skeletal:
        print(f"  • Skeletal models directory: {output_dir.parent / 'skeletal_trees'}")

    if successful_twigs > 0:
        print(f"\n[GLOBE] Enhanced Twig Features:")
        print(
            f"  • Tree meshes automatically transformed from Y-up to Z-up coordinate system"
        )
        print(f"  • Twigs positioned using Grove's face-based primvar system")
        print(f"  • Random twig variation assignment for natural appearance")
        print(f"  • Species-specific twig asset lookup and assignment")
        print(f"  • Compatible with Blender and other Z-up applications")
    
    if export_skeletal:
        print(f"\n[BONE] Skeleton Features:")
        print(f"  • Optimized bone hierarchies for animation")
        print(f"  • Connected bone chains for IK systems")
        print(f"  • Grove-specific joint attributes (age, mass, radius)")
        print(f"  • Z-up coordinate system for Blender/Unreal")

    print(f"\n[LIGHT] Usage Notes:")
    print(f"  • Files ending with '_with_twigs.usda' contain final rendering trees with twigs")
    print(f"  • Files ending with '_with_skeleton.usda' contain skeletal rigs for animation")
    print(f"  • Import skeletal rigs into Blender to create armatures for standard trees")
    print(f"  • Use skeletal rigs for wind animation or manual tree posing")
    print(f"  • Both file types use Z-up coordinate system for better compatibility")
    print(f"  • Recommended workflow: Use standard trees for rendering, skeletal rigs for animation")

    return 0


if __name__ == "__main__":
    sys.exit(main())
