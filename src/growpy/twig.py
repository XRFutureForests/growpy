"""Twig assignment and USD integration for tree models."""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import the_grove_22_core as gc

from .config import get_config


def load_twig_lookup_table(csv_path: Optional[Path] = None) -> pd.DataFrame:
    """Load the tree_asset_lookup lookup table using global config."""
    # Get global config (creates default if none set)
    config = get_config()
    
    if csv_path is None:
        # Use config's data directory (more robust)
        data_dir = config.get_data_directory()
        csv_path = data_dir / "tree_asset_lookup.csv"

    return pd.read_csv(csv_path)


def load_twig_conversion_report(json_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the twig conversion report containing USD twig metadata using global config."""
    # Get global config (creates default if none set)
    config = get_config()
    
    if json_path is None:
        # Use config's assets directory
        assets_dir = config.get_assets_directory()
        json_path = assets_dir / "twigs" / "conversion_report.json"

    with open(json_path, "r") as f:
        return json.load(f)


def get_twig_for_species(
    species_model: str, 
    lookup_table: Optional[pd.DataFrame] = None
) -> Optional[str]:
    """
    Get the appropriate twig for a species model.

    Args:
        species_model: The species model name (e.g., 'Pinaceae - Fir.seed.json')
        lookup_table: DataFrame with species-twig mappings (loaded if None)

    Returns:
        Twig name or None if no match found or twig is unavailable
    """
    # Get global config (creates default if none set)
    config = get_config()
    
    if lookup_table is None:
        lookup_table = load_twig_lookup_table()
    
    # Try to get twig from config first (using preset name as key)
    try:
        # Remove .seed.json extension to get clean species name
        species_name = species_model.replace(".seed.json", "")
        twig_name = config.get_twig_for_species(species_name)
        if twig_name and twig_name not in ["—", "", None] and not pd.isna(twig_name):
            return twig_name
    except Exception:
        pass
    
    # Fallback to lookup table matching
    model_name = species_model.replace(".seed.json", ".seed.json")
    matches = lookup_table[lookup_table["Model"] == model_name]

    if matches.empty:
        return None

    twig_name = matches.iloc[0]["Twig"]

    # Check if twig is marked as unavailable
    if twig_name in ["—", "", None] or pd.isna(twig_name):
        return None

    return twig_name


def get_twig_usd_paths(
    twig_name: str, 
    conversion_report: Optional[Dict[str, Any]] = None, 
    base_path: Optional[Path] = None
) -> Dict[str, str]:
    """
    Get USD file paths for a twig using global config.

    Args:
        twig_name: Name of the twig (e.g., 'PacificSilverFir')
        conversion_report: Twig conversion report data (loaded if None)
        base_path: Base path for resolving relative paths (uses config if None)

    Returns:
        Dictionary with 'prototype' and 'material' paths
    """
    # Get global config (creates default if none set)
    config = get_config()
    
    if conversion_report is None:
        conversion_report = load_twig_conversion_report()
    
    if base_path is None:
        base_path = config.get_assets_directory()

    # Remove 'Twig' suffix if present for lookup
    lookup_name = twig_name.replace("Twig", "")

    if lookup_name not in conversion_report:
        return {}

    twig_info = conversion_report[lookup_name]

    if not twig_info.get("success", False):
        return {}

    paths = {}

    # Get prototype path - try both relative and absolute approaches
    if twig_info.get("prototype_path"):
        # Try relative to assets directory first
        prototype_path = base_path / "twigs" / "prototypes" / f"{lookup_name}_prototype.usda"
        if not prototype_path.exists():
            # Try the path from conversion report
            prototype_path = base_path / twig_info["prototype_path"]
        
        if prototype_path.exists():
            paths["prototype"] = str(prototype_path)

    # Get material path - try both relative and absolute approaches  
    if twig_info.get("material_path"):
        # Try relative to assets directory first
        material_path = base_path / "twigs" / "materials" / f"{lookup_name}_material.usda"
        if not material_path.exists():
            # Try the path from conversion report
            material_path = base_path / twig_info["material_path"]
        
        if material_path.exists():
            paths["material"] = str(material_path)

    return paths


def calculate_twig_positions(
    model: Any, density: float = 1.0, min_radius: float = 0.001
) -> List[Tuple[float, float, float, float, float, float, float]]:
    """
    Calculate positions for twig instances based on branch tips using Grove's twig methods.

    Args:
        model: Grove 3D model
        density: Density factor for twig placement (0.0-1.0)
        min_radius: Minimum branch radius for twig placement

    Returns:
        List of (x, y, z, rx, ry, rz, scale) tuples for twig transforms
    """
    positions = []

    # Use Grove's built-in twig location and orientation methods
    try:
        twig_locations = (
            model.get_twig_locations()
        )  # Flat list of floats [x1,y1,z1,x2,y2,z2,...]
        twig_orientations = (
            model.get_twig_orientations()
        )  # Flat list of floats [w1,x1,y1,z1,w2,x2,y2,z2,...]

        # Parse locations (groups of 3 floats)
        num_locations = len(twig_locations) // 3

        # Parse orientations (groups of 4 floats - quaternions)
        num_orientations = len(twig_orientations) // 4

        # Get thickness attribute for filtering by minimum radius
        thickness_attr = getattr(model, "point_attribute_thickness", None)

        for i in range(num_locations):
            # Apply density filter
            if density < 1.0:
                import random

                if random.random() > density:
                    continue

            # Check minimum radius requirement if thickness data is available
            if thickness_attr and i < len(thickness_attr):
                if thickness_attr[i] < min_radius:
                    continue

            # Extract position from flat list
            x = twig_locations[i * 3]
            y = twig_locations[i * 3 + 1]
            z = twig_locations[i * 3 + 2]

            # Extract orientation (quaternion) from flat list
            rx, ry, rz = 0.0, 0.0, 0.0
            if i < num_orientations:
                qw = twig_orientations[i * 4]
                qx = twig_orientations[i * 4 + 1]
                qy = twig_orientations[i * 4 + 2]
                qz = twig_orientations[i * 4 + 3]

                # Convert quaternion to euler angles (simplified)
                try:
                    rx = math.atan2(
                        2.0 * (qw * qx + qy * qz), 1.0 - 2.0 * (qx * qx + qy * qy)
                    )
                    ry = math.asin(max(-1.0, min(1.0, 2.0 * (qw * qy - qz * qx))))
                    rz = math.atan2(
                        2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz)
                    )
                except:
                    # Fallback to zero rotation if quaternion conversion fails
                    rx, ry, rz = 0.0, 0.0, 0.0

            # Calculate scale based on thickness if available
            scale = 1.0
            if thickness_attr and i < len(thickness_attr):
                # Scale twig based on branch thickness (normalized)
                scale = max(0.5, min(2.0, thickness_attr[i] * 10.0))

            positions.append((x, y, z, rx, ry, rz, scale))

    except Exception as e:
        print(f"Warning: Could not get twig positions from model: {e}")
        # Fallback: no twigs
        pass

    return positions


def create_twig_instances_usd(
    twig_paths: Dict[str, str],
    positions: List[Tuple[float, float, float, float, float, float, float]],
    base_scale: float = 1.0,
) -> str:
    """
    Create USD content for twig instances.

    Args:
        twig_paths: Dictionary with 'prototype' and optionally 'material' paths
        positions: List of (x, y, z, rx, ry, rz, scale) tuples
        base_scale: Base uniform scale factor for twigs

    Returns:
        USD string content for twig instances
    """
    if not twig_paths.get("prototype") or not positions:
        return ""

    usd_content = []

    # Add reference to the twig prototype
    prototype_path = twig_paths["prototype"]
    usd_content.append(f'def "TwigPrototype" (')
    usd_content.append(f"    add references = @{prototype_path}@")
    usd_content.append(")")
    usd_content.append("")

    # Create instances
    usd_content.append('def Scope "TwigInstances"')
    usd_content.append("{")

    for i, (x, y, z, rx, ry, rz, local_scale) in enumerate(positions):
        instance_name = f"twig_{i:04d}"
        final_scale = base_scale * local_scale

        usd_content.append(f'    def Xform "{instance_name}" (')
        usd_content.append(f"        add references = </TwigPrototype>")
        usd_content.append("    )")
        usd_content.append("    {")

        # Create transformation matrix with rotation and scale
        import math

        # Convert euler angles to rotation matrix (simplified)
        cos_rx, sin_rx = math.cos(rx), math.sin(rx)
        cos_ry, sin_ry = math.cos(ry), math.sin(ry)
        cos_rz, sin_rz = math.cos(rz), math.sin(rz)

        # Combined rotation matrix (Z * Y * X order)
        r11 = cos_ry * cos_rz
        r12 = -cos_ry * sin_rz
        r13 = sin_ry
        r21 = sin_rx * sin_ry * cos_rz + cos_rx * sin_rz
        r22 = -sin_rx * sin_ry * sin_rz + cos_rx * cos_rz
        r23 = -sin_rx * cos_ry
        r31 = -cos_rx * sin_ry * cos_rz + sin_rx * sin_rz
        r32 = cos_rx * sin_ry * sin_rz + sin_rx * cos_rz
        r33 = cos_rx * cos_ry

        # Apply scale to rotation matrix
        r11 *= final_scale
        r12 *= final_scale
        r13 *= final_scale
        r21 *= final_scale
        r22 *= final_scale
        r23 *= final_scale
        r31 *= final_scale
        r32 *= final_scale
        r33 *= final_scale

        # Add transform matrix
        usd_content.append(f"        matrix4d xformOp:transform = (")
        usd_content.append(f"            ({r11:.6f}, {r12:.6f}, {r13:.6f}, 0),")
        usd_content.append(f"            ({r21:.6f}, {r22:.6f}, {r23:.6f}, 0),")
        usd_content.append(f"            ({r31:.6f}, {r32:.6f}, {r33:.6f}, 0),")
        usd_content.append(f"            ({x:.6f}, {y:.6f}, {z:.6f}, 1)")
        usd_content.append("        )")
        usd_content.append(
            '        uniform token[] xformOpOrder = ["xformOp:transform"]'
        )
        usd_content.append("    }")
        usd_content.append("")

    usd_content.append("}")

    return "\n".join(usd_content)


def add_twigs_to_model_usd(
    model_usd: str,
    model: Any,
    species_model: str,
    twig_density: float = 1.0,
    twig_scale: float = 1.0,
    min_radius: float = 0.001,
    lookup_table: Optional[pd.DataFrame] = None,
    conversion_report: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Add twig instances to an existing model USD string using global config.

    Args:
        model_usd: Original USD content for the tree model
        model: Grove model object for extracting twig positions
        species_model: Species model name for twig lookup
        twig_density: Density factor for twig placement (0.0-1.0)
        twig_scale: Scale factor for twigs
        min_radius: Minimum branch radius for twig placement
        lookup_table: Species-twig lookup table (loaded if None)
        conversion_report: Twig conversion report (loaded if None)

    Returns:
        Modified USD content with twig instances
    """
    # Load lookup data if not provided using global config
    if lookup_table is None:
        lookup_table = load_twig_lookup_table()

    if conversion_report is None:
        conversion_report = load_twig_conversion_report()

    # Get appropriate twig for species
    twig_name = get_twig_for_species(species_model, lookup_table)
    if not twig_name:
        return model_usd  # No twig available for this species

    # Get twig USD paths using global config
    twig_paths = get_twig_usd_paths(twig_name, conversion_report)
    if not twig_paths:
        return model_usd  # No USD files available for this twig

    # Calculate twig positions from the model
    twig_positions = calculate_twig_positions(
        model, density=twig_density, min_radius=min_radius
    )

    if not twig_positions:
        return model_usd  # No valid twig positions found

    # Create twig instances USD content
    twig_usd = create_twig_instances_usd(twig_paths, twig_positions, twig_scale)

    if not twig_usd:
        return model_usd

    # Insert twig content into the USD file
    # Find the closing brace of the main tree definition and add twigs before it
    lines = model_usd.split("\n")

    # Look for the last closing brace to insert twigs before it
    insert_index = len(lines)
    brace_count = 0

    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if line == "}":
            brace_count += 1
            if brace_count == 1:  # First closing brace from the end
                insert_index = i
                break
        elif line == "{":
            brace_count -= 1

    # Insert twig content
    if insert_index < len(lines):
        lines.insert(insert_index, "")
        lines.insert(insert_index + 1, "    // Twig instances")
        for twig_line in twig_usd.split("\n"):
            if twig_line.strip():
                lines.insert(insert_index + 2, "    " + twig_line)
                insert_index += 1
            else:
                lines.insert(insert_index + 2, "")
                insert_index += 1

    return "\n".join(lines)


def save_model_with_twigs_to_usd(
    model: Any,
    species_model: str,
    output_path: Path,
    twig_density: float = 1.0,
    twig_scale: float = 1.0,
    min_radius: float = 0.001,
    build_options: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Save a Grove model to USD with twig instances.

    Args:
        model: Grove 3D model
        species_model: Species model name for twig lookup
        output_path: Path for output USD file
        twig_density: Density factor for twig placement (0.0-1.0)
        twig_scale: Scale factor for twigs
        min_radius: Minimum branch radius for twig placement
        build_options: Additional build options for the model

    Returns:
        True if successful, False otherwise
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get base USD content for the model
        base_usd = gc.io.model_to_usda_string(model)

        # Add twig instances to the USD
        usd_with_twigs = add_twigs_to_model_usd(
            base_usd,
            model,
            species_model,
            twig_density=twig_density,
            twig_scale=twig_scale,
            min_radius=min_radius,
        )

        # Write to file
        with open(output_path, "w") as f:
            f.write(usd_with_twigs)

        return True

    except Exception as e:
        print(f"Error saving model with twigs to USD: {e}")
        return False


def generate_forest_with_twigs(
    forest: List[Tuple[gc.Grove, str]],
    output_dir: Path,
    twig_density: float = 1.0,
    twig_scale: float = 1.0,
    min_radius: float = 0.001,
    build_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate USD files for a forest with twig instances.

    Args:
        forest: List of (grove, species_model) tuples
        output_dir: Directory for output USD files
        twig_density: Density factor for twig placement
        twig_scale: Scale factor for twigs
        min_radius: Minimum branch radius for twig placement
        build_options: Build options for models

    Returns:
        Dictionary with generation results and statistics
    """
    results = {
        "total_groves": len(forest),
        "successful_exports": 0,
        "failed_exports": 0,
        "twig_assignments": {},
        "export_paths": [],
    }

    # Load lookup data once
    lookup_table = load_twig_lookup_table()
    conversion_report = load_twig_conversion_report()

    output_dir.mkdir(parents=True, exist_ok=True)

    for i, (grove, species_model) in enumerate(forest):
        try:
            # Build models for this grove
            models = grove.build_models(build_options or {})

            if not models:
                results["failed_exports"] += 1
                continue

            # Get twig assignment
            twig_name = get_twig_for_species(species_model, lookup_table)
            results["twig_assignments"][f"grove_{i}"] = {
                "species": species_model,
                "twig": twig_name or "None",
            }

            # Export each tree in the grove
            for j, model in enumerate(models):
                output_filename = f"grove_{i:03d}_tree_{j:03d}_with_twigs.usda"
                output_path = output_dir / output_filename

                success = save_model_with_twigs_to_usd(
                    model,
                    species_model,
                    output_path,
                    twig_density=twig_density,
                    twig_scale=twig_scale,
                    min_radius=min_radius,
                    build_options=build_options,
                )

                if success:
                    results["successful_exports"] += 1
                    results["export_paths"].append(str(output_path))
                else:
                    results["failed_exports"] += 1

        except Exception as e:
            print(f"Error processing grove {i} with species {species_model}: {e}")
            results["failed_exports"] += 1

    return results


def list_available_twigs(
    conversion_report: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    List all available twigs with their metadata.

    Args:
        conversion_report: Twig conversion report (loaded if None)

    Returns:
        List of dictionaries with twig information
    """
    if conversion_report is None:
        conversion_report = load_twig_conversion_report()

    twigs = []

    for twig_name, info in conversion_report.items():
        if info.get("success", False):
            twig_info = {
                "name": twig_name,
                "vertex_count": info.get("vertex_count", 0),
                "face_count": info.get("face_count", 0),
                "has_material": bool(info.get("material_path")),
                "textures": info.get("textures", []),
                "prototype_path": info.get("prototype_path"),
                "material_path": info.get("material_path"),
            }
            twigs.append(twig_info)

    return sorted(twigs, key=lambda x: x["name"])


def get_species_twig_mapping(
    lookup_table: Optional[pd.DataFrame] = None,
) -> Dict[str, str]:
    """
    Get mapping of species models to their assigned twigs.

    Args:
        lookup_table: Species-twig lookup table (loaded if None)

    Returns:
        Dictionary mapping species model names to twig names
    """
    if lookup_table is None:
        lookup_table = load_twig_lookup_table()

    mapping = {}

    for _, row in lookup_table.iterrows():
        model = row["Model"]
        twig = row["Twig"]

        if twig not in ["—", "", None] and not pd.isna(twig):
            mapping[model] = twig

    return mapping
