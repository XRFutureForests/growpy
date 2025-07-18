"""
Export module for The Grove forest data.

This module provides functions to export forest data in various formats:
- Grove JSON files for Blender import
- 3D models as OBJ or USD files
- Individual tree models or combined grove models
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Tuple

import the_grove_22_core as gc
from tqdm import tqdm

from .config import GrowPyConfig

# Set up logging
logger = logging.getLogger(__name__)


class ExportError(Exception):
    """Exception raised when export operations fail."""
    pass


class ModelFormat(Enum):
    """Supported 3D model formats for export."""

    OBJ = "obj"
    USD = "usd"
    FBX = "fbx"  # Note: FBX is post-processed from USD/OBJ files


# Type aliases for better readability
ForestData = List[Tuple[gc.Grove, str, int]]
ExportedFiles = List[Path]
LodConfigs = Dict[str, Dict[str, Any]]


def export_grove_json_files(
    forest_data: ForestData, output_directory: Path, input_name: str = "demo_forest"
) -> ExportedFiles:
    """
    Export grove simulation data as JSON files for Blender import.

    Args:
        forest_data: List of (grove, species_name, tree_count) tuples
        output_directory: Directory to save JSON files
        input_name: Name of the input file (without extension) for subfolder organization

    Returns:
        List of paths to exported JSON files
    """
    # Create input-specific subfolder with groves subfolder
    input_output_dir = output_directory / input_name / "groves"
    _ensure_directory_exists(input_output_dir)
    exported_files = []

    for grove, species_name, tree_count in tqdm(
        forest_data, desc="Exporting grove JSON", unit="species"
    ):
        file_path = _create_grove_json_file(
            grove, species_name, tree_count, input_output_dir
        )
        exported_files.append(file_path)

    _print_json_export_summary(exported_files)
    return exported_files




def export_individual_tree_models(
    forest_data: ForestData,
    output_directory: Path,
    lod_configurations: LodConfigs | None = None,
    model_format: ModelFormat = ModelFormat.OBJ,
    input_name: str = "demo_forest",
) -> ExportedFiles:
    """
    Export individual tree models with LOD levels (one model per tree per LOD level).

    Args:
        forest_data: List of (grove, species_name, tree_count) tuples
        output_directory: Directory to save model files
        lod_configurations: Dictionary of LOD configurations. If None, uses defaults
        model_format: Format to export models (OBJ, USD, or FBX)
        input_name: Name of the input file (without extension) for subfolder organization

    Returns:
        List of paths to exported model files

    Note:
        FBX format requires post-processing and will first export as USD,
        then convert to FBX using Blender if available.
    """
    # Create input-specific subfolder with tree models subfolder
    input_output_dir = output_directory / input_name / "tree_models"
    _ensure_directory_exists(input_output_dir)

    # If FBX is requested, export as USD first, then convert
    if model_format == ModelFormat.FBX:
        # Export as USD first
        usd_files = _export_individual_trees_as_usd(
            forest_data,
            input_output_dir,
            lod_configurations or GrowPyConfig.get_lod_configs(),
        )

        # Convert to FBX
        fbx_files = _convert_usd_to_fbx(usd_files, input_output_dir, input_name)
        _print_individual_trees_summary(fbx_files, ModelFormat.FBX)
        return fbx_files

    # Standard export path for OBJ/USD
    exported_files = []
    lod_configs = lod_configurations or GrowPyConfig.get_lod_configs()

    for grove, species_name, _ in tqdm(
        forest_data, desc="Exporting individual trees", unit="species"
    ):
        species_files = _export_individual_trees_for_species(
            grove, species_name, lod_configs, input_output_dir, model_format
        )
        exported_files.extend(species_files)

    _print_individual_trees_summary(exported_files, model_format)
    return exported_files




# Private helper functions
def _ensure_directory_exists(directory_path: Path) -> None:
    """Ensure the target directory exists."""
    directory_path.mkdir(parents=True, exist_ok=True)


def _sanitize_species_name(species_name: str) -> str:
    """Convert species name to filesystem-safe format."""
    return species_name.replace(" ", "_").replace("_-_", "_")


def _create_grove_json_file(
    grove: gc.Grove, species_name: str, tree_count: int, output_directory: Path
) -> Path:
    """Create a single grove JSON file."""
    sanitized_name = _sanitize_species_name(species_name)
    grove_json_string = gc.io.grove_to_json_string(grove)
    file_path = output_directory / f"{sanitized_name}_grove.json"

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(grove_json_string)

    return file_path




def _export_individual_trees_for_species(
    grove: gc.Grove,
    species_name: str,
    lod_configs: LodConfigs,
    output_directory: Path,
    model_format: ModelFormat,
) -> ExportedFiles:
    """Export all individual trees for a single species with all LOD levels."""
    exported_files = []
    sanitized_name = _sanitize_species_name(species_name)

    # Create species-specific subfolder within tree_models
    species_output_dir = output_directory / sanitized_name
    _ensure_directory_exists(species_output_dir)

    for lod_name, lod_settings in tqdm(
        lod_configs.items(),
        desc=f"Exporting LODs for {species_name} trees",
        unit="LOD",
        leave=False,
    ):
        individual_models = grove.build_models(lod_settings)

        for tree_index, model in enumerate(individual_models):
            filename = f"{sanitized_name}_tree_{tree_index:03d}_{lod_name}.{model_format.value}"
            file_path = species_output_dir / filename

            _write_model_to_file(model, file_path, model_format)
            exported_files.append(file_path)

    return exported_files


def _write_model_to_file(model, file_path: Path, model_format: ModelFormat) -> None:
    """Write a single model to file in the specified format."""
    if model_format == ModelFormat.OBJ:
        model_string = gc.io.model_to_obj_string(model)
    elif model_format == ModelFormat.USD:
        model_string = gc.io.model_to_usda_string(model)
    elif model_format == ModelFormat.FBX:
        # FBX format is handled through post-processing, should not reach here
        raise ValueError(
            "FBX format requires post-processing and should be handled at a higher level"
        )
    else:
        raise ValueError(f"Unsupported model format: {model_format}")

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(model_string)


def _calculate_total_file_size_mb(file_paths: ExportedFiles) -> float:
    """Calculate total file size in MB for a list of files."""
    return sum(file_path.stat().st_size for file_path in file_paths) / (1024 * 1024)


def _print_json_export_summary(exported_files: ExportedFiles) -> Dict[str, Any]:
    """Create summary data for JSON export."""
    if not exported_files:
        return {"error": "No files were exported"}

    total_size_mb = _calculate_total_file_size_mb(exported_files)
    return {"files_exported": len(exported_files), "total_size_mb": total_size_mb}




def _print_individual_trees_summary(
    exported_files: ExportedFiles, model_format: ModelFormat
) -> Dict[str, Any]:
    """Create summary data for individual trees export."""
    if not exported_files:
        return {"error": "No files were exported"}

    species_counts = _count_species_and_trees(exported_files)
    num_lod_levels = len(GrowPyConfig.get_lod_configs())

    species_tree_counts = {}
    for species, total_files in species_counts.items():
        tree_count = (
            total_files // num_lod_levels if num_lod_levels > 0 else total_files
        )
        species_tree_counts[species] = {
            "tree_count": tree_count,
            "lod_levels": num_lod_levels,
        }

    return {
        "files_exported": len(exported_files),
        "model_format": model_format.value.upper(),
        "species_count": len(species_counts),
        "species_tree_counts": species_tree_counts,
        "lod_config": GrowPyConfig.get_lod_configs(),
    }


def _count_species_and_lods(
    file_paths: ExportedFiles, separator: str
) -> Dict[str, int]:
    """Count LOD levels per species."""
    species_counts = {}
    for file_path in file_paths:
        species = (
            file_path.stem.split(separator)[0]
            if separator in file_path.stem
            else file_path.stem
        )
        species_counts[species] = species_counts.get(species, 0) + 1
    return species_counts


def _count_species_and_trees(file_paths: ExportedFiles) -> Dict[str, int]:
    """Count total files per species for individual trees."""
    species_counts = {}
    for file_path in file_paths:
        if "_tree_" in file_path.stem:
            species = file_path.stem.split("_tree_")[0]
            species_counts[species] = species_counts.get(species, 0) + 1
    return species_counts




def _export_individual_trees_as_usd(
    forest_data: ForestData,
    output_directory: Path,
    lod_configs: LodConfigs,
) -> ExportedFiles:
    """Export individual trees as USD files (helper for FBX conversion)."""
    exported_files = []

    for grove, species_name, _ in tqdm(
        forest_data, desc="Exporting USD for FBX conversion", unit="species"
    ):
        species_files = _export_individual_trees_for_species(
            grove, species_name, lod_configs, output_directory, ModelFormat.USD
        )
        exported_files.extend(species_files)

    return exported_files


def _convert_usd_to_fbx(
    usd_files: ExportedFiles, output_directory: Path, input_name: str = "demo_forest"
) -> ExportedFiles:
    """
    Convert USD files to FBX format using the FBX module.
    FBX files are placed in the same species-specific subfolders as USD files.

    Args:
        usd_files: List of USD file paths to convert
        output_directory: Base output directory (should be tree_models subdirectory)
        input_name: Name of the input file for FBX subfolder organization

    Returns:
        List of FBX file paths created
    """
    try:
        from .config import GrowPyConfig
        from .fbx import LODCombiner

        # Group USD files by species (they're already in species subfolders)
        species_groups = {}
        for usd_file in usd_files:
            # Extract species name from path: tree_models/Species_Name/file.usd
            species_dir = usd_file.parent
            species_name = species_dir.name

            if species_name not in species_groups:
                species_groups[species_name] = []
            species_groups[species_name].append(usd_file)

        fbx_files = []

        # Convert each species separately and place FBX files in the same species folders
        for species_name, species_usd_files in species_groups.items():
            species_input_dir = output_directory / species_name

            try:
                # Create LOD combiner for this species
                lod_combiner = LODCombiner(
                    input_dir=species_input_dir,
                    output_dir=species_input_dir,  # Output to same directory as USD files
                )

                # Convert this species' USD files to FBX
                lod_combiner.combine_all_lods()

                # Collect FBX files created for this species
                if species_input_dir.exists():
                    species_fbx_files = list(species_input_dir.glob("*.fbx"))
                    fbx_files.extend(species_fbx_files)
                    logger.info(f"Successfully converted {len(species_fbx_files)} FBX files for {species_name}")
                else:
                    logger.warning(f"No FBX files found for {species_name} after conversion")
                    
            except Exception as e:
                logger.error(f"Failed to convert USD to FBX for species {species_name}: {e}")
                continue

        return fbx_files

    except ImportError as e:
        logger.error(f"FBX conversion not available: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error during FBX conversion: {e}")
        return []
