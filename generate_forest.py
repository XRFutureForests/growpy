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

import logging
import sys
from pathlib import Path


def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("forest_generation.log"),
        ],
    )


def check_analysis_files_exist(output_dir, input_name):
    """Check if analysis files already exist."""
    analysis_dir = output_dir / input_name / "analysis"
    required_files = [
        "height_curves.csv",
        "height_to_cycle_models.pkl",
        f"{input_name}_with_predicted_cycles.csv",
    ]
    return all((analysis_dir / file).exists() for file in required_files)


def check_grove_files_exist(output_dir, input_name, forest):
    """Check if grove JSON files already exist."""
    groves_dir = output_dir / input_name / "groves"
    if not groves_dir.exists():
        return False

    # Check if all species have JSON files
    for _, species, _ in forest:
        species_file = (
            groves_dir / f"{species.replace(' - ', '_').replace(' ', '_')}_grove.json"
        )
        if not species_file.exists():
            return False
    return True


def check_tree_models_exist(output_dir, input_name, forest, lod_configs, model_format):
    """Check if tree model files already exist."""
    tree_models_dir = output_dir / input_name / "tree_models"
    if not tree_models_dir.exists():
        return False

    # Check if all species have model files for all LOD levels
    for _, species, _ in forest:
        species_dir = tree_models_dir / species.replace(" - ", "_").replace(" ", "_")
        if not species_dir.exists():
            return False

        # Check each LOD level
        for lod_name in lod_configs.keys():
            extension = "usd" if model_format.name == "USD" else "fbx"
            model_file = (
                species_dir
                / f"{species.replace(' - ', '_').replace(' ', '_')}_tree_000_{lod_name}.{extension}"
            )
            if not model_file.exists():
                return False
    return True


def check_all_outputs_exist(output_dir, input_name, lod_configs):
    """Check if all output files exist (analysis, groves, USD, FBX)."""
    # Check analysis files
    analysis_dir = output_dir / input_name / "analysis"
    required_files = [
        "height_curves.csv",
        "height_to_cycle_models.pkl",
        f"{input_name}_with_predicted_cycles.csv",
    ]
    if not all((analysis_dir / file).exists() for file in required_files):
        return False

    # Check grove files exist (we need to load forest to check species)
    groves_dir = output_dir / input_name / "groves"
    if not groves_dir.exists() or not any(groves_dir.glob("*_grove.json")):
        return False

    # Check USD files exist
    tree_models_dir = output_dir / input_name / "tree_models"
    if not tree_models_dir.exists():
        return False

    # Check if at least some model files exist
    for species_dir in tree_models_dir.iterdir():
        if species_dir.is_dir():
            # Check if we have both USD and FBX files
            usd_files = list(species_dir.glob("*.usd"))
            fbx_files = list(species_dir.glob("*.fbx"))
            if len(usd_files) < len(lod_configs) or len(fbx_files) == 0:
                return False

    return True


def main():
    """Generate forest models from demo data."""
    setup_logging()
    logger = logging.getLogger(__name__)

    # Add src to path for imports
    src_path = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_path))

    # Import after path setup
    import pandas as pd

    from growpy.config import GrowPyConfig
    from growpy.data.loader import load_and_validate_csv
    from growpy.exporters import (
        ModelFormat,
        export_grove_json_files,
        export_individual_tree_models,
    )
    from growpy.grove.grove_creation import create_groves_from_data
    from growpy.grove.simulation import simulate_forest_growth
    from growpy.modeling.height_curves import generate_height_curves
    from growpy.modeling.models import (
        add_predicted_cycles_to_data,
        create_cycle_prediction_models,
    )

    logger.info("Starting Grove Forest Generator")

    # Setup paths
    data_dir = Path(__file__).parent / "data"
    input_dir = data_dir / "input"
    output_dir = data_dir / "output"
    csv_path = input_dir / "demo_forest.csv"
    config_path = Path(__file__).parent / "config.ini"

    if not csv_path.exists():
        logger.error(f"Could not find {csv_path}")
        logger.error("Make sure the demo forest CSV file exists in the input folder.")
        return 1

    # Get input name for organized output structure
    input_name = csv_path.stem  # "demo_forest"

    # Configure simulation - try to load from config.ini, fallback to defaults
    if config_path.exists():
        logger.info(f"Loading configuration from {config_path}")
        try:
            config = GrowPyConfig.from_config_file(config_path)
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load config file ({e})")
            logger.info("Using default configuration")
            config = GrowPyConfig()
    else:
        logger.info("Using default configuration (no config.ini found)")
        config = GrowPyConfig()
        # Create a sample config.ini file for user reference
        try:
            config.to_config_file(config_path)
            logger.info(f"Created sample config.ini at {config_path}")
        except Exception as e:
            logger.warning(f"Could not create sample config.ini: {e}")

    config.output_dir = output_dir

    logger.info(f"Input:  {csv_path}")
    logger.info(f"Output: {output_dir}/{input_name}/")

    # Quick check if all outputs already exist
    lod_configs = config.get_selected_lod_configs()
    if check_all_outputs_exist(output_dir, input_name, lod_configs):
        logger.info("All output files already exist. Forest generation is complete!")
        logger.info(f"Check output directory: {output_dir}/{input_name}/")
        return 0

    # Step 1: Load forest data and generate age predictions
    if check_analysis_files_exist(output_dir, input_name):
        logger.info(
            "Analysis files already exist, skipping forest data loading and age prediction"
        )
        # Load existing enhanced data
        enhanced_csv_path = (
            output_dir
            / input_name
            / "analysis"
            / f"{input_name}_with_predicted_cycles.csv"
        )
        if not enhanced_csv_path.exists():
            logger.error(f"Enhanced CSV file not found: {enhanced_csv_path}")
            return 1
        enhanced_data = pd.read_csv(enhanced_csv_path)
        growth_cycles = int(enhanced_data["required_cycles"].max()) + 1
        forest = create_groves_from_data(enhanced_data, growth_cycles, config)
        logger.info(f"Loaded {len(forest)} species for export steps")
    else:
        logger.info("Loading forest data and generating age predictions...")
        # Step 1: Load and validate CSV data
        data = load_and_validate_csv(csv_path)
        # Step 2: Generate height curves
        species_list = data["species"].unique().tolist()
        input_output_dir = output_dir / input_name / "analysis"
        input_output_dir.mkdir(parents=True, exist_ok=True)
        height_curves = generate_height_curves(species_list, config, input_output_dir)
        # Step 3: Create prediction models
        models = create_cycle_prediction_models(height_curves, input_output_dir)
        # Step 4: Create enhanced data with growth cycle predictions
        enhanced_data = add_predicted_cycles_to_data(data, models)
        enhanced_csv_path = input_output_dir / f"{input_name}_with_predicted_cycles.csv"
        enhanced_data.to_csv(enhanced_csv_path, index=False)
        growth_cycles = int(enhanced_data["required_cycles"].max()) + 1
        # Step 5: Create grove objects
        forest = create_groves_from_data(enhanced_data, growth_cycles, config)
        logger.info(f"Loaded {len(forest)} species:")
        for _, species, tree_count in forest:
            logger.info(f"  • {species}: {tree_count} trees")
        logger.info(f"Growth cycles required: {growth_cycles}")
        # Step 6: Simulate growth
        logger.info("Simulating forest growth...")
        simulate_forest_growth(forest, config, growth_cycles)
        logger.info("Growth simulation complete")

    # Step 3: Export models
    logger.info("Starting export process...")

    # Export grove JSON files for Blender import
    if check_grove_files_exist(output_dir, input_name, forest):
        logger.info("Grove JSON files already exist, skipping export")
    else:
        logger.info("Exporting grove JSON files...")
        export_grove_json_files(forest, output_dir, input_name)
        logger.info("Grove JSON export complete")

    # Export individual tree USD models with selected LOD levels
    logger.info(f"Using LOD levels: {list(lod_configs.keys())}")

    if check_tree_models_exist(
        output_dir, input_name, forest, lod_configs, ModelFormat.USD
    ):
        logger.info("USD tree models already exist, skipping export")
    else:
        logger.info("Exporting individual tree models as USD files...")
        export_individual_tree_models(
            forest,
            output_dir,
            lod_configs,
            model_format=ModelFormat.USD,
            input_name=input_name,
        )
        logger.info("USD export complete")

    # Step 4: Export as FBX using integrated functionality (optional)
    if check_tree_models_exist(
        output_dir, input_name, forest, lod_configs, ModelFormat.FBX
    ):
        logger.info("FBX tree models already exist, skipping export")
    else:
        logger.info("Exporting individual tree models as FBX files...")
        export_individual_tree_models(
            forest,
            output_dir,
            lod_configs,
            model_format=ModelFormat.FBX,
            input_name=input_name,
        )
        logger.info("FBX export complete")

    logger.info("Forest generation complete!")
    logger.info(f"Check output directory: {output_dir}/{input_name}/")
    logger.info("Directory structure:")
    logger.info(
        f"  {output_dir}/{input_name}/groves/           - JSON files for Blender"
    )
    logger.info(
        f"  {output_dir}/{input_name}/tree_models/      - USD and FBX models organized by species"
    )
    logger.info(
        f"  {output_dir}/{input_name}/analysis/        - Height curves and age prediction data"
    )

    return 0


if __name__ == "__main__":
    exit(main())
