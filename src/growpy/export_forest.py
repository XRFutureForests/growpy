"""
Export module for The Grove forest data.

This module provides functions to export forest data in various formats:
- Grove JSON files for Blender import
- 3D models as OBJ or USD files
- Individual tree models or combined grove models
"""

from enum import Enum
from pathlib import Path
from typing import List, Tuple

import the_grove_22_core as gc
from config import GrowPyConfig
from tqdm import tqdm


class ModelFormat(Enum):
    """Supported 3D model formats for export."""

    OBJ = "obj"
    USD = "usd"


def export_grove_json(
    forest: List[Tuple[gc.Grove, str, int]], output_dir: Path
) -> List[Path]:
    """
    Export grove simulation data as JSON files for Blender import.

    Args:
        forest: List of (grove, species_name, tree_count) tuples
        output_dir: Directory to save JSON files

    Returns:
        List of paths to exported JSON files
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_files = []

    for grove, species, tree_count in tqdm(
        forest, desc="Exporting grove JSON", unit="species"
    ):
        species_clean = species.replace(" ", "_").replace("-", "_")
        grove_json = gc.io.grove_to_json_string(grove)
        grove_file_path = output_dir / f"{species_clean}_grove.json"

        with open(grove_file_path, "w") as f:
            f.write(grove_json)

        print(
            f"Exported grove data for {tree_count} {species} trees: {grove_file_path}"
        )
        exported_files.append(grove_file_path)

    return exported_files


def export_grove_models(
    forest: List[Tuple[gc.Grove, str, int]],
    output_dir: Path,
    lod_configs: dict | None = None,
    model_format: ModelFormat = ModelFormat.OBJ,
) -> List[Path]:
    """
    Export grove models (one model per grove, all trees combined).

    Args:
        forest: List of (grove, species_name, tree_count) tuples
        output_dir: Directory to save model files
        lod_configs: Dictionary of LOD configurations. If None, uses default config
        model_format: Format to export models (OBJ or USD)

    Returns:
        List of paths to exported model files
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_files = []

    # Use default LOD configs if none provided
    if lod_configs is None:
        lod_configs = GrowPyConfig.get_lod_configs()

    for grove, species, tree_count in tqdm(
        forest, desc="Exporting grove models", unit="species"
    ):
        species_clean = species.replace(" ", "_").replace("-", "_")

        # Export each LOD level for this species
        for lod_name, lod_settings in tqdm(
            lod_configs.items(),
            desc=f"Exporting LODs for {species}",
            unit="LOD",
            leave=False,
        ):
            # Build model with LOD settings
            model = grove.build_as_one_model(lod_settings)

            # Generate filename with LOD suffix and format
            filename = f"{species_clean}_{lod_name}.{model_format.value}"
            file_path = output_dir / filename

            # Export model in specified format
            _export_model_file(model, file_path, model_format)
            exported_files.append(file_path)

    return exported_files


def export_individual_tree_models(
    forest: List[Tuple[gc.Grove, str, int]],
    output_dir: Path,
    build_options: dict | None = None,
    model_format: ModelFormat = ModelFormat.OBJ,
) -> List[Path]:
    """
    Export individual tree models (one model per tree).

    Args:
        forest: List of (grove, species_name, tree_count) tuples
        output_dir: Directory to save model files
        build_options: Build options for model generation. If None, uses defaults
        model_format: Format to export models (OBJ or USD)

    Returns:
        List of paths to exported model files
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_files = []

    # Use default build options if none provided
    if build_options is None:
        build_options = {
            "resolution": 16,
            "resolution_reduce": 0.8,
            "texture_repeat": 3,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.0,
            "build_blend": True,
            "build_end_cap": True,
        }

    for grove, species, tree_count in tqdm(
        forest, desc="Exporting individual trees", unit="species"
    ):
        species_clean = species.replace(" ", "_").replace("-", "_")

        # Build individual tree models
        models = grove.build_models(build_options)

        for i, model in enumerate(
            tqdm(models, desc=f"Exporting {species} trees", unit="tree", leave=False)
        ):
            filename = f"{species_clean}_tree_{i:03d}.{model_format.value}"
            file_path = output_dir / filename

            # Export model in specified format
            _export_model_file(model, file_path, model_format)
            exported_files.append(file_path)

    return exported_files


def export_complete_forest(
    forest: List[Tuple[gc.Grove, str, int]],
    config: GrowPyConfig,
    include_json: bool = True,
    include_grove_models: bool = True,
    include_individual_trees: bool = False,
    model_format: ModelFormat = ModelFormat.OBJ,
) -> dict:
    """
    Export complete forest data including JSON and 3D models.

    Args:
        forest: List of (grove, species_name, tree_count) tuples
        config: Configuration object with output directory and LOD settings
        include_json: Whether to export grove JSON files
        include_grove_models: Whether to export grove models (one per species)
        include_individual_trees: Whether to export individual tree models
        model_format: Format for 3D models (OBJ or USD)

    Returns:
        Dictionary with lists of exported file paths by type
    """
    config.output_dir.mkdir(parents=True, exist_ok=True)
    exported_files = {"json": [], "grove_models": [], "individual_trees": []}

    # Export grove JSON files
    if include_json:
        exported_files["json"] = export_grove_json(forest, config.output_dir)

    # Export grove models with LOD levels
    if include_grove_models:
        lod_configs = GrowPyConfig.get_lod_configs()
        exported_files["grove_models"] = export_grove_models(
            forest, config.output_dir, lod_configs, model_format
        )

    # Export individual tree models
    if include_individual_trees:
        build_options = config.to_grove_build_options()
        exported_files["individual_trees"] = export_individual_tree_models(
            forest, config.output_dir, build_options, model_format
        )

    # Print summary
    _print_export_summary(exported_files, model_format)

    return exported_files


def _export_model_file(model, file_path: Path, model_format: ModelFormat) -> None:
    """
    Export a single model to file in the specified format.

    Args:
        model: The Grove model to export
        file_path: Path where to save the file
        model_format: Format to export (OBJ or USD)
    """
    if model_format == ModelFormat.OBJ:
        model_string = gc.io.model_to_obj_string(model)
    elif model_format == ModelFormat.USD:
        model_string = gc.io.model_to_usda_string(model)
    else:
        raise ValueError(f"Unsupported model format: {model_format}")

    with open(file_path, "w") as f:
        f.write(model_string)


def _print_export_summary(exported_files: dict, model_format: ModelFormat) -> None:
    """Print a summary of exported files."""
    print("\n" + "=" * 80)
    print("EXPORT SUMMARY")
    print("=" * 80)

    if exported_files["json"]:
        print(f"Grove JSON files: {len(exported_files['json'])}")
        for file_path in exported_files["json"]:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"  • {file_path.name} ({file_size_mb:.1f} MB)")

    if exported_files["grove_models"]:
        print(
            f"\nGrove {model_format.value.upper()} models: {len(exported_files['grove_models'])}"
        )
        species_counts = {}
        for file_path in exported_files["grove_models"]:
            species = (
                file_path.stem.split("_LOD")[0]
                if "_LOD" in file_path.stem
                else file_path.stem
            )
            species_counts[species] = species_counts.get(species, 0) + 1
        for species, count in species_counts.items():
            print(f"  • {species}: {count} LOD levels")

    if exported_files["individual_trees"]:
        print(
            f"\nIndividual tree {model_format.value.upper()} models: {len(exported_files['individual_trees'])}"
        )
        species_counts = {}
        for file_path in exported_files["individual_trees"]:
            species = (
                file_path.stem.split("_tree_")[0]
                if "_tree_" in file_path.stem
                else file_path.stem
            )
            species_counts[species] = species_counts.get(species, 0) + 1
        for species, count in species_counts.items():
            print(f"  • {species}: {count} trees")

    # Print LOD configuration info if grove models were exported
    if exported_files["grove_models"]:
        print("\nLOD Configuration Summary:")
        print("-" * 80)
        print(
            f"{'Level':<12} {'Resolution':<10} {'Reduce':<8} {'Age Cut':<8} {'Thick Cut':<10} {'Blend':<6} {'End Cap':<8}"
        )
        print("-" * 80)

        lod_configs = GrowPyConfig.get_lod_configs()
        for lod_name, lod_settings in lod_configs.items():
            print(
                f"{lod_name:<12} {lod_settings['resolution']:<10} {lod_settings['resolution_reduce']:<8.2f} "
                f"{lod_settings['build_cutoff_age']:<8} {lod_settings['build_cutoff_thickness']:<10.2f} "
                f"{str(lod_settings['build_blend']):<6} {str(lod_settings['build_end_cap']):<8}"
            )

    print("=" * 80)
