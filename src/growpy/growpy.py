"""
GrowPy - Lightweight CSV to tree generation using The Grove 2.2
==============================================================

Focused on leveraging Grove's existing functionality for mixed species forests.
"""

import sys
from pathlib import Path
from typing import List, Union, Optional

# Add Grove modules to path
from .config import GrowPyConfig

# Find Grove paths
DEFAULT_GROVE_PATH = Path(__file__).parent.parent / "the_grove_22"
DEFAULT_PRESETS_PATH = DEFAULT_GROVE_PATH / "presets"
DEFAULT_MODULES_PATH = DEFAULT_GROVE_PATH / "modules"

sys.path.insert(0, str(DEFAULT_MODULES_PATH))

try:
    import the_grove_22_core as grove_core
    import pandas as pd
except ImportError as e:
    raise RuntimeError(f"Required dependencies not found: {e}")


class GrowPyError(Exception):
    """GrowPy specific errors."""

    pass


def list_species() -> List[str]:
    """Get list of available tree species."""
    if not DEFAULT_PRESETS_PATH.exists():
        return []

    species = []
    for preset_file in DEFAULT_PRESETS_PATH.glob("*.seed.json"):
        species_name = preset_file.stem
        if species_name.endswith(".seed"):
            species_name = species_name[:-5]

        # Skip malformed or empty species names (including ones that start with '.')
        if species_name and species_name != "" and not species_name.startswith("."):
            species.append(species_name)

    return sorted(species)


def get_grove_info() -> dict:
    """Get Grove version and edition information."""
    try:
        return {
            "version": grove_core.about.release,
            "edition": grove_core.about.edition,
            "description": grove_core.about.about,
        }
    except Exception:
        return {
            "version": "unknown",
            "edition": "unknown",
            "description": "Grove info unavailable",
        }


def safe_apply_species_preset(grove, species: str) -> bool:
    """
    Safely apply species preset, catching Grove compatibility issues.

    Args:
        grove: Grove object
        species: Species name

    Returns:
        True if preset was applied successfully, False if there was an issue
    """
    try:
        return apply_species_preset(grove, species)
    except Exception as e:
        # Catch any exceptions that might escape from apply_species_preset
        error_str = str(e)
        error_type = str(type(e))

        if (
            "PanicException" in error_type
            or "invalid type" in error_str
            or "expected usize" in error_str
            or "called `Result::unwrap()` on an `Err` value" in error_str
        ):
            print(
                f"Warning: Grove compatibility issue with preset '{species}' - using default properties"
            )
            return False
        else:
            print(f"Warning: Unexpected error with preset '{species}': {e}")
            return False


def apply_species_preset(grove, species: str) -> bool:
    """
    Apply species preset to Grove using Grove's built-in preset loading.

    Args:
        grove: Grove object
        species: Species name

    Returns:
        True if preset was applied successfully
    """
    preset_path = DEFAULT_PRESETS_PATH / f"{species}.seed.json"
    if not preset_path.exists():
        print(f"Warning: No preset found for species '{species}'")
        return False

    try:
        # Read preset file
        with open(preset_path, "r") as f:
            preset_json = f.read()

        # Use Grove's built-in preset loading
        properties = grove_core.io.properties_from_json_string(preset_json)
        grove.set_properties(properties)
        return True

    except Exception as e:
        # Handle Grove parsing errors gracefully
        error_msg = str(e)
        error_type = str(type(e))

        if (
            "PanicException" in error_type
            or "invalid type" in error_msg
            or "expected usize" in error_msg
            or "called `Result::unwrap()` on an `Err` value" in error_msg
        ):
            print(
                f"Warning: Grove version compatibility issue with preset '{species}': JSON format incompatibility"
            )
            print("  This is a known issue with some Grove 2.2 preset files")
            return False
        else:
            print(f"Warning: Error applying preset for {species}: {e}")
            return False


def generate_trees(
    csv_path: Union[str, Path], config: Optional[GrowPyConfig] = None
) -> List[str]:
    """
    Generate trees from CSV data using The Grove 2.2.

    Args:
        csv_path: Path to CSV file with columns: x, y, z, species
        config: Optional configuration

    Returns:
        List of generated file paths

    Example:
        files = generate_trees("forest.csv")

        # With custom config
        config = GrowPyConfig(growth_cycles=15, resolution=32)
        files = generate_trees("forest.csv", config)
    """
    config = config or GrowPyConfig()
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise GrowPyError(f"CSV file not found: {csv_path}")

    # Load CSV data
    try:
        data = pd.read_csv(csv_path)
        _validate_csv_data(data)
    except Exception as e:
        raise GrowPyError(f"Error loading CSV: {e}")

    # Validate species
    unique_species = data["species"].unique()
    available_species = list_species()
    invalid_species = [s for s in unique_species if s not in available_species]
    if invalid_species:
        raise GrowPyError(
            f"Unknown species: {invalid_species}. Available: {available_species}"
        )

    # Create output directory
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # Generate individual trees
    return _generate_individual_species(data, config)


def _generate_individual_species(data, config: GrowPyConfig) -> List[str]:
    """Generate separate grove for each species using Grove's mixing species approach."""
    print(f"Generating {len(data)} trees as individual species groves...")

    groves = []

    # Create grove for each species
    for species, group in data.groupby("species"):
        grove = grove_core.Grove()

        # Clear default tree as recommended in Grove documentation
        grove.clear_trees()

        if config.random_seed:
            grove.set_random_seed(config.random_seed + hash(species) % 1000)

        # Apply species preset using Grove's built-in system
        preset_success = safe_apply_species_preset(grove, species)
        if not preset_success:
            print(
                f"  Warning: Using default properties for {species} (preset failed to load)"
            )
            # Continue with default Grove properties rather than failing

        # Add trees at positions using Grove's add_new_tree
        positions = []
        for _, row in group.iterrows():
            positions.append(
                grove_core.Vector(float(row.x), float(row.y), float(row.z))
            )

        # Apply position variation if enabled (using Grove's tree_math)
        if config.add_position_variation and len(positions) > 1:
            try:
                # Use Grove's add_variation function for natural positioning
                positions, directions, delays = grove_core.tree_math.add_variation(
                    positions,
                    random_shift=config.position_random_shift,
                    seed=config.random_seed or 0,
                )
            except Exception as e:
                print(f"Warning: Could not apply position variation: {e}")
                # Fallback to default directions and no delays
                directions = [grove_core.Vector(0.0, 0.0, 1.0)] * len(positions)
                delays = [0] * len(positions)
        else:
            # Default directions and no delays
            directions = [grove_core.Vector(0.0, 0.0, 1.0)] * len(positions)
            delays = [0] * len(positions)

        # Add trees to grove
        for position, direction, delay in zip(positions, directions, delays):
            grove.add_new_tree(position, direction, delay)

        # Validate grove has trees
        if len(grove.trees) == 0:
            print(f"Warning: No trees added to {species} grove")
            continue

        groves.append((grove, species, len(group)))
        print(f"  Created {species} grove with {len(group)} trees")

    if not groves:
        raise GrowPyError("No valid groves created")

    # Simulate all groves together with shared light environment (per Grove docs)
    print(
        f"Simulating {len(groves)} groves together for {config.growth_cycles} cycles..."
    )
    grove_objects = [g[0] for g in groves]

    # Follow exact pattern from "Mixing species" documentation
    for cycle in range(config.growth_cycles):
        # Step 1: Collect shade geometry from all groves
        coords = []
        for grove in grove_objects:
            coords.extend(grove.create_shade_geometry_coords())

        # Step 2: Calculate shade and simulate each grove
        for grove in grove_objects:
            grove.calculate_shade_together(coords)
            grove.simulate(1)  # One flush at a time as documented

    # Build and export models with position information
    exported_files = []
    for grove, species, tree_count in groves:
        models = grove.build_models(config.to_grove_build_options())

        if not models:
            print(f"Warning: No models built for {species}")
            continue

        # Get the original positions for this species from the CSV data
        species_group = data[data["species"] == species]
        positions = [
            grove_core.Vector(float(row.x), float(row.y), float(row.z))
            for _, row in species_group.iterrows()
        ]

        for i, model in enumerate(models):
            # Get the corresponding position for this tree
            tree_position = (
                positions[i] if i < len(positions) else grove_core.Vector(0.0, 0.0, 0.0)
            )

            # Include position in filename for identification
            position_suffix = (
                f"_x{tree_position.x:.1f}_y{tree_position.y:.1f}_z{tree_position.z:.1f}"
            )

            filename = f"{species.replace(' ', '_')}_{i:03d}{position_suffix}.{config.export_format.value}"
            file_path = config.output_dir / filename

            # Export with position translation
            _export_model_with_position(
                model, file_path, config.export_format, config, tree_position
            )
            exported_files.append(str(file_path))

    print(f"Exported {len(exported_files)} individual tree files with positions")
    return exported_files


def _export_model_with_position(
    model,
    file_path: Path,
    export_format,
    config: GrowPyConfig,
    position: Optional[grove_core.Vector] = None,
):
    """Export model using Grove's built-in export functions with optional position translation."""
    try:
        # Apply coordinate system transformation if needed (Grove Model feature)
        if config.up_axis != "Z":  # Grove default is Z-up
            model.set_up_axis(config.up_axis)

        if export_format.value == "obj":
            # Use Grove's built-in OBJ export (studio edition feature)
            if hasattr(grove_core.io, "model_to_obj_string"):
                obj_string = grove_core.io.model_to_obj_string(model)

                # If we have a position, translate the vertices in the OBJ string
                if position and (
                    position.x != 0.0 or position.y != 0.0 or position.z != 0.0
                ):
                    obj_string = _translate_obj_vertices(obj_string, position)

                with open(file_path, "w") as f:
                    f.write(obj_string)
            else:
                raise GrowPyError("OBJ export not available in this Grove edition")

        elif export_format.value == "usd":
            # Use Grove's built-in USD export (studio edition feature)
            if hasattr(grove_core.io, "model_to_usda_string"):
                usd_string = grove_core.io.model_to_usda_string(model)

                # Note: USD translation would need different implementation
                if position and (
                    position.x != 0.0 or position.y != 0.0 or position.z != 0.0
                ):
                    print(
                        "Warning: Position translation not implemented for USD format"
                    )

                with open(file_path, "w") as f:
                    f.write(usd_string)
            else:
                raise GrowPyError("USD export not available in this Grove edition")
        else:
            raise GrowPyError(f"Unsupported export format: {export_format}")

    except Exception as e:
        raise GrowPyError(f"Export failed for {file_path}: {e}")


def _translate_obj_vertices(obj_string: str, position: grove_core.Vector) -> str:
    """Translate all vertices in an OBJ string by the given position offset."""
    lines = obj_string.split("\n")
    translated_lines = []

    for line in lines:
        if line.startswith("v "):  # Vertex line
            parts = line.split()
            if len(parts) >= 4:  # 'v x y z' (and optionally w)
                try:
                    # Fix coordinate mapping for Blender: CSV (x,y,z) -> OBJ (x,-z,y)
                    # This corrects the Y-Z axis swap and Y-axis inversion in Blender
                    x = float(parts[1]) + position.x  # X stays X
                    y = float(parts[2]) - position.z  # CSV Z becomes OBJ Y (negated)
                    z = float(parts[3]) + position.y  # CSV Y becomes OBJ Z

                    # Reconstruct the vertex line with corrected coordinates
                    translated_line = f"v {x:.6f} {y:.6f} {z:.6f}"
                    if len(parts) > 4:  # Include w component if present
                        translated_line += f" {parts[4]}"
                    translated_lines.append(translated_line)
                except (ValueError, IndexError):
                    # If parsing fails, keep original line
                    translated_lines.append(line)
            else:
                translated_lines.append(line)
        else:
            # Non-vertex lines pass through unchanged
            translated_lines.append(line)

    return "\n".join(translated_lines)


def _export_model(model, file_path: Path, export_format, config: GrowPyConfig):
    """Export model using Grove's built-in export functions (legacy function for compatibility)."""
    return _export_model_with_position(model, file_path, export_format, config, None)


def _validate_csv_data(data) -> None:
    """Validate CSV has required columns."""
    required = ["x", "y", "z", "species"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    for col in required:
        if data[col].isnull().any():
            raise ValueError(f"Column '{col}' contains missing values")
