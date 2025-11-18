"""
PVE Preset JSON generation for Unreal Engine Procedural Vegetation Editor.

Generates the JSON format required by PVE Preset Loader node, compatible with
Quixel Megaplants preset structure. This enables GrowPy trees to be used as
PVE presets with full parametric control.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def generate_pve_preset_json(
    grove: Any,
    species_name: str,
    output_path: Path,
    tree_index: int = 0,
) -> Dict:
    """
    Generate PVE Preset JSON from a Grove simulation.

    This creates the JSON format used by Unreal's PVE Preset Loader node,
    matching the structure found in Quixel Megaplants presets.

    Args:
        grove: Grove object after simulation (grove.simulate())
        species_name: Name of the species
        output_path: Path to save JSON file
        tree_index: Index of tree in grove (default: 0)

    Returns:
        Dictionary with PVE preset structure

    Example:
        ```python
        from growpy import create_grove
        from growpy.io.pve_preset_json import generate_pve_preset_json
        import the_grove_22_core as gc

        grove = create_grove("European Beech")
        grove.add_new_tree(gc.Vector(0,0,0), gc.Vector(0,0,1), 0)
        grove.simulate(flushes=12)

        pve_json = generate_pve_preset_json(
            grove=grove,
            species_name="European_Beech_01",
            output_path=Path("beech_preset.json")
        )
        ```
    """
    import the_grove_22_core as gc

    # Get Grove properties (growth parameters)
    properties = grove.get_properties()

    # Extract global attributes from Grove
    global_attrs = _extract_global_attributes(grove, properties)

    # Extract point data from Grove geometry
    points_data = _extract_points_data(grove, tree_index)

    # Extract primitive (branch connectivity) data
    primitives_data = _extract_primitives_data(grove, tree_index)

    # Build PVE preset structure
    pve_preset = {
        "globalAttributes": global_attrs,
        "points": points_data,
        "primitives": primitives_data,
    }

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(pve_preset, f, indent=2)

    print(f"Generated PVE preset JSON: {output_path}")
    return pve_preset


def _extract_global_attributes(grove: Any, properties: Any) -> Dict:
    """
    Extract global growth attributes from Grove properties.

    Maps Grove parameters to PVE globalAttributes format.
    """
    import the_grove_22_core as gc

    # Note: Many of these are Grove-specific and may need adjustment for PVE
    # Some parameters are curves (arrays), others are single values

    global_attrs = {
        # Basic simulation parameters
        "cycle": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": getattr(properties, "simulation_steps", 30),
        },
        "cycleTime": {
            "isArray": False,
            "size": 1,
            "type": "float",
            "value": getattr(properties, "cycle_time", 1.25),
        },
        "randomSeed": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": getattr(properties, "random_seed", 0),
        },
        # Gravity
        "gravitationalForce": {
            "isArray": False,
            "size": 1,
            "type": "float",
            "value": getattr(properties, "gravitational_force", 2.0),
        },
        # Branch structure limits
        "maxBranchNumber": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": grove.get_num_branches(),
        },
        "maxBudNumber": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": grove.get_num_buds(),
        },
        "compoundMaxBranchGeneration": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": _get_max_generation(grove),
        },
        "compoundMaxBranchNumber": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": grove.get_num_branches(),
        },
        # Growth parameters (these are typically curves in Grove)
        # For now, we'll extract simple values - can be enhanced with curve data
        "phototropism": _create_curve_attribute(
            _get_property_value(properties, "phototropism", [0.5, 0.0, 1.0, 0.0, 0.0])
        ),
        "phototropismChild": _create_curve_attribute(
            _get_property_value(
                properties, "phototropism_child", [0.5, 0.0, 1.0, 0.0, 0.0]
            )
        ),
        "phyllotaxy": _create_curve_attribute(
            _get_property_value(
                properties,
                "phyllotaxy",
                [
                    137.5,
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
            )
        ),
        "phyllotaxyChild": _create_curve_attribute(
            _get_property_value(
                properties,
                "phyllotaxy_child",
                [
                    137.5,
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
            )
        ),
        "phyllotaxyLeaf": _create_curve_attribute(
            _get_property_value(
                properties,
                "phyllotaxy_leaf",
                [137.5, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            )
        ),
        "axialElongation": _create_curve_attribute(
            _get_property_value(
                properties, "axial_elongation", [0.25, 0.0, 0.5, 0.0, 0.0, 1.0]
            )
        ),
        "axialElongationChild": _create_curve_attribute(
            _get_property_value(
                properties, "axial_elongation_child", [0.25, 0.0, 0.5, 0.0, 0.0, 1.0]
            )
        ),
        "lateralElongation": _create_curve_attribute(
            _get_property_value(
                properties,
                "lateral_elongation",
                [0.002, 1.0, 0.5, 7000.0, 10000.0, 0.5, 5.0, 0.6, 0.0],
            )
        ),
        "lateralElongationChild": _create_curve_attribute(
            _get_property_value(
                properties,
                "lateral_elongation_child",
                [0.002, 1.0, 0.5, 7000.0, 10000.0, 0.5, 5.0, 0.6, 0.0],
            )
        ),
        "branchingCondition": _create_curve_attribute(
            _get_property_value(
                properties,
                "branching_condition",
                [0.0, 0.0, 0.0, 1.0, 1.0, 0.4, 0.0, 0.0],
            )
        ),
        "branchingConditionChild": _create_curve_attribute(
            _get_property_value(
                properties,
                "branching_condition_child",
                [0.0, 0.0, 0.0, 1.0, 1.0, 0.4, 0.0, 0.0],
            )
        ),
        # Light and leaf growth
        "lightDetection": _create_curve_attribute(
            _get_property_value(
                properties, "light_detection", [3.0, 1.0, 64.0, 32.0, 1.0]
            )
        ),
        "leafGrowth": _create_curve_attribute(
            _get_property_value(
                properties,
                "leaf_growth",
                [0.027, 0.2, 0.395, 0.15, 2.0, 0.0, 0.5, 0.033, 0.0],
            )
        ),
        # Guide parameters
        "guide": _create_curve_attribute([0.0, 3.0, 0.0, 0.0]),
        # Random angles
        "randomAngle": _create_curve_attribute([1.17, 4.25, 0.0]),
        "randomAngleChild": _create_curve_attribute([1.17, 4.25, 0.0]),
        # Trunk growth
        "trunkGrowth": _create_curve_attribute(
            [6.0, 1.0, 1.0, 1.0, 1.0, 1.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        ),
        # Senescence (leaf drop)
        "abscissionSenescense": _create_curve_attribute(
            [0.148, 36.0, 1.0, 5.0, 0.0, 0.452, 6.0, 11.0, 0.0]
        ),
        # Plant profiles (shape curves) - these define the tree silhouette
        # For now, create default profiles - can be extracted from Grove later
        "plantProfile_1": _create_plant_profile(101),
        "plantProfile_2": _create_plant_profile(101),
        "plantProfile_3": _create_plant_profile(101),
        "plantProfile_4": _create_plant_profile(101),
        "plantProfile_5": _create_plant_profile(101),
        # Scale parameters
        "maxPscale": {
            "isArray": False,
            "size": 1,
            "type": "float",
            "value": _get_max_pscale(grove),
        },
        "minPscale": {"isArray": False, "size": 1, "type": "float", "value": 0.0},
        "max_pscale": {
            "isArray": False,
            "size": 1,
            "type": "float",
            "value": _get_max_pscale(grove),
        },
        "max_curve_length": {
            "isArray": False,
            "size": 1,
            "type": "float",
            "value": _get_max_curve_length(grove),
        },
        # Photogrammetry (not used for procedural trees)
        "photogrammetryTrunk": {"isArray": False, "size": 1, "type": "int", "value": 0},
        "photogrammetryMeshNames": {
            "isArray": True,
            "size": 1,
            "type": "string",
            "value": [],
        },
        "photogrammetryMeshes": {
            "isArray": True,
            "size": 1,
            "type": "dict",
            "value": [],
        },
    }

    return global_attrs


def _extract_points_data(grove: Any, tree_index: int = 0) -> Dict:
    """
    Extract point cloud data from Grove geometry.

    This includes positions, attributes, and per-point metadata.
    """
    # Get tree geometry from Grove
    # Note: This will need Grove API calls to extract point data

    # Placeholder structure - needs actual Grove geometry extraction
    points_data = {
        "attributes": {
            "P": {},  # Position (redundant with positions below)
            "pscale": {},  # Branch thickness
            "generation": {},  # Branch hierarchy level
            "branchGradient": {},  # Position along branch (0=base, 1=tip)
            "plantGradient": {},  # Position in overall plant
            "lengthFromRoot": {},  # Distance from trunk base
            "lengthFromSeed": {},  # Total growth length
            "budNumber": {},  # Bud identifier
            "budStatus": {},  # Active/dormant/etc
            "budDirection": {},  # Growth direction vector
            "budDevelopment": {},  # Development stage
            "budHormoneLevels": {},  # Auxin/cytokinin levels
            "budLateralMeristem": {},  # Lateral bud info
            "budLightDetected": {},  # Light exposure
            # LOD (Level of Detail) attributes
            "LODArray_endCapSegments": {},
            "LODArray_keepPTs": {},
            "LOD_branchPscaleGradient": {},
            "LOD_canopyGradient": {},
            "LOD_groundGradient": {},
            "LOD_hullGradient": {},
            "LOD_mainTrunkGradient": {},
            "LOD_plantPscaleGradient": {},
            "LOD_totalPscaleGradient": {},
            # UV coordinates
            "uv_base": {},
            "uv_base_unmodified": {},
            "uv_metric": {},
            "uv_out": {},
            # Other
            "njord_pixelIdx": {},  # Light simulation index
        },
        "positions": [],  # List of [x, y, z] coordinates
    }

    # TODO: Extract actual point data from Grove
    # This requires calling Grove API methods to get:
    # - Point positions
    # - Branch hierarchy
    # - Bud information
    # - Per-point attributes

    return points_data


def _extract_primitives_data(grove: Any, tree_index: int = 0) -> Dict:
    """
    Extract primitive (branch connectivity) data from Grove.

    Defines how points connect to form branches.
    """
    primitives_data = {
        "attributes": {},
        "points": [],  # List of point index arrays defining curves/branches
    }

    # TODO: Extract branch connectivity from Grove
    # Each entry in "points" is an array of point indices that form a curve

    return primitives_data


# Helper functions


def _create_curve_attribute(values: List[float]) -> Dict:
    """Create a curve attribute in PVE format."""
    return {"isArray": True, "size": 1, "type": "float", "value": values}


def _create_plant_profile(num_points: int = 101) -> Dict:
    """
    Create a plant profile curve (defines tree silhouette).

    Default creates a simple parabolic shape.
    """
    # Create simple default curve
    curve_points = []
    for i in range(num_points):
        t = i / (num_points - 1)
        # Simple parabolic shape
        value = 4.0 * t * (1.0 - t)  # Peak at center
        curve_points.append(value)

    return {"isArray": True, "size": 1, "type": "float", "value": curve_points}


def _get_property_value(
    properties: Any, attr_name: str, default: List[float]
) -> List[float]:
    """Safely get property value with default fallback."""
    try:
        value = getattr(properties, attr_name, None)
        if value is not None:
            return value if isinstance(value, list) else [value]
    except:
        pass
    return default


def _get_max_generation(grove: Any) -> int:
    """Get maximum branch generation (hierarchy depth)."""
    try:
        # This would need Grove API to traverse branch hierarchy
        return 3  # Default placeholder
    except:
        return 3


def _get_max_pscale(grove: Any) -> float:
    """Get maximum branch radius from Grove."""
    try:
        # This would need Grove API to get max thickness
        return 0.02  # Default placeholder
    except:
        return 0.02


def _get_max_curve_length(grove: Any) -> float:
    """Get maximum branch length from Grove."""
    try:
        # This would need Grove API to get max branch length
        return 3.0  # Default placeholder
    except:
        return 3.0


def generate_pve_preset_for_species(
    species_name: str,
    output_dir: Path,
    num_variations: int = 1,
    growth_cycles: int = 12,
    resolution: int = 24,
) -> List[Path]:
    """
    Generate multiple PVE preset JSON files for a species.

    Creates variations with different random seeds.

    Args:
        species_name: Name of species
        output_dir: Output directory
        num_variations: Number of variations to generate
        growth_cycles: Number of growth cycles to simulate
        resolution: Branch resolution

    Returns:
        List of generated JSON file paths
    """
    import the_grove_22_core as gc

    from growpy import create_grove

    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files = []

    for i in range(num_variations):
        # Create grove with unique seed
        grove = create_grove(species_name)

        # Add tree
        grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), i)

        # Simulate growth
        grove.simulate(flushes=growth_cycles)

        # Generate JSON
        variation_name = f"{species_name.replace(' ', '_')}_{i+1:02d}"
        json_path = output_dir / f"{variation_name}.json"

        generate_pve_preset_json(
            grove=grove,
            species_name=variation_name,
            output_path=json_path,
            tree_index=0,
        )

        generated_files.append(json_path)

    return generated_files
    return generated_files
