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
    add_bone_ids_to_model,
    apply_species_texture_settings,
    build_lod_models,
    calculate_growth_cycles_from_height,
    create_forest,
    save_tree_to_usd,
    save_tree_with_skeleton,
    simulate_forest_growth,
    export_forest_with_skeletons,
    create_skeleton_lod_models,
    generate_wind_animation,
    build_tree_skeletons,
    get_skeleton_info,
    get_model_attributes
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
    """Export all models with skeleton data using enhanced growpy functions."""
    
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
    
    # Build export tasks with enhanced skeleton data
    for grove, species_name, tree_count in forest:
        species_clean = species_name.replace(" ", "").replace("-", "_")
        
        # Create LOD models and skeletons using enhanced functions
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
    
    # Export with progress tracking using enhanced functions
    total_exported = 0
    config = GrowPyConfig()
    
    with tqdm(total=len(export_tasks), desc="Exporting USD+Skeletons", unit="model") as pbar:
        for model, filepath, species, lod_name, index, species_name, skeleton in export_tasks:
            
            try:
                # Apply species-specific material and texture settings
                apply_species_texture_settings(model, species_name, config)
                
                # Add bone IDs for proper skeleton binding (like Blender export)
                if skeleton:
                    add_bone_ids_to_model(model, skeleton)
                
                # Export with skeleton using enhanced function
                save_tree_with_skeleton(model, skeleton, filepath, texture_aspect_ratio=1.2)
                total_exported += 1
                
            except Exception as e:
                print(f"Failed to export {filepath}: {e}")
            
            pbar.update(1)
            pbar.set_postfix({
                "species": species, 
                "lod": lod_name, 
                "exported": total_exported
            })
    
    print(f"Exported {total_exported} models with skeletons and enhanced features")
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
    """Generate a detailed report of skeleton statistics and Grove model attributes."""
    
    print("\n[CHART] Enhanced Grove Model Analysis Report")
    print("=" * 60)
    
    total_joints = 0
    total_bones = 0
    total_attributes = 0
    
    for grove, species_name, tree_count in forest:
        print(f"\n[TREE] Species: {species_name}")
        
        # Build skeletons for analysis
        skeletons = build_tree_skeletons(grove, optimize_bones=True)
        
        # Build a sample model to analyze attributes
        try:
            sample_models = build_lod_models(grove, {"sample": {"resolution": 16, "build_end_cap": True}})
            sample_model = sample_models["sample"][0] if sample_models["sample"] else None
        except:
            sample_model = None
        
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
        
        # Show Grove model attributes
        if sample_model:
            print(f"  Grove model attributes:")
            attrs = get_model_attributes(sample_model)
            
            geom = attrs['geometry']
            print(f"    Geometry: {geom['point_count']} points, {geom['face_count']} faces")
            
            point_attrs = attrs['point_attributes']
            face_attrs = attrs['face_attributes']
            attr_count = len(point_attrs) + len(face_attrs)
            total_attributes += attr_count
            
            if point_attrs:
                print(f"    Point attributes ({len(point_attrs)}): {list(point_attrs.keys())}")
            if face_attrs:
                print(f"    Face attributes ({len(face_attrs)}): {list(face_attrs.keys())}")
        
        avg_joints = species_joints / len(skeletons) if skeletons else 0
        avg_bones = species_bones / len(skeletons) if skeletons else 0
        
        print(f"  Average per tree: {avg_joints:.1f} joints, {avg_bones:.1f} bones")
        print(f"  Total trees: {len(skeletons)}")
        
        total_joints += species_joints
        total_bones += species_bones
    
    print(f"\n[TREND] Overall Enhanced Statistics:")
    print(f"  Total joints across all trees: {total_joints}")
    print(f"  Total bones across all trees: {total_bones}")
    print(f"  Total Grove attributes processed: {total_attributes}")
    print(f"  Enhanced skeleton features: bone IDs, material mapping, UV correction")
    print(f"  Skeleton optimization: {skeleton_options}")


def main():
    """Enhanced forest generation workflow using proper Grove API with full feature support."""
    print("Enhanced GrowPy Forest Generator with Grove API Integration")
    print("   - Proper Grove model building with comprehensive parameters")
    print("   - Enhanced skeleton export with bone IDs (matches Blender format)")
    print("   - Species-specific material and texture mapping")
    print("   - Working twig placement with Grove face-based system")
    print("   - Wind animation generation for dynamic trees")
    print("   - Automatic Y-up -> Z-up coordinate transformation")
    print("   - Multi-LOD export with full Grove attribute preservation")
    print("=" * 70)

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
    forest_data["height"] /= 4
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

        # Export with progress bar using enhanced features
        with tqdm(total=total_models, desc="Exporting standard USD", unit="model") as pbar:
            for model, filepath, species, lod_name, index, species_name in export_tasks:
                # Apply species-specific material and texture settings
                apply_species_texture_settings(model, species_name, config)
                
                # Export using enhanced function
                save_tree_to_usd(model, filepath, texture_aspect_ratio=1.2)
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

    # Generate wind animation if skeletal models were created
    wind_animation_success = False
    if export_skeletal and skeletal_export_tasks:
        print(f"\n[WIND] Generating wind animation for skeletal trees...")
        try:
            animation_dir = output_dir.parent / "wind_animation"
            animation_dir.mkdir(parents=True, exist_ok=True)
            
            animation_count = 0
            for grove, species_name, tree_count in forest:
                try:
                    # Generate wind animation frames
                    wind_shapes = generate_wind_animation(
                        grove, 
                        wind_vector=(1.0, 0.2, 0.0),  # Gentle horizontal wind
                        frame_count=24,  # Animation frames
                        turbulence=0.8   # Moderate wind strength
                    )
                    
                    if wind_shapes:
                        species_clean = species_name.replace(" ", "").replace("-", "_")
                        for frame_idx, wind_shape in enumerate(wind_shapes):
                            anim_filename = f"{species_clean}_wind_frame_{frame_idx:03d}.usda"
                            anim_filepath = animation_dir / anim_filename
                            
                            # Apply material settings and export
                            apply_species_texture_settings(wind_shape, species_name, config)
                            save_tree_to_usd(wind_shape, anim_filepath, texture_aspect_ratio=1.2)
                            animation_count += 1
                        
                        print(f"     ✅ Generated {len(wind_shapes)} wind frames for {species_name}")
                    
                except Exception as e:
                    print(f"     ⚠️ Wind animation failed for {species_name}: {e}")
            
            if animation_count > 0:
                wind_animation_success = True
                print(f"[OK] Generated {animation_count} total wind animation frames")
            
        except Exception as e:
            print(f"     ⚠️ Wind animation generation failed: {e}")

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
    print(f"  • Wind animation: {'✅ Generated' if wind_animation_success else '❌ Not generated'}")
    print(f"  • Output directory: {output_dir}")
    if export_skeletal:
        print(f"  • Skeletal models directory: {output_dir.parent / 'skeletal_trees'}")
    if wind_animation_success:
        print(f"  • Wind animation directory: {output_dir.parent / 'wind_animation'}")

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
        print(f"\n[BONE] Enhanced Skeleton Features:")
        print(f"  • Optimized bone hierarchies for animation")
        print(f"  • Bone IDs (gr_bone_id primvar) compatible with Blender export format")
        print(f"  • Connected bone chains for IK systems")
        print(f"  • Grove-specific joint attributes (age, mass, radius)")
        print(f"  • Species-specific material and texture mapping")
        print(f"  • Z-up coordinate system for Blender/Unreal compatibility")

    print(f"\n[LIGHT] Enhanced Usage Notes:")
    print(f"  • Files ending with '_with_twigs.usda' contain final rendering trees")
    print(f"  • Files ending with '_with_skeleton.usda' contain rigged models for animation")
    print(f"  • Wind animation frames in 'wind_animation' directory for dynamic effects")
    print(f"  • All exports include proper Grove attributes and material settings")
    print(f"  • Skeleton exports include bone IDs matching Blender format")
    print(f"  • Working twig placement preserves Grove's face-based system")
    print(f"  • Z-up coordinate system ensures compatibility with major 3D software")
    print(f"  • Enhanced workflow: Standard trees for rendering, skeletal for animation")

    return 0


if __name__ == "__main__":
    sys.exit(main())
