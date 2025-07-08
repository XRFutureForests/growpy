"""
GrowPy - Main module for forest generation from CSV data

This module provides functionality to generate 3D tree models from CSV data
using The Grove 2.2 procedural tree generation system.
"""

import sys
import csv
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
import pandas as pd

# Add The Grove modules to Python path
current_dir = Path(__file__).parent.parent
grove_modules_path = current_dir / "the_grove_22" / "modules"
sys.path.insert(0, str(grove_modules_path))
import the_grove_22_core as tg


def list_available_species() -> List[str]:
    """
    List all available species presets.

    Returns:
        List of species names that can be used in CSV files
    """
    presets_dir = current_dir / "the_grove_22" / "presets"
    species_list = []

    if presets_dir.exists():
        for preset_file in presets_dir.glob("*.seed.json"):
            # Remove .seed from the filename to get clean species name
            species_name = preset_file.stem
            if species_name.endswith(".seed"):
                species_name = species_name[:-5]  # Remove '.seed' suffix
            species_list.append(species_name)

    return sorted(species_list)


def _load_species_preset(species_name: str) -> Optional[Dict]:
    """
    Load species preset data from JSON file.

    Args:
        species_name: Name of the species preset

    Returns:
        Dictionary with preset data or None if not found
    """
    presets_dir = current_dir / "the_grove_22" / "presets"
    preset_path = presets_dir / f"{species_name}.seed.json"

    if preset_path.exists():
        try:
            with open(preset_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load preset for {species_name}: {e}")
    else:
        print(f"Warning: Species preset not found: {species_name}")

    return None


def _estimate_flushes_for_height(target_height: float, preset_data: Dict) -> int:
    """
    Estimate the number of flushes required to reach the target height.

    Uses the geometric series formula based on grow_length and grow_length_reduce:
    height = grow_length × (1 - grow_length_reduce^n) / (1 - grow_length_reduce)

    Solving for n (flushes):
    n = log(1 - height×(1-grow_length_reduce)/grow_length) / log(grow_length_reduce)

    Args:
        target_height: Desired tree height in meters
        preset_data: Species preset parameters

    Returns:
        Estimated number of flushes needed
    """
    import math

    # Extract key growth parameters
    grow_length = preset_data.get("grow_length", 0.5)
    grow_length_reduce = preset_data.get("grow_length_reduce", 0.78)

    # Avoid division by zero and ensure valid parameters
    if grow_length_reduce >= 1.0 or grow_length_reduce <= 0.0:
        # If no reduction or invalid, use simple linear approach
        estimated_flushes = int(target_height / grow_length / 3)
    else:
        # Apply geometric series formula exactly as provided:
        # height = grow_length × (1 - grow_length_reduce^n) / (1 - grow_length_reduce)
        # Rearranging: n = log(1 - height×(1-grow_length_reduce)/grow_length) / log(grow_length_reduce)

        estimated_flushes = int(
            math.log(1 - (target_height * (1 - grow_length_reduce) / grow_length))
            / math.log(grow_length_reduce)
        )

    return estimated_flushes


def grow_forest_from_csv(
    csv_file: Union[str, Path],
    output_file: Union[str, Path] = "forest_scene.obj",
    resolution: int = 16,
) -> str:
    """
    Generate a single combined forest model from CSV data with height constraints.


    Args:
        csv_file: Path to CSV file with tree data (x,y,z,species,age,height)
        output_file: Path for the combined OBJ file
        resolution: Model resolution

    Returns:
        Path to the generated file

    """
    csv_file = Path(csv_file)
    output_file = Path(output_file)

    # Read all tree data
    trees_data = pd.read_csv(csv_file)

    # Check if all species in the CSV have corresponding presets
    unique_species = trees_data["species"].unique()
    missing_species = []
    available_species = list_available_species()

    for species in unique_species:
        if species not in available_species:
            missing_species.append(species)

    if missing_species:
        print(f"Warning: Missing presets for species: {missing_species}")
        print(f"Available species: {available_species}")
        raise ValueError(f"Missing presets for species: {missing_species}")

    # Load presets for each tree and calculate required flushes
    print("Loading species presets and calculating required flushes...")

    for index, row in trees_data.iterrows():
        species = row["species"]
        target_height = row["height"]

        # Load species preset
        preset_data = _load_species_preset(species)
        if preset_data is None:
            raise ValueError(f"Failed to load preset for species: {species}")

        # Calculate required flushes to reach target height
        required_flushes = _estimate_flushes_for_height(target_height, preset_data)

        # Store calculated flushes back in dataframe
        trees_data.at[index, "calculated_flushes"] = required_flushes

        print(
            f"Tree {index}: {species}, target height: {target_height}m, estimated flushes: {required_flushes}"
        )

    # Create single grove
    grove = tg.Grove()

    # Apply a representative species preset to the grove
    # Since Grove works with one set of properties, we'll use the most common species
    species_counts = trees_data["species"].value_counts()
    representative_species = str(species_counts.index[0])  # Most common species

    print(f"Applying preset from representative species: {representative_species}")
    representative_preset = _load_species_preset(representative_species)

    if representative_preset:
        # Apply preset using Grove's properties system
        props = grove.get_properties()

        for key, value in representative_preset.items():
            # Apply preset parameters to grove properties
            if isinstance(value, (int, float, bool)):
                try:
                    setattr(props, key, value)
                except (AttributeError, TypeError):
                    # Property might not exist or have wrong type, skip
                    pass

        # Set the modified properties back to the grove
        grove.set_properties(props)
        print(f"Applied {len(representative_preset)} preset parameters to grove")

    # Add each tree to the grove with position, direction, and delay
    print("Adding trees to grove...")

    # Find the maximum flushes needed to determine delays
    max_flushes = int(trees_data["calculated_flushes"].max())

    for index, row in trees_data.iterrows():
        # Get tree position from CSV (x, y, z coordinates)
        position = [float(row["x"]), float(row["y"]), float(row["z"])]

        # Set upward direction for tree growth
        direction = [0.0, 0.0, 1.0]  # Growing upward in Z direction

        # Calculate delay: trees that need more flushes should start earlier
        required_flushes = int(row["calculated_flushes"])
        delay = max_flushes - required_flushes

        # Add tree to grove
        grove.add_new_tree(position, direction, delay)

        species = row["species"]
        print(
            f"Added tree {index}: {species} at ({position[0]}, {position[1]}, {position[2]}) with delay {delay} (needs {required_flushes} flushes)"
        )

    print(
        f"Grove created with {len(trees_data)} trees. Maximum flushes needed: {max_flushes}"
    )
    print(f"Note: All trees use {representative_species} growth characteristics")

    return str(output_file)


if __name__ == "__main__":
    # Example usage - for full demo run: python growpy_demo.py
    demo_csv = current_dir.parent / "data" / "demo_forest.csv"

    combined_output = Path("../data/output/combined_forest.obj")

    combined_file = grow_forest_from_csv(
        csv_file=demo_csv,
        output_file=combined_output,
        resolution=5,  # Reduced from 16 for faster generation
    )
