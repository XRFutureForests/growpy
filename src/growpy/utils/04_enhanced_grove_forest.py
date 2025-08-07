#!/usr/bin/env python3
"""
Enhanced Grove-integrated forest generation with proper API usage.

This script demonstrates correct usage of the Grove API through GrowPy:
1. Proper Grove model building with comprehensive parameters
2. Skeletal animation support using Grove's skeleton system
3. Face-based twig placement using Grove's attribute system
4. Material and texture integration with species-specific settings
5. Multi-LOD export with full Grove attribute preservation
6. Wind animation generation for dynamic forests

Key Grove API Features Used:
- grove.build_models() with comprehensive build parameters
- grove.build_skeletons() for animation support
- model.set_up_axis("Z") and model.set_winding_order("COUNTER_CLOCKWISE")
- model.apply_uv_aspect_ratio() for texture correction
- gc.io.model_to_usda_string() for proper USD export
- Face attribute system for twig placement
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


def create_enhanced_grove_forest(csv_file: Path, config: GrowPyConfig) -> list:
    """Create forest with enhanced Grove integration.

    Args:
        csv_file: Path to CSV with tree data (x, y, z, species, height)
        config: GrowPy configuration

    Returns:
        List of (grove, species_name, tree_count, attributes) tuples
    """
    print("🌲 Creating enhanced Grove forest...")

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

    return forest


def simulate_grove_forest_with_comprehensive_features(
    forest: list, cycles: int, config: GrowPyConfig
) -> None:
    """Simulate forest growth with comprehensive Grove features.

    Args:
        forest: List of (grove, species_name, tree_count, attributes) tuples
        cycles: Number of growth cycles to simulate
        config: GrowPy configuration
    """
    print(f"🌱 Simulating {cycles} growth cycles with Grove features...")

    with tqdm(total=cycles, desc="Growth simulation") as pbar:
        for cycle in range(cycles):
            # Use enhanced forest simulation
            simulate_forest_growth(forest, 1)

            pbar.update(1)
            pbar.set_postfix({"cycle": f"{cycle + 1}/{cycles}", "species": len(forest)})


def export_grove_forest_with_full_features(
    forest: list, output_dir: Path, config: GrowPyConfig
) -> dict:
    """Export forest with comprehensive Grove features.

    Args:
        forest: List of (grove, species_name, tree_count, attributes) tuples
        output_dir: Output directory for exported files
        config: GrowPy configuration

    Returns:
        Dictionary with export statistics
    """
    print("📤 Exporting forest with full Grove features...")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Enhanced LOD configurations using proper Grove parameters
    lod_configs = {
        "lod0": {
            "resolution": 24,  # High resolution cross-sections
            "build_end_cap": True,  # Cap branch ends
            "build_cutoff_thickness": 0.0,  # Build all branches
            "build_cutoff_age": 0,  # Build all ages
            "build_blend": True,  # Smooth transitions
            "texture_repeat": 1.0,  # Standard UV repeat
            "resolution_reduce": 0.9,  # Minimal reduction
        },
        "lod1": {
            "resolution": 16,  # Medium resolution
            "build_end_cap": True,
            "build_cutoff_thickness": 0.01,
            "build_cutoff_age": 0,
            "build_blend": True,
            "texture_repeat": 1.0,
            "resolution_reduce": 0.8,
        },
        "lod2": {
            "resolution": 12,  # Lower resolution
            "build_end_cap": True,
            "build_cutoff_thickness": 0.02,
            "build_cutoff_age": 1,  # Skip youngest branches
            "build_blend": True,
            "texture_repeat": 1.0,
            "resolution_reduce": 0.7,
        },
        "skeletal": {
            "resolution": 8,  # Skeleton-optimized
            "build_end_cap": False,  # No end caps for animation
            "build_cutoff_thickness": 0.03,
            "build_cutoff_age": 0,
            "build_blend": True,
            "texture_repeat": 1.0,
            "resolution_reduce": 0.6,
        },
    }

    # Skeleton options for animation
    skeleton_options = {
        "length_factor": 2.0,
        "reduce_threshold": 0.4,
        "bias_factor": 0.3,
        "connected": True,
    }

    stats = {
        "total_exported": 0,
        "species_processed": 0,
        "skeletons_created": 0,
        "models_with_twigs": 0,
        "total_attributes": 0,
    }

    for grove, species_name, tree_count, attributes in forest:
        print(f"\n🌳 Processing {species_name} ({tree_count} trees)")

        try:
            # Get species-specific texture settings
            species_data = config.get_species_data(species_name)
            texture_aspect_ratio = 1.2  # Default for bark textures
            if species_data and "texture_aspect_ratio" in species_data:
                texture_aspect_ratio = float(species_data["texture_aspect_ratio"])

            # Build comprehensive LOD models with proper Grove parameters
            print(f"  🔨 Building LOD models with Grove API...")
            lod_models = build_lod_models(grove, lod_configs, texture_aspect_ratio)

            # Build skeletons for animation
            print(f"  🦴 Building skeletons...")
            skeletons = build_tree_skeletons(grove, optimize_bones=True)
            stats["skeletons_created"] += len(skeletons)

            # Export each LOD level
            species_clean = species_name.replace(" ", "").replace("-", "_")

            for lod_name, models in lod_models.items():
                print(f"    📦 Exporting {lod_name} ({len(models)} models)")

                for i, model in enumerate(models):
                    # Apply species-specific texture settings
                    apply_species_texture_settings(model, species_name, config)

                    # Get comprehensive model attributes
                    model_attrs = get_model_attributes(model)
                    stats["total_attributes"] += len(
                        model_attrs.get("point_attributes", {})
                    )
                    stats["total_attributes"] += len(
                        model_attrs.get("face_attributes", {})
                    )

                    # Export with skeleton data
                    if lod_name == "skeletal" and i < len(skeletons):
                        filename = (
                            f"{species_clean}_{lod_name}_{i:03d}_with_skeleton.usda"
                        )
                        filepath = output_dir / filename

                        from growpy.tree import save_tree_with_skeleton

                        save_tree_with_skeleton(
                            model, skeletons[i], filepath, texture_aspect_ratio
                        )

                        print(f"    ✅ Exported with skeleton: {filename}")
                    else:
                        filename = f"{species_clean}_{lod_name}_{i:03d}.usda"
                        filepath = output_dir / filename

                        save_tree_to_usd(
                            model, filepath, texture_aspect_ratio=texture_aspect_ratio
                        )
                        print(f"    ✅ Exported: {filename}")

                    # Try to integrate Grove twig system
                    if GROVE_TWIG_AVAILABLE:
                        try:
                            twig_success = add_twigs_to_grove_model(
                                model, species_name, config
                            )
                            if twig_success:
                                stats["models_with_twigs"] += 1
                                print(f"    🌿 Added Grove-based twigs")
                        except Exception as e:
                            print(f"    ⚠️ Twig integration failed: {e}")

                    stats["total_exported"] += 1

            stats["species_processed"] += 1

        except Exception as e:
            print(f"  ❌ Error processing {species_name}: {e}")
            continue

    return stats


def generate_grove_wind_animation(
    forest: list, output_dir: Path, config: GrowPyConfig
) -> bool:
    """Generate wind animation using Grove's animation system.

    Args:
        forest: List of (grove, species_name, tree_count, attributes) tuples
        output_dir: Output directory for animation files
        config: GrowPy configuration

    Returns:
        bool: True if wind animation was generated successfully
    """
    if not GROVE_CORE_AVAILABLE:
        print("⚠️ Grove core not available for wind animation")
        return False

    print("💨 Generating Grove wind animation...")

    wind_dir = output_dir / "wind_animation"
    wind_dir.mkdir(parents=True, exist_ok=True)

    # Wind parameters
    wind_vector = (1.0, 0.5, 0.0)  # Wind direction
    frame_count = 60  # Animation frames
    turbulence = 1.5  # Wind strength

    try:
        for grove, species_name, tree_count, attributes in forest:
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
    """Main function demonstrating comprehensive Grove API usage."""
    print("🚀 Enhanced Grove Forest Generation")
    print("=" * 50)

    # Configuration
    config = GrowPyConfig(
        random_seed=42,
        output_dir=Path("output/grove_enhanced_forest"),
        lod_levels=["lod0", "lod1", "lod2", "skeletal"],
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
        # Create enhanced forest
        forest = create_enhanced_grove_forest(input_csv, config)

        # Simulate with comprehensive Grove features
        simulate_grove_forest_with_comprehensive_features(
            forest, cycles=25, config=config
        )

        # Export with full Grove feature set
        stats = export_grove_forest_with_full_features(
            forest, config.output_dir, config
        )

        # Generate wind animation
        wind_success = generate_grove_wind_animation(forest, config.output_dir, config)

        # Print comprehensive statistics
        print(f"\n🎉 Grove Forest Generation Complete!")
        print(f"📊 Export Statistics:")
        print(f"  • Species processed: {stats['species_processed']}")
        print(f"  • Models exported: {stats['total_exported']}")
        print(f"  • Skeletons created: {stats['skeletons_created']}")
        print(f"  • Models with twigs: {stats['models_with_twigs']}")
        print(f"  • Total attributes: {stats['total_attributes']}")
        print(f"  • Wind animation: {'✅' if wind_success else '❌'}")
        print(f"📁 Output directory: {config.output_dir}")

        return 0

    except Exception as e:
        print(f"❌ Forest generation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
