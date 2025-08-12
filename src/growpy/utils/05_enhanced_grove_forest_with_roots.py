#!/usr/bin/env python3
"""
Enhanced Grove forest generation with comprehensive root system support.

This script demonstrates advanced Grove API usage with complete tree systems:
1. Proper Grove model building with comprehensive parameters
2. Root system generation using negative gravitropism
3. Skeletal animation support for both trees and roots
4. Face-based twig placement using Grove's attribute system
5. Material and texture integration with species-specific settings
6. Multi-LOD export with full Grove attribute preservation
7. Wind animation generation for dynamic forests
8. Complete underground root architecture simulation

Key Enhanced Features:
- Root system generation with species-specific architectures
- Combined tree+root export for complete plant systems
- Underground visualization support
- Root-specific LOD configurations
- Integration with existing Grove API workflow

Root System Types:
- Tap roots: Deep central roots (oaks, walnuts)
- Fibrous roots: Shallow spreading networks (maples, birches)
- Buttress roots: Large surface roots (tropical trees)
- Adventitious roots: Aerial roots (banyan trees)
"""
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from growpy import (
    GrowPyConfig,
    create_forest,
    set_global_config,
    simulate_forest_growth,
)
from growpy.forest import create_forest_with_attributes

# Import Grove-enhanced functions
from growpy.tree import (
    apply_species_texture_settings,
    build_grove_with_all_attributes,
    build_lod_models,
    build_tree_skeletons,
    export_forest_with_skeletons,
    get_model_attributes,
    get_skeleton_info,
    save_tree_to_usd,
)

# Import root system functionality
try:
    from growpy.roots import (
        RootArchitecture,
        create_root_system,
        get_species_root_type,
        build_root_models,
        save_root_system_to_usd,
        create_combined_tree_with_roots,
        add_roots_to_forest,
    )
    GROVE_ROOTS_AVAILABLE = True
except ImportError:
    GROVE_ROOTS_AVAILABLE = False
    print("⚠️ Root system functionality not available")

try:
    from growpy.twig import add_twigs_to_grove_model, extract_twig_data_from_grove_model

    GROVE_TWIG_AVAILABLE = True
except ImportError:
    GROVE_TWIG_AVAILABLE = False

try:
    import the_grove_22_core as gc

    GROVE_CORE_AVAILABLE = True
except ImportError:
    GROVE_CORE_AVAILABLE = False
    print("Warning: Grove core not available - some features will be limited")


def create_enhanced_grove_forest_with_roots(csv_file: Path, config: GrowPyConfig) -> list:
    """Create forest with enhanced Grove integration including root systems.

    Args:
        csv_file: Path to CSV with tree data (x, y, z, species, height)
        config: GrowPy configuration

    Returns:
        List of (grove, species_name, tree_count, attributes, grove_type) tuples
        where grove_type is either 'tree' or 'roots'
    """
    print("🌲 Creating enhanced Grove forest with root systems...")

    # Load forest data
    forest_data = pd.read_csv(csv_file)
    required_columns = ["x", "y", "z", "species"]

    if not all(col in forest_data.columns for col in required_columns):
        raise ValueError(f"CSV must contain columns: {required_columns}")

    print(
        f"📊 Loaded {len(forest_data)} trees of {forest_data['species'].nunique()} species"
    )

    # Calculate growth cycles if height data available
    if "height" in forest_data.columns:
        try:
            from growpy.tree import calculate_growth_cycles_from_height

            calculate_growth_cycles_from_height(forest_data)
            print("✅ Calculated growth cycles from height data")
        except Exception as e:
            print(f"⚠️ Could not calculate growth cycles: {e}")
            forest_data["delay"] = 0
    else:
        forest_data["delay"] = 0

    # Create forest with enhanced attributes
    forest = create_forest_with_attributes(forest_data)

    # Add grove_type attribute to distinguish trees from roots
    enhanced_forest = []
    for grove, species_name, tree_count, attributes in forest:
        if attributes is None:
            attributes = {}
        attributes['grove_type'] = 'tree'
        enhanced_forest.append((grove, species_name, tree_count, attributes, 'tree'))

    # Generate root systems if available
    if GROVE_ROOTS_AVAILABLE:
        print("🌱 Generating root systems for forest...")
        
        root_forest = []
        for grove, species_name, tree_count, attributes, grove_type in enhanced_forest:
            if grove_type != 'tree':
                continue
                
            print(f"  🌿 Creating roots for {species_name}")
            
            # Determine root type for this species
            root_type = get_species_root_type(species_name)
            print(f"    Root architecture: {root_type}")
            
            # Create root systems for each tree in the grove
            # Simplified approach: create one root grove per species
            try:
                # Get positions from forest data for this species
                species_data = forest_data[forest_data['species'] == species_name]
                
                for idx, tree_row in species_data.iterrows():
                    tree_position = (tree_row['x'], tree_row['y'], tree_row['z'])
                    
                    # Create individual root system
                    root_grove = create_root_system(
                        tree_position=tree_position,
                        species_name=species_name,
                        root_type=root_type,
                        root_count=4 + int(idx % 4),  # 4-7 primary roots
                        growth_cycles=15  # Root growth cycles
                    )
                    
                    if root_grove:
                        root_attributes = {
                            'grove_type': 'roots',
                            'parent_species': species_name,
                            'root_type': root_type,
                            'tree_position': tree_position
                        }
                        
                        root_species_name = f"{species_name} (Roots)"
                        root_forest.append((root_grove, root_species_name, 1, root_attributes, 'roots'))
                        
                        # Only create a few root systems for performance
                        if len([x for x in root_forest if x[1].startswith(species_name)]) >= 3:
                            break
                
                print(f"    ✅ Created root systems for {species_name}")
                
            except Exception as e:
                print(f"    ❌ Error creating roots for {species_name}: {e}")
        
        # Combine tree and root forest
        enhanced_forest.extend(root_forest)
        print(f"🌳 Enhanced forest: {len([x for x in enhanced_forest if x[4] == 'tree'])} tree groves, {len([x for x in enhanced_forest if x[4] == 'roots'])} root groves")
    
    else:
        print("⚠️ Root generation not available, proceeding with trees only")

    return enhanced_forest


def simulate_enhanced_forest_with_comprehensive_features(
    forest: list, cycles: int, config: GrowPyConfig
) -> None:
    """Simulate forest growth with comprehensive Grove features for trees and roots.

    Args:
        forest: List of (grove, species_name, tree_count, attributes, grove_type) tuples
        cycles: Number of growth cycles to simulate
        config: GrowPy configuration
    """
    print(f"🌱 Simulating {cycles} growth cycles with Grove features...")

    # Separate trees and roots for different simulation strategies
    tree_groves = [(grove, species_name, tree_count) for grove, species_name, tree_count, attributes, grove_type in forest if grove_type == 'tree']
    root_groves = [(grove, species_name, tree_count, attributes) for grove, species_name, tree_count, attributes, grove_type in forest if grove_type == 'roots']

    with tqdm(total=cycles, desc="Growth simulation") as pbar:
        for cycle in range(cycles):
            # Simulate tree growth with light competition
            if tree_groves:
                simulate_forest_growth(tree_groves, 1)

            # Simulate root growth (roots don't compete for light but grow independently)
            if GROVE_ROOTS_AVAILABLE and root_groves:
                for root_grove, root_species_name, tree_count, attributes in root_groves:
                    try:
                        root_grove.simulate(1)
                    except Exception as e:
                        print(f"⚠️ Root simulation error for {root_species_name}: {e}")

            pbar.update(1)
            pbar.set_postfix({
                "cycle": f"{cycle + 1}/{cycles}", 
                "trees": len(tree_groves),
                "roots": len(root_groves)
            })


def export_enhanced_forest_with_roots(
    forest: list, output_dir: Path, config: GrowPyConfig
) -> dict:
    """Export forest with comprehensive Grove features including root systems.

    Args:
        forest: List of (grove, species_name, tree_count, attributes, grove_type) tuples
        output_dir: Output directory for exported files
        config: GrowPy configuration

    Returns:
        Dictionary with export statistics
    """
    print("📤 Exporting enhanced forest with trees and root systems...")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Enhanced LOD configurations
    tree_lod_configs = {
        "lod0": {
            "resolution": 24,
            "build_end_cap": True,
            "build_cutoff_thickness": 0.0,
            "build_cutoff_age": 0,
            "build_blend": True,
            "texture_repeat": 1.0,
            "resolution_reduce": 0.9,
        },
        "lod1": {
            "resolution": 16,
            "build_end_cap": True,
            "build_cutoff_thickness": 0.01,
            "build_cutoff_age": 0,
            "build_blend": True,
            "texture_repeat": 1.0,
            "resolution_reduce": 0.8,
        },
        "skeletal": {
            "resolution": 8,
            "build_end_cap": False,
            "build_cutoff_thickness": 0.03,
            "build_cutoff_age": 0,
            "build_blend": True,
            "texture_repeat": 1.0,
            "resolution_reduce": 0.6,
        },
    }

    # Root-specific LOD configurations
    root_lod_configs = {
        "root_high": {
            "resolution": 12,
            "resolution_reduce": 0.8,
            "build_cutoff_thickness": 0.002,
            "build_cutoff_age": 0,
            "build_blend": True,
            "build_end_cap": True,
            "texture_repeat": 1.0,
        },
        "root_medium": {
            "resolution": 8,
            "resolution_reduce": 0.7,
            "build_cutoff_thickness": 0.005,
            "build_cutoff_age": 1,
            "build_blend": True,
            "build_end_cap": True,
            "texture_repeat": 1.0,
        },
        "root_low": {
            "resolution": 6,
            "resolution_reduce": 0.6,
            "build_cutoff_thickness": 0.01,
            "build_cutoff_age": 2,
            "build_blend": False,
            "build_end_cap": False,
            "texture_repeat": 1.0,
        },
    }

    stats = {
        "total_exported": 0,
        "trees_exported": 0,
        "roots_exported": 0,
        "species_processed": 0,
        "skeletons_created": 0,
        "models_with_twigs": 0,
        "total_attributes": 0,
    }

    # Create separate directories for trees and roots
    trees_dir = output_dir / "trees"
    roots_dir = output_dir / "roots"

    for grove, species_name, tree_count, attributes, grove_type in forest:
        print(f"\n🌳 Processing {species_name} ({grove_type}) - {tree_count} instances")

        try:
            species_clean = species_name.replace(" ", "").replace("-", "_").replace("(", "").replace(")", "")
            
            if grove_type == 'tree':
                # Process tree groves
                current_dir = trees_dir
                lod_configs = tree_lod_configs
                
                # Get species-specific texture settings
                texture_aspect_ratio = 1.2  # Default for bark textures
                # Note: Could implement species-specific texture ratios if needed

                # Build comprehensive LOD models
                print(f"  🔨 Building tree LOD models...")
                lod_models = build_lod_models(grove, lod_configs, texture_aspect_ratio)

                # Build skeletons for animation
                print(f"  🦴 Building tree skeletons...")
                skeletons = build_tree_skeletons(grove, optimize_bones=True)
                stats["skeletons_created"] += len(skeletons)

                # Export each LOD level
                for lod_name, models in lod_models.items():
                    print(f"    📦 Exporting {lod_name} ({len(models)} models)")

                    for i, model in enumerate(models):
                        # Apply species-specific texture settings
                        apply_species_texture_settings(model, species_name, config)

                        # Get model attributes
                        model_attrs = get_model_attributes(model)
                        stats["total_attributes"] += len(model_attrs.get("point_attributes", {}))
                        stats["total_attributes"] += len(model_attrs.get("face_attributes", {}))

                        # Export with skeleton data if available
                        if lod_name == "skeletal" and i < len(skeletons):
                            filename = f"{species_clean}_{lod_name}_{i:03d}_with_skeleton.usda"
                            filepath = current_dir / filename

                            from growpy.tree import save_tree_with_skeleton
                            save_tree_with_skeleton(model, skeletons[i], filepath, texture_aspect_ratio)
                            print(f"    ✅ Exported with skeleton: {filename}")
                        else:
                            filename = f"{species_clean}_{lod_name}_{i:03d}.usda"
                            filepath = current_dir / filename
                            save_tree_to_usd(model, filepath, texture_aspect_ratio=texture_aspect_ratio)
                            print(f"    ✅ Exported: {filename}")

                        # Try to integrate Grove twig system
                        if GROVE_TWIG_AVAILABLE:
                            try:
                                twig_success = add_twigs_to_grove_model(model, species_name, config)
                                if twig_success:
                                    stats["models_with_twigs"] += 1
                                    print(f"    🌿 Added Grove-based twigs")
                            except Exception as e:
                                print(f"    ⚠️ Twig integration failed: {e}")

                        stats["total_exported"] += 1
                        stats["trees_exported"] += 1

            elif grove_type == 'roots' and GROVE_ROOTS_AVAILABLE:
                # Process root groves
                current_dir = roots_dir
                
                print(f"  🌱 Building root system models...")
                root_models = build_root_models(grove, root_lod_configs)

                # Export root models
                for lod_name, models in root_models.items():
                    print(f"    📦 Exporting {lod_name} ({len(models)} models)")

                    for i, model in enumerate(models):
                        filename = f"{species_clean}_{lod_name}_{i:03d}.usda"
                        filepath = current_dir / filename

                        save_tree_to_usd(model, filepath, texture_aspect_ratio=0.8)  # Different ratio for roots
                        print(f"    ✅ Exported root model: {filename}")

                        stats["total_exported"] += 1
                        stats["roots_exported"] += 1

            stats["species_processed"] += 1

        except Exception as e:
            print(f"  ❌ Error processing {species_name}: {e}")
            continue

    return stats


def generate_grove_wind_animation(
    forest: list, output_dir: Path, config: GrowPyConfig
) -> bool:
    """Generate wind animation using Grove's animation system (trees only).

    Args:
        forest: List of (grove, species_name, tree_count, attributes, grove_type) tuples
        output_dir: Output directory for animation files
        config: GrowPy configuration

    Returns:
        bool: True if wind animation was generated successfully
    """
    if not GROVE_CORE_AVAILABLE:
        print("⚠️ Grove core not available for wind animation")
        return False

    print("💨 Generating Grove wind animation (trees only)...")

    wind_dir = output_dir / "wind_animation"
    wind_dir.mkdir(parents=True, exist_ok=True)

    # Wind parameters
    wind_vector = (1.0, 0.5, 0.0)  # Wind direction
    frame_count = 60  # Animation frames
    turbulence = 1.5  # Wind strength

    try:
        # Only animate trees, not roots
        tree_forest = [(grove, species_name, tree_count, attributes) for grove, species_name, tree_count, attributes, grove_type in forest if grove_type == 'tree']
        
        for grove, species_name, tree_count, attributes in tree_forest:
            print(f"  🌬️ Creating wind animation for {species_name}")

            from growpy.tree import generate_wind_animation

            wind_shapes = generate_wind_animation(
                grove, wind_vector, frame_count, turbulence
            )

            if wind_shapes:
                # Export wind animation frames
                species_clean = species_name.replace(" ", "").replace("-", "_")

                for frame_idx, wind_shape in enumerate(wind_shapes):
                    filename = f"{species_clean}_wind_frame_{frame_idx:03d}.usda"
                    filepath = wind_dir / filename

                    save_tree_to_usd(wind_shape, filepath)

                print(f"    ✅ Generated {len(wind_shapes)} wind animation frames")
            else:
                print(f"    ⚠️ No wind shapes generated for {species_name}")

        return True

    except Exception as e:
        print(f"❌ Wind animation generation failed: {e}")
        return False


def main():
    """Main function demonstrating comprehensive Grove API usage with root systems."""
    print("🚀 Enhanced Grove Forest Generation with Root Systems")
    print("=" * 60)

    # Configuration
    config = GrowPyConfig(
        random_seed=42,
        output_dir=Path("output/grove_enhanced_forest_with_roots"),
        lod_levels=["lod0", "lod1", "skeletal", "root_high", "root_medium", "root_low"],
    )
    set_global_config(config)

    # Input data
    script_dir = Path(__file__).parent
    input_csv = script_dir.parent.parent.parent / "data" / "input" / "small_demo.csv"

    if not input_csv.exists():
        print(f"❌ Input file not found: {input_csv}")
        print(
            "Please ensure the CSV file exists with columns: x, y, z, species, height"
        )
        return 1

    try:
        # Create enhanced forest with root systems
        forest = create_enhanced_grove_forest_with_roots(input_csv, config)

        # Simulate with comprehensive Grove features
        simulate_enhanced_forest_with_comprehensive_features(
            forest, cycles=25, config=config
        )

        # Export with full Grove feature set including roots
        stats = export_enhanced_forest_with_roots(
            forest, config.output_dir, config
        )

        # Generate wind animation (trees only)
        wind_success = generate_grove_wind_animation(forest, config.output_dir, config)

        # Print comprehensive statistics
        print(f"\n🎉 Enhanced Grove Forest Generation Complete!")
        print(f"📊 Export Statistics:")
        print(f"  • Species processed: {stats['species_processed']}")
        print(f"  • Total models exported: {stats['total_exported']}")
        print(f"    - Tree models: {stats['trees_exported']}")
        print(f"    - Root models: {stats['roots_exported']}")
        print(f"  • Skeletons created: {stats['skeletons_created']}")
        print(f"  • Models with twigs: {stats['models_with_twigs']}")
        print(f"  • Total attributes: {stats['total_attributes']}")
        print(f"  • Wind animation: {'✅' if wind_success else '❌'}")
        print(f"📁 Output directory: {config.output_dir}")
        print(f"  • Trees: {config.output_dir / 'trees'}")
        print(f"  • Roots: {config.output_dir / 'roots'}")
        print(f"  • Wind: {config.output_dir / 'wind_animation'}")

        if GROVE_ROOTS_AVAILABLE:
            print(f"\n🌱 Root System Features:")
            root_groves = [x for x in forest if x[4] == 'roots']
            root_types = set()
            for grove, species_name, tree_count, attributes, grove_type in root_groves:
                if attributes and 'root_type' in attributes:
                    root_types.add(attributes['root_type'])
            
            print(f"  • Root architectures generated: {', '.join(root_types)}")
            print(f"  • Root systems created: {len(root_groves)}")
            print(f"  • Species-specific root patterns applied")
            print(f"  • Underground growth simulation using negative gravitropism")
            print(f"  • Root-specific LOD configurations for performance")
        else:
            print(f"\n⚠️ Root system generation was not available")

        print(f"\n🎯 Usage Notes:")
        print(f"  • Tree models in 'trees/' directory for above-ground vegetation")
        print(f"  • Root models in 'roots/' directory for underground systems")
        print(f"  • Combine tree and root models for complete plant visualization")
        print(f"  • Root models use species-appropriate architecture patterns")
        print(f"  • Wind animation applies to trees only (roots are underground)")
        print(f"  • All models use Z-up coordinate system for compatibility")

        return 0

    except Exception as e:
        print(f"❌ Forest generation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
