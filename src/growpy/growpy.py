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
    output_directory: Union[str, Path] = "forest_output",
    resolution: int = 16,
    flushes: int = 10,
    base_name: str = "forest",
    # Build options
    reduce: float = 0.8,
    texture_repeat: int = 3,
    build_end_cap: bool = True,
    build_blend: bool = True,
    build_cutoff_age: int = 0,
    build_cutoff_thickness: float = 0.0,
) -> str:
    """
    Generate individual tree models from CSV data.

    Args:
        csv_file: Path to CSV file with tree data (x,y,z,species,age,height)
        output_directory: Directory where individual tree OBJ files will be saved
        resolution: Model resolution (higher = more detail)
        flushes: Number of growth flushes to simulate for all trees
        base_name: Base name for generated files (default: "forest")
        
        # Build options (control tree geometry generation):
        reduce: Reduce geometry complexity on thinner branches (0.0-1.0, default: 0.8)
        texture_repeat: Number of bark texture repetitions (default: 3)
        build_end_cap: Close branch ends (default: True)
        build_blend: Smooth branch transitions (default: True)
        build_cutoff_age: Skip branches younger than this age (default: 0 - keep all)
        build_cutoff_thickness: Skip branches thinner than this (default: 0.0 - keep all)

    Returns:
        Path to the summary file

    Note: The strange pointy artifacts are often caused by build_cutoff_age > 0 or 
    build_cutoff_thickness > 0.0, which can remove important structural branches.
    Try build_cutoff_age=0 and build_cutoff_thickness=0.0 for cleaner results.
    """
    csv_file = Path(csv_file)
    output_dir = Path(output_directory)

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

    # Load presets for each tree (no flush calculation needed)
    print("Loading species presets...")

    # Validate that all species have presets
    for species in unique_species:
        preset_data = _load_species_preset(species)
        if preset_data is None:
            raise ValueError(f"Failed to load preset for species: {species}")

    print(f"All species presets validated. Using {flushes} flushes for all trees.")

    # Create separate groves for each species (proper "grow together" approach)
    print("Creating species-specific groves...")

    # Group trees by species
    species_groups = trees_data.groupby("species")
    list_of_groves = []
    grove_species_map = {}
    grove_tree_positions = {}  # Track original positions for each grove

    for species, group_data in species_groups:
        print(f"Creating grove for species: {species} ({len(group_data)} trees)")

        # Create grove for this species
        grove = tg.Grove()

        # Store original positions for this grove
        grove_positions = []

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

        # Add trees of this species to their grove
        for index, row in group_data.iterrows():
            # Access coordinates by column name to ensure correct mapping
            x, y, z = float(row.x), float(row.y), float(row.z)
            
            # Store original position for later use during export
            grove_positions.append((x, y, z))
            
            # Use coordinates as specified in CSV (no coordinate transformation)
            position = tg.Vector(x, y, z)
            direction = tg.Vector(0.0, 0.0, 1.0)  # Z-up (standard for many 3D applications)

            # No delay needed since all trees use the same number of flushes
            delay = 0

            grove.add_new_tree(position, direction, delay)

            print(f"Added {species} tree at ({x}, {y}, {z})")

        list_of_groves.append(grove)
        grove_species_map[len(list_of_groves) - 1] = species
        grove_tree_positions[len(list_of_groves) - 1] = grove_positions

    # Calculate total simulation flushes needed (now just use the fixed parameter)
    max_flushes = flushes

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

    # Build 3D models from all groves as individual tree files
    print("\nBuilding individual tree models...")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Use the base_name parameter for individual files

    # Build options for model generation (now using function parameters)
    build_options = {
        "resolution": resolution,
        "reduce": reduce,
        "texture_repeat": texture_repeat,
        "build_end_cap": build_end_cap,
        "build_blend": build_blend,
        "build_cutoff_age": build_cutoff_age,
        "build_cutoff_thickness": build_cutoff_thickness,
    }

    # Track generated files and statistics
    generated_files = []
    total_trees = 0
    total_vertices = 0
    total_faces = 0
    global_tree_counter = 1  # Start from 1 for clearer numbering

    for grove_index, grove in enumerate(list_of_groves):
        species = grove_species_map[grove_index]
        original_positions = grove_tree_positions[grove_index]
        expected_tree_count = len(original_positions)
        print(f"Building individual models for {species} grove...")

        # Build individual models for each tree in this grove
        models = grove.build_models(build_options)
        
        print(f"Grove for {species} with {expected_tree_count} trees generated {len(models)} models")
        
        # Debug: Check model sizes
        for i, model in enumerate(models):
            print(f"  Model {i}: {len(model.points)} vertices, {len(model.faces)} faces")
        
        # If we get more models than expected, only use the largest one (full tree)
        if len(models) > expected_tree_count:
            print(f"  Warning: Got {len(models)} models for {expected_tree_count} trees. Using largest models only.")
            # Sort models by vertex count and take the largest ones
            models_with_sizes = [(i, len(model.points), model) for i, model in enumerate(models)]
            models_with_sizes.sort(key=lambda x: x[1], reverse=True)  # Sort by vertex count, largest first
            models = [item[2] for item in models_with_sizes[:expected_tree_count]]  # Take only as many as we have trees
            print(f"  Selected {len(models)} largest models")
        
        # Save each tree as a separate OBJ file
        for tree_index, model in enumerate(models):
            # Get the original world position for this tree
            if tree_index < len(original_positions):
                orig_x, orig_y, orig_z = original_positions[tree_index]
            else:
                orig_x, orig_y, orig_z = 0.0, 0.0, 0.0  # Fallback
            
            # Create filename with global tree counter for clarity
            tree_filename = f"{base_name}_tree_{global_tree_counter:03d}_{species.replace(' - ', '_').replace(' ', '_')}.obj"
            tree_filepath = output_dir / tree_filename
            
            # Use The Grove's built-in OBJ export (much more robust)
            try:
                obj_string = tg.io.model_to_obj_string(model)
                
                # Apply world position transformation to the OBJ string
                if orig_x != 0.0 or orig_y != 0.0 or orig_z != 0.0:
                    obj_lines = obj_string.split('\n')
                    transformed_lines = []
                    
                    for line in obj_lines:
                        if line.startswith('v '):  # Vertex line
                            parts = line.split()
                            if len(parts) >= 4:  # v x y z
                                try:
                                    # Original Grove coordinates (Z-up) - keep tree geometry unchanged
                                    grove_x = float(parts[1])
                                    grove_y = float(parts[2])
                                    grove_z = float(parts[3])
                                    
                                    # Apply world position offset with coordinate transformation
                                    # Transform position coordinates: CSV X,Y -> Blender X,-Z (horizontal plane)
                                    world_x = grove_x + orig_x  # X position stays X
                                    world_y = grove_y + orig_z  # Tree Y (up) gets Z position offset  
                                    world_z = grove_z - orig_y  # Tree Z (depth) gets inverted Y position offset
                                    
                                    transformed_lines.append(f"v {world_x:.6f} {world_y:.6f} {world_z:.6f}")
                                except (ValueError, IndexError):
                                    transformed_lines.append(line)  # Keep original if parsing fails
                            else:
                                transformed_lines.append(line)
                        else:
                            transformed_lines.append(line)  # Keep non-vertex lines as-is
                    
                    obj_string = '\n'.join(transformed_lines)
                
                # Add our custom header with metadata
                header_lines = [
                    "# Individual tree model generated by GrowPy",
                    "# Coordinate system: Grove Z-up preserved, position coordinates transformed",
                    "# Import settings for Blender: Forward: -Z Forward, Up: Y Up", 
                    "# Tree geometry: Grove Z-up preserved (trees stay upright)",
                    "# Position mapping: CSV X,Y -> Blender X,-Z (horizontal distribution with Y inverted)",
                    f"# Species: {species}",
                    f"# Global tree number: {global_tree_counter}",
                    f"# Tree index in species: {tree_index}",
                    f"# Original world position (CSV): ({orig_x}, {orig_y}, {orig_z})",
                    f"# Vertices: {len(model.points)}, Faces: {len(model.faces)}",
                    "",
                ]
                
                # Combine header with Grove's OBJ export
                final_obj_content = "\n".join(header_lines) + obj_string
                
                # Write to file
                with open(tree_filepath, "w") as obj_file:
                    obj_file.write(final_obj_content)
                    
            except Exception as e:
                print(f"  Error using Grove's OBJ export: {e}")
                print("  Falling back to manual OBJ export...")
                
                # Fallback to manual export if Grove's export fails
                points = model.points
                faces = model.faces
                uvs = model.uvs

                with open(tree_filepath, "w") as obj_file:
                    # Write header
                    obj_file.write("# Individual tree model generated by GrowPy (manual export)\n")
                    obj_file.write("# Coordinate system: Grove Z-up preserved, position coordinates transformed\n")
                    obj_file.write(f"# Species: {species}\n")
                    obj_file.write(f"# Global tree number: {global_tree_counter}\n")
                    obj_file.write(f"# Original world position (CSV): ({orig_x}, {orig_y}, {orig_z})\n")
                    obj_file.write(f"# Vertices: {len(points)}, Faces: {len(faces)}\n\n")

                    # Write vertices with world position transformation
                    for point in points:
                        # Transform position coordinates: CSV X,Y -> Blender X,-Z (horizontal plane)
                        # Keep tree geometry in Grove Z-up (trees stay upright)
                        world_x = point.x + orig_x  # X position stays X
                        world_y = point.y + orig_z  # Tree Y (up) gets Z position offset
                        world_z = point.z - orig_y  # Tree Z (depth) gets inverted Y position offset
                        obj_file.write(f"v {world_x:.6f} {world_y:.6f} {world_z:.6f}\n")

                    # Write UV coordinates if available
                    if uvs:
                        obj_file.write("\n")
                        for uv in uvs:
                            if hasattr(uv, "x"):
                                obj_file.write(f"vt {uv.x:.6f} {uv.y:.6f}\n")
                            else:
                                obj_file.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

                    # Write faces (ensure 1-based indexing for OBJ format)
                    obj_file.write("\n")
                    for face in faces:
                        if uvs:
                            # Include UV indices if UVs are available
                            face_str = " ".join([f"{v}/{v}" for v in face])
                        else:
                            # Vertex indices only
                            face_str = " ".join([str(v) for v in face])
                        obj_file.write(f"f {face_str}\n")

            generated_files.append(str(tree_filepath))
            total_trees += 1
            total_vertices += len(model.points)
            total_faces += len(model.faces)
            global_tree_counter += 1  # Increment global counter
            
            print(f"  Saved tree {global_tree_counter-1}: {tree_filename} at world pos ({orig_x}, {orig_y}, {orig_z}) ({len(model.points)} vertices, {len(model.faces)} faces)")

    # Create a summary file listing all generated trees
    summary_file = output_dir / f"{base_name}_summary.txt"
    with open(summary_file, "w") as summary:
        summary.write("Forest Generation Summary\n")
        summary.write("=" * 50 + "\n")
        summary.write(f"Total trees generated: {total_trees}\n")
        summary.write(f"Total vertices: {total_vertices}\n")
        summary.write(f"Total faces: {total_faces}\n")
        summary.write(f"Species included: {list(grove_species_map.values())}\n\n")
        summary.write("Generated files:\n")
        summary.write("-" * 20 + "\n")
        for filepath in generated_files:
            summary.write(f"{Path(filepath).name}\n")

    print(f"\nSuccessfully generated {total_trees} individual tree models!")
    print(f"Total geometry: {total_vertices} vertices, {total_faces} faces")
    print(f"Files saved to: {output_dir}")
    print(f"Summary saved to: {summary_file}")

    return str(summary_file)


if __name__ == "__main__":
    # Example usage - for full demo run
    demo_csv = current_dir.parent / "data" / "demo_forest.csv"
    combined_output_dir = Path("../data/output")

    combined_file = grow_forest_from_csv(
        csv_file=demo_csv,
        output_directory=combined_output_dir,
        resolution=10,  # Reduced from 16 for faster generation
        flushes=8,  # Fixed number of flushes for all trees
        base_name="demo_forest",
        # Build options to avoid artifacts
        build_cutoff_age=0,  # Keep all branches (prevents pointy artifacts)
        build_cutoff_thickness=0.0,  # Keep all branches (prevents gaps)
    )