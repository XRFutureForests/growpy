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

        denominator = 1.0 - grow_length_reduce
        fraction = target_height * denominator / grow_length

        # Check if the target height is achievable with this formula
        if fraction >= 1.0:
            # Height is at or beyond the theoretical maximum for this species
            # Use a large number of flushes
            estimated_flushes = max(50, int(target_height / grow_length))
        else:
            inner_log_arg = 1.0 - fraction
            if inner_log_arg <= 0:
                estimated_flushes = max(50, int(target_height / grow_length))
            else:
                estimated_flushes = int(
                    math.log(inner_log_arg) / math.log(grow_length_reduce)
                )

    # Ensure reasonable bounds (limit to smaller numbers for faster testing)
    estimated_flushes = max(5, min(20, estimated_flushes))

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

    # Create separate groves for each species (proper "grow together" approach)
    print("Creating species-specific groves...")

    # Group trees by species
    species_groups = trees_data.groupby("species")
    list_of_groves = []
    grove_species_map = {}

    for species, group_data in species_groups:
        print(f"Creating grove for species: {species} ({len(group_data)} trees)")

        # Create grove for this species
        grove = tg.Grove()

        # Load and apply species-specific preset
        species_preset = _load_species_preset(str(species))
        if species_preset:
            props = grove.get_properties()

            for key, value in species_preset.items():
                if isinstance(value, (int, float, bool)):
                    try:
                        setattr(props, key, value)
                    except (AttributeError, TypeError):
                        pass

            grove.set_properties(props)
            print(f"Applied {species} preset to grove")

        # Find max flushes needed for this species
        max_flushes_species = int(group_data["calculated_flushes"].max())

        # Add trees of this species to their grove
        for index, row in group_data.iterrows():
            x, y, z = float(row["x"]), float(row["y"]), float(row["z"])
            position = tg.Vector(x, y, z)
            direction = tg.Vector(0.0, 0.0, 1.0)

            required_flushes = int(row["calculated_flushes"])
            delay = max_flushes_species - required_flushes

            grove.add_new_tree(position, direction, delay)

            print(f"Added {species} tree at ({x}, {y}, {z}) with delay {delay}")

        list_of_groves.append(grove)
        grove_species_map[len(list_of_groves) - 1] = species

    # Calculate total simulation flushes needed across all species
    max_flushes = int(trees_data["calculated_flushes"].max())

    print(
        f"\nGrowing {len(list_of_groves)} groves together for {max_flushes} flushes..."
    )

    # Grow all groves together with shared light environment
    for flush_num in range(max_flushes):
        print(f"Simulating flush {flush_num + 1}/{max_flushes}")

        # Collect shade geometry from all groves
        coords = []
        for grove in list_of_groves:
            coords.extend(grove.create_shade_geometry_coords())

        # Calculate shade and simulate each grove
        for i, grove in enumerate(list_of_groves):
            grove.calculate_shade_together(coords)
            grove.simulate(1)

    print(
        f"Simulation complete! All {len(list_of_groves)} species groves grown together."
    )

    # Build 3D models from all groves
    print("\nBuilding 3D models...")

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Build options for model generation
    build_options = {
        "resolution": resolution,
        "reduce": 0.8,  # Reduce geometry complexity on thinner branches
        "texture_repeat": 3,  # Bark texture repetitions
        "build_end_cap": True,  # Close branch ends
        "build_blend": True,  # Smooth branch transitions
    }

    # Collect all models from all groves
    all_points = []
    all_faces = []
    all_uvs = []
    vertex_offset = 0

    for grove_index, grove in enumerate(list_of_groves):
        species = grove_species_map[grove_index]
        print(f"Building models for {species} grove...")

        # Build model for this grove
        model = grove.build_as_one_model(build_options)

        # Add this grove's geometry to the combined model
        grove_points = model.points
        grove_faces = model.faces
        grove_uvs = model.uvs

        # Add points (vertices)
        all_points.extend(grove_points)

        # Add faces with adjusted vertex indices
        for face in grove_faces:
            adjusted_face = [vertex_index + vertex_offset for vertex_index in face]
            all_faces.append(adjusted_face)

        # Add UV coordinates
        all_uvs.extend(grove_uvs)

        # Update vertex offset for next grove
        vertex_offset += len(grove_points)

        print(
            f"Added {len(grove_points)} vertices and {len(grove_faces)} faces from {species}"
        )

    # Write combined OBJ file
    print(f"\nExporting combined forest to {output_file}...")

    with open(output_file, "w") as obj_file:
        # Write header
        obj_file.write("# Forest model generated by GrowPy\n")
        obj_file.write(
            f"# Contains {len(list_of_groves)} species: {list(grove_species_map.values())}\n"
        )
        obj_file.write(
            f"# Total vertices: {len(all_points)}, Total faces: {len(all_faces)}\n\n"
        )

        # Write vertices
        for point in all_points:
            obj_file.write(f"v {point.x:.6f} {point.y:.6f} {point.z:.6f}\n")

        # Write UV coordinates if available
        if all_uvs:
            obj_file.write("\n")
            for uv in all_uvs:
                # UV coordinates might be tuples or Vector objects
                if hasattr(uv, "x"):
                    obj_file.write(f"vt {uv.x:.6f} {uv.y:.6f}\n")
                else:
                    obj_file.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

        # Write faces
        obj_file.write("\n")
        for face in all_faces:
            if all_uvs:
                # Include UV indices if UVs are available
                face_str = " ".join([f"{v}/{v}" for v in face])
            else:
                # Vertex indices only
                face_str = " ".join([str(v) for v in face])
            obj_file.write(f"f {face_str}\n")

    print(f"Successfully exported forest model to {output_file}")
    print(f"Model contains {len(all_points)} vertices and {len(all_faces)} faces")
    print(f"Species included: {list(grove_species_map.values())}")

    return str(output_file)


if __name__ == "__main__":
    # Example usage - for full demo run: python growpy_demo.py
    demo_csv = current_dir.parent / "data" / "demo_forest.csv"

    combined_output = Path("../data/output/combined_forest.obj")

    combined_file = grow_forest_from_csv(
        csv_file=demo_csv,
        output_file=combined_output,
        resolution=10,  # Reduced from 16 for faster generation
    )
