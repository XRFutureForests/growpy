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

# Add The Grove modules to Python path
current_dir = Path(__file__).parent.parent
grove_modules_path = current_dir / "the_grove_22" / "modules"
sys.path.insert(0, str(grove_modules_path))

try:
    import the_grove_22_core
except ImportError as e:
    raise ImportError(
        f"Could not import the_grove_22_core module. Make sure The Grove 2.2 is properly installed.\n"
        f"Expected module path: {grove_modules_path}\n"
        f"Error: {e}"
    )


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


def validate_csv_format(csv_file: Union[str, Path]) -> Tuple[bool, str]:
    """
    Validate that the CSV file has the required format.

    Args:
        csv_file: Path to the CSV file

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_columns = {"x", "y", "z", "species", "age"}

    try:
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return False, "CSV file appears to be empty or has no header row"

            header_set = set(reader.fieldnames)
            missing_required = required_columns - header_set

            if missing_required:
                return False, f"Missing required columns: {', '.join(missing_required)}"

            # Check first row for data validity
            try:
                first_row = next(reader)
                float(first_row["x"])
                float(first_row["y"])
                float(first_row["z"])
                int(first_row["age"])
                if "height" in first_row and first_row["height"]:
                    float(first_row["height"])
            except (ValueError, StopIteration) as e:
                return False, f"Invalid data format in first row: {e}"

            return True, "CSV format is valid"

    except Exception as e:
        return False, f"Error reading CSV file: {e}"


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


def _create_tree_model(
    position: Tuple[float, float, float],
    species: str,
    age: int,
    target_height: Optional[float] = None,
    resolution: int = 16,
) -> Optional[object]:
    """
    Create a single tree model.

    Args:
        position: (x, y, z) coordinates for the tree
        species: Species name matching a preset file
        age: Age of the tree in years
        target_height: Optional target height (not fully implemented)
        resolution: Model resolution (number of sides at base)

    Returns:
        Tree model object or None if failed
    """
    try:
        # Create new grove for this tree
        grove = the_grove_22_core.Grove()

        # Load and apply species preset
        preset_data = _load_species_preset(species)
        if preset_data:
            props = grove.get_properties()

            # Apply preset properties
            for key, value in preset_data.items():
                try:
                    if hasattr(props, key):
                        setattr(props, key, value)
                except (TypeError, AttributeError):
                    # Skip properties that can't be set
                    pass

            grove.set_properties(props)

        # Position the tree
        x, y, z = position
        grove.replant_tree(
            0,
            the_grove_22_core.Vector(x, y, z),
            the_grove_22_core.Rotation(the_grove_22_core.Vector(0, 0, 1), 0),
        )

        # Simulate growth
        grove.simulate(age)

        # Build model with specified resolution
        build_options = {
            "resolution": resolution,
            "resolution_reduce": 0.8,
            "build_blend": True,
            "build_end_cap": True,
        }

        models = grove.build_models(build_options)

        if models and len(models) > 0:
            return models[0]

    except Exception as e:
        print(f"Error creating tree model for {species} at {position}: {e}")

    return None


def grow_forest_from_csv(
    csv_file: Union[str, Path],
    output_dir: Union[str, Path] = "output",
    resolution: int = 16,
    file_prefix: str = "tree_",
    validate_format: bool = True,
) -> List[str]:
    """
    Generate individual tree models from CSV data and export as OBJ files.

    Args:
        csv_file: Path to CSV file with tree data (x,y,z,species,age,height)
        output_dir: Directory to save generated OBJ files
        resolution: Model resolution (sides at tree base, default 16)
        file_prefix: Prefix for generated filenames
        validate_format: Whether to validate CSV format first

    Returns:
        List of generated file paths

    Raises:
        ValueError: If CSV format is invalid
        FileNotFoundError: If CSV file doesn't exist
    """
    csv_file = Path(csv_file)
    output_dir = Path(output_dir)

    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    if validate_format:
        is_valid, error_msg = validate_csv_format(csv_file)
        if not is_valid:
            raise ValueError(f"Invalid CSV format: {error_msg}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_files = []

    print(f"Reading tree data from: {csv_file}")
    print(f"Output directory: {output_dir}")
    print(f"Model resolution: {resolution}")
    print()

    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader, 1):
            try:
                # Extract data from CSV
                x = float(row["x"])
                y = float(row["y"])
                z = float(row["z"])
                species = row["species"]
                age = int(row["age"])
                target_height = (
                    float(row.get("height", 0)) if row.get("height") else None
                )

                print(
                    f"Creating tree {i:3d}: {species:<30} at ({x:6.1f}, {y:6.1f}, {z:6.1f}), age {age:2d}"
                )

                # Create tree model
                model = _create_tree_model(
                    (x, y, z), species, age, target_height, resolution
                )

                if model:
                    # Export to OBJ
                    obj_string = the_grove_22_core.io.model_to_obj_string(model)

                    # Create safe filename
                    safe_species = (
                        species.replace(" ", "_").replace("-", "_").replace(".", "_")
                    )
                    filename = f"{file_prefix}{i:03d}_{safe_species}.obj"
                    filepath = output_dir / filename

                    with open(filepath, "w") as obj_file:
                        obj_file.write(obj_string)

                    generated_files.append(str(filepath))
                    print(f"             -> Exported to {filename}")
                else:
                    print("             -> Failed to generate model")

            except Exception as e:
                print(f"Error processing row {i}: {e}")
                continue

    print(f"\nGenerated {len(generated_files)} tree models in {output_dir}")
    return generated_files


def grow_combined_forest_from_csv(
    csv_file: Union[str, Path],
    output_file: Union[str, Path] = "forest_scene.obj",
    resolution: int = 16,
    validate_format: bool = True,
) -> str:
    """
    Generate a single combined forest model from CSV data.

    Note: This creates a single OBJ file with all trees, but each tree
    uses the same species parameters (from the first tree in CSV).
    For mixed species forests, use grow_forest_from_csv instead.

    Args:
        csv_file: Path to CSV file with tree data
        output_file: Path for the combined OBJ file
        resolution: Model resolution
        validate_format: Whether to validate CSV format first

    Returns:
        Path to the generated file

    Raises:
        ValueError: If CSV format is invalid or no trees to process
        FileNotFoundError: If CSV file doesn't exist
    """
    csv_file = Path(csv_file)
    output_file = Path(output_file)

    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    if validate_format:
        is_valid, error_msg = validate_csv_format(csv_file)
        if not is_valid:
            raise ValueError(f"Invalid CSV format: {error_msg}")

    # Read all tree data
    trees_data = []
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trees_data.append(
                {
                    "x": float(row["x"]),
                    "y": float(row["y"]),
                    "z": float(row["z"]),
                    "species": row["species"],
                    "age": int(row["age"]),
                    "height": (
                        float(row.get("height", 0)) if row.get("height") else None
                    ),
                }
            )

    if not trees_data:
        raise ValueError("No tree data found in CSV file")

    print(f"Creating combined forest with {len(trees_data)} trees")

    try:
        # Create grove and configure with first tree's species
        grove = the_grove_22_core.Grove()
        first_species = trees_data[0]["species"]

        preset_data = _load_species_preset(first_species)
        if preset_data:
            props = grove.get_properties()
            for key, value in preset_data.items():
                try:
                    if hasattr(props, key):
                        setattr(props, key, value)
                except (TypeError, AttributeError):
                    pass
            grove.set_properties(props)

        # Add all trees to the grove
        max_age = 0
        for i, tree in enumerate(trees_data):
            if i == 0:
                # First tree is already in the grove, just position it
                grove.replant_tree(
                    0,
                    the_grove_22_core.Vector(tree["x"], tree["y"], tree["z"]),
                    the_grove_22_core.Rotation(the_grove_22_core.Vector(0, 0, 1), 0),
                )
            else:
                # Add additional trees
                position = the_grove_22_core.Vector(tree["x"], tree["y"], tree["z"])
                direction = the_grove_22_core.Vector(0, 0, 1)
                grove.add_new_tree(position, direction, 0)

            max_age = max(max_age, tree["age"])

        print(f"Simulating growth for {max_age} years...")

        # Simulate growth for maximum age
        grove.simulate(max_age)

        # Build as single combined model
        print("Building combined model...")
        build_options = {
            "resolution": resolution,
            "resolution_reduce": 0.8,
            "build_blend": True,
            "build_end_cap": True,
        }

        combined_model = grove.build_as_one_model(build_options)

        # Export to OBJ
        print(f"Exporting to {output_file}...")
        obj_string = the_grove_22_core.io.model_to_obj_string(combined_model)

        # Create output directory if needed
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            f.write(obj_string)

        print(f"Combined forest exported to {output_file}")
        return str(output_file)

    except Exception as e:
        raise RuntimeError(f"Error creating combined forest: {e}")


if __name__ == "__main__":
    # Example usage - for full demo run: python growpy_demo.py
    demo_csv = current_dir.parent / "data" / "demo_forest.csv"
    if demo_csv.exists():
        print("Testing GrowPy with demo forest...")
        print("For complete demonstration, run: python growpy_demo.py")
        files = grow_forest_from_csv(demo_csv, "test_output", resolution=8)
        print(f"Generated {len(files)} tree models")
    else:
        print("Demo CSV file not found. Available species:")
        for species in list_available_species()[:10]:  # Show first 10
            print(f"  - {species}")
        print(f"... and {len(list_available_species()) - 10} more")
        print("For complete demonstration, run: python growpy_demo.py")
