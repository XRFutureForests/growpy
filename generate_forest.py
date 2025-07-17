#!/usr/bin/env python3
"""
Main script for generating tree models from demo forest data.

This script uses the growpy module to:
1. Load forest data from CSV (demo_forest.csv with columns: x, y, z, species, height)
2. Generate height curves and age prediction models for each species
3. Predict tree ages based on height and species
4. Simulate tree growth with light competition
5. Export models in various formats (JSON, USD, FBX)

Input Requirements:
- demo_forest.csv must contain columns: x, y, z, species, height
- No age column needed - ages are predicted from heights automatically
"""

import sys
from pathlib import Path


def main():
    """Generate forest models from demo data."""
    # Add src to path for imports
    src_path = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_path))

    # Import after path setup
    from growpy.config import GrowPyConfig
    from growpy.exporters import (
        ModelFormat,
        export_grove_json_files,
        export_individual_tree_models,
    )
    from growpy.simulation import add_trees, grow_forest

    print("🌲 Grove Forest Generator")
    print("=" * 50)

    # Setup paths
    data_dir = Path(__file__).parent / "data"
    input_dir = data_dir / "input"
    output_dir = data_dir / "output"
    csv_path = input_dir / "demo_forest.csv"
    config_path = Path(__file__).parent / "config.ini"

    if not csv_path.exists():
        print(f"❌ Error: Could not find {csv_path}")
        print("   Make sure the demo forest CSV file exists in the input folder.")
        return 1

    # Get input name for organized output structure
    input_name = csv_path.stem  # "demo_forest"

    # Configure simulation - try to load from config.ini, fallback to defaults
    if config_path.exists():
        print(f"📋 Loading configuration from {config_path}")
        try:
            config = GrowPyConfig.from_config_file(config_path)
            print("   ✅ Configuration loaded successfully")
        except Exception as e:
            print(f"   ⚠️  Warning: Could not load config file ({e})")
            print("   Using default configuration")
            config = GrowPyConfig()
    else:
        print("📋 Using default configuration (no config.ini found)")
        config = GrowPyConfig()
        # Create a sample config.ini file for user reference
        try:
            config.to_config_file(config_path)
            print(f"   📄 Created sample config.ini at {config_path}")
        except Exception as e:
            print(f"   ⚠️  Could not create sample config.ini: {e}")

    config.output_dir = output_dir

    print(f"📁 Input:  {csv_path}")
    print(f"📁 Output: {output_dir}/{input_name}/")
    print()

    # Step 1: Load forest data and generate age predictions
    print("📊 Loading forest data and generating age predictions...")
    print("   This step will:")
    print("   • Load tree positions, species, and heights from CSV")
    print("   • Generate height curves for each species through simulation")
    print("   • Create linear regression models to predict age from height")
    print("   • Apply age predictions to all trees based on their heights")
    forest = []
    forest = add_trees(forest, csv_path, config)

    print(f"   Loaded {len(forest)} species:")
    for grove, species, tree_count in forest:
        print(f"   • {species}: {tree_count} trees")
    print()

    # Step 2: Simulate growth
    print("🌱 Simulating forest growth...")
    grow_forest(forest, config)
    print("   ✅ Growth simulation complete")
    print()

    # Step 3: Export models
    print("💾 Exporting forest data...")

    # Export grove JSON files for Blender import
    print("\n📄 Exporting grove JSON files...")
    export_grove_json_files(forest, output_dir, input_name)

    # Export individual tree USD models with LOD levels
    print("\n🌳 Exporting individual tree models as USD files...")
    lod_configs = GrowPyConfig.get_lod_configs()
    export_individual_tree_models(
        forest,
        output_dir,
        lod_configs,
        model_format=ModelFormat.USD,
        input_name=input_name,
    )

    # Step 4: Export as FBX using integrated functionality (optional)
    print("\n🔄 Exporting individual tree models as FBX files...")
    export_individual_tree_models(
        forest,
        output_dir,
        lod_configs,
        model_format=ModelFormat.FBX,
        input_name=input_name,
    )

    print("\n🎉 Forest generation complete!")
    print(f"   Check output directory: {output_dir}/{input_name}/")
    print("\n📁 Directory structure:")
    print(f"   {output_dir}/{input_name}/groves/           - JSON files for Blender")
    print(
        f"   {output_dir}/{input_name}/tree_models/      - USD and FBX models organized by species"
    )
    print(
        f"   {output_dir}/{input_name}/analysis/        - Height curves and age prediction data"
    )
    print("\n💡 Next steps:")
    print("   • Import JSON files into Blender for animation")
    print("   • Use USD files in game engines or 3D software")
    print("   • Use FBX files for Unity, Unreal Engine, or other game engines")
    print("   • Each species has its own subfolder with all model formats")

    return 0


if __name__ == "__main__":
    exit(main())
