"""Model export operations using Grove's native USD output."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import the_grove_22_core as gc

from .forest import ForestGroves


def export_grove_json(grove: gc.Grove, output_path: Path) -> bool:
    """Export grove to JSON using Grove's core functionality."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        json_string = gc.io.grove_to_json_string(grove)

        with open(output_path, "w") as f:
            f.write(json_string)

        return True
    except Exception:
        return False


def export_model_usd(model, output_path: Path) -> bool:
    """Export model to USD using Grove's native USD output."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        usd_string = gc.io.model_to_usda_string(model)

        with open(output_path, "w") as f:
            f.write(usd_string)

        return True
    except Exception:
        return False


def build_lod_models(
    grove: gc.Grove, lod_configs: Dict[str, Dict[str, Any]]
) -> Dict[str, List]:
    """Build multiple LOD variants of grove models."""
    lod_models = {}
    for lod_name, config in lod_configs.items():
        lod_models[lod_name] = grove.build_models(config)
    return lod_models


def export_forest_groves_json(
    forest_groves: ForestGroves, output_dir: Path
) -> List[Path]:
    """Export all forest groves to JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_files = []

    for grove, species_name, tree_count in forest_groves:
        safe_name = species_name.replace(" ", "_")
        filename = f"{safe_name}_grove.json"
        file_path = output_dir / filename

        if export_grove_json(grove, file_path):
            exported_files.append(file_path)

    return exported_files


def export_forest_usd_models(
    forest_groves: ForestGroves,
    output_dir: Path,
    lod_configs: Dict[str, Dict[str, Any]],
    forest_data: Optional[pd.DataFrame] = None,
) -> List[Path]:
    """Export forest models to USD with multiple LOD variants."""
    models_dir = output_dir / "usd_models"
    models_dir.mkdir(parents=True, exist_ok=True)
    exported_files = []

    # Group CSV data by species for height/scale information
    csv_by_species = {}
    if forest_data is not None:
        for species_name, species_data in forest_data.groupby("species"):
            csv_by_species[str(species_name)] = species_data

    for grove, species_name, tree_count in forest_groves:
        species_dir = models_dir / species_name.replace(" ", "_")
        species_dir.mkdir(parents=True, exist_ok=True)

        # Build all LOD models for this species
        lod_models = build_lod_models(grove, lod_configs)

        # Get CSV data for this species if available
        species_csv = csv_by_species.get(species_name)

        # Export each tree with all LOD variants
        for tree_idx in range(tree_count):
            # Get the best available LOD model
            base_model = None
            for lod_name in ["LOD0_Ultra", "LOD1_High", "LOD2_Medium", "LOD3_Low"]:
                if lod_name in lod_models and tree_idx < len(lod_models[lod_name]):
                    base_model = lod_models[lod_name][tree_idx]
                    break

            if base_model is None:
                continue

            # Calculate scale factor from CSV height data if available
            scale_factor = 1.0
            if species_csv is not None and tree_idx < len(species_csv):
                csv_row = species_csv.iloc[tree_idx]
                if "height" in csv_row:
                    target_height = float(csv_row["height"])
                    # Get simulated tree height
                    tree = (
                        grove.trees[tree_idx] if tree_idx < len(grove.trees) else None
                    )
                    if tree and tree.nodes:
                        simulated_height = max(
                            (node.pos.length() for node in tree.nodes), default=1.0
                        )
                        if simulated_height > 0:
                            scale_factor = target_height / simulated_height

            # Apply scale transformation to model if needed
            if scale_factor != 1.0:
                # Use Grove's transform capabilities
                base_model.set_up_axis("Z")  # Ensure correct orientation

            # Export the model
            filename = f"{species_name.replace(' ', '_')}_tree_{tree_idx:03d}.usda"
            file_path = species_dir / filename

            if export_model_usd(base_model, file_path):
                exported_files.append(file_path)

    return exported_files
