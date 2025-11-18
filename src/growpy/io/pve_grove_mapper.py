"""
Map Grove API data directly to PVE Preset JSON format.

This module extracts data from Grove simulations and maps it to the
Quixel Megaplants PVE format, avoiding Houdini entirely.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .pve_schema import create_empty_pve_preset


def create_pve_template_from_reference(reference_json_path: Path) -> Dict:
    """
    Create an empty PVE template based on a reference JSON (like Hazel).

    Preserves the structure but clears the data arrays/values.
    """
    with open(reference_json_path, "r") as f:
        reference = json.load(f)

    template = {
        "globalAttributes": _create_empty_global_attributes(
            reference.get("globalAttributes", {})
        ),
        "points": {
            "attributes": _create_empty_point_attributes(
                reference["points"]["attributes"]
            ),
            "positions": [],
        },
        "primitives": {
            "attributes": _create_empty_primitive_attributes(
                reference["primitives"]["attributes"]
            ),
            "points": [],
        },
    }

    return template


def _create_empty_global_attributes(reference: Dict) -> Dict:
    """Create empty globalAttributes structure."""
    empty = {}
    for key, value in reference.items():
        empty[key] = {
            "isArray": value.get("isArray", False),
            "size": value.get("size", 1),
            "type": value.get("type", "float"),
            "value": [] if value.get("isArray") else 0,
        }
    return empty


def _create_empty_point_attributes(reference: Dict) -> Dict:
    """Create empty point attributes structure, preserving 'value' vs 'values' key."""
    empty = {}
    for key, value in reference.items():
        # Preserve the exact key name from reference (value vs values)
        value_key = "values" if "values" in value else "value"
        empty[key] = {
            "isArray": value.get("isArray", False),
            "size": value.get("size", 1),
            "type": value.get("type", "float"),
            value_key: [],
        }
    return empty


def _create_empty_primitive_attributes(reference: Dict) -> Dict:
    """Create empty primitive attributes structure."""
    empty = {}
    for key, value in reference.items():
        empty[key] = {
            "isArray": value.get("isArray", False),
            "size": value.get("size", 1),
            "type": value.get("type", "int"),
            "value": [],
        }
    return empty


def map_grove_to_pve(
    grove: Any,
    template: Dict,
    species_name: str,
    tree_index: int = 0,
) -> Dict:
    """
    Map Grove simulation data to PVE preset JSON format.

    Args:
        grove: Grove object after simulation
        template: Empty PVE template from create_pve_template_from_reference()
        species_name: Name of species
        tree_index: Index of tree in grove

    Returns:
        Filled PVE preset dictionary
    """
    import the_grove_22_core as gc

    # Get Grove properties and build models
    properties = grove.get_properties()

    # Build tree models to access geometry
    build_params = {
        "resolution": 16,
        "resolution_reduce": 0.8,
        "texture_repeat": 3,
        "build_cutoff_age": 0,
        "build_cutoff_thickness": 0.0,
        "build_blend": True,
        "build_end_cap": True,
    }
    models = grove.build_models(build_params)

    # Build skeleton for branch hierarchy
    skeletons = grove.build_skeletons()

    # Fill template with Grove data
    pve_data = template.copy()

    # Map global attributes
    pve_data["globalAttributes"] = _map_global_attributes(
        grove, properties, template["globalAttributes"]
    )

    # Map point data from skeleton
    if tree_index < len(skeletons):
        skeleton = skeletons[tree_index]
        pve_data["points"] = _map_points_from_skeleton(skeleton, template["points"])

    # Map primitives from skeleton poly_lines
    if tree_index < len(skeletons):
        skeleton = skeletons[tree_index]
        pve_data["primitives"] = _map_primitives_from_skeleton(
            skeleton, template["primitives"]
        )

    return pve_data


def _map_global_attributes(grove: Any, properties: Any, template: Dict) -> Dict:
    """
    Map Grove properties to PVE globalAttributes.

    Only fills values we can reliably extract from Grove, keeps empty arrays as-is.
    """
    import copy

    global_attrs = copy.deepcopy(template)

    # Map only the basic simulation parameters we have
    if "cycle" in global_attrs:
        global_attrs["cycle"]["value"] = getattr(properties, "simulation_steps", 30)

    if "cycleTime" in global_attrs:
        global_attrs["cycleTime"]["value"] = getattr(properties, "cycle_time", 1.25)

    if "gravitationalForce" in global_attrs:
        global_attrs["gravitationalForce"]["value"] = getattr(
            properties, "gravity", 2.0
        )

    if "randomSeed" in global_attrs:
        global_attrs["randomSeed"]["value"] = getattr(properties, "random_seed", 0)

    # For array parameters (curves), keep them empty if template has empty
    # Grove doesn't export these parameter curves, so preserve Hazel structure
    # Empty arrays will remain empty, matching Hazel behavior

    return global_attrs


def _map_points_from_skeleton(skeleton: Any, template: Dict) -> Dict:
    """
    Map Grove skeleton points to PVE points structure.

    Only fills position and core attributes, keeps other attributes empty like Hazel.
    """
    import copy

    points_data = {"attributes": copy.deepcopy(template["attributes"]), "positions": []}

    # Extract skeleton points (these are branch joints)
    skeleton_points = skeleton.points  # List of (x, y, z) tuples
    num_points = len(skeleton_points)

    # Get positions
    positions = [[p[0], p[1], p[2]] for p in skeleton_points]
    points_data["positions"] = positions

    # Fill only the essential point attributes that Grove provides

    # P (position as attribute - copy of positions, flattened)
    if "P" in points_data["attributes"]:
        p_flat = [coord for pos in positions for coord in pos]
        value_key = "values" if "values" in points_data["attributes"]["P"] else "value"
        points_data["attributes"]["P"][value_key] = p_flat

    # generation (branch hierarchy depth)
    if "generation" in points_data["attributes"]:
        generation = _calculate_generation_from_polylines(skeleton)
        value_key = (
            "values" if "values" in points_data["attributes"]["generation"] else "value"
        )
        points_data["attributes"]["generation"][value_key] = generation

    # pscale (point scale/radius)
    if "pscale" in points_data["attributes"]:
        pscales = list(skeleton.point_attribute_radius)
        value_key = (
            "values" if "values" in points_data["attributes"]["pscale"] else "value"
        )
        points_data["attributes"]["pscale"][value_key] = pscales

    # lengthFromRoot (cumulative distance from root)
    if "lengthFromRoot" in points_data["attributes"]:
        lengths = _calculate_length_from_root(skeleton)
        value_key = (
            "values"
            if "values" in points_data["attributes"]["lengthFromRoot"]
            else "value"
        )
        points_data["attributes"]["lengthFromRoot"][value_key] = lengths

    # branchGradient (normalized position along branch)
    if "branchGradient" in points_data["attributes"]:
        gradients = _calculate_branch_gradients(skeleton)
        value_key = (
            "values"
            if "values" in points_data["attributes"]["branchGradient"]
            else "value"
        )
        points_data["attributes"]["branchGradient"][value_key] = gradients

    # All other attributes (LOD, bud, UV, etc.) remain empty as in Hazel template

    return points_data


def _map_primitives_from_skeleton(skeleton: Any, template: Dict) -> Dict:
    """
    Map Grove skeleton poly_lines to PVE primitives (branch curves).

    Only fills core branch attributes, keeps other attributes empty like Hazel.
    """
    import copy

    primitives_data = {
        "attributes": copy.deepcopy(template["attributes"]),
        "points": [],
    }

    # Get poly_lines from skeleton
    poly_lines = skeleton.poly_lines  # List of lists of point indices
    num_poly_lines = len(poly_lines)

    # Each poly_line is a branch - add to points array
    for poly_line in poly_lines:
        point_indices = list(poly_line)
        primitives_data["points"].append(point_indices)

    # Fill only core branch attributes
    num_branches = num_poly_lines

    # branchNumber (sequential ID)
    if "branchNumber" in primitives_data["attributes"]:
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["branchNumber"]
            else "value"
        )
        primitives_data["attributes"]["branchNumber"][value_key] = list(
            range(num_branches)
        )

    # branchGeneration (depth in hierarchy)
    if "branchGeneration" in primitives_data["attributes"]:
        generations = _calculate_branch_generation(skeleton)
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["branchGeneration"]
            else "value"
        )
        primitives_data["attributes"]["branchGeneration"][value_key] = generations

    # branchParentNumber (parent branch index)
    if "branchParentNumber" in primitives_data["attributes"]:
        parents = _calculate_branch_parents(skeleton)
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["branchParentNumber"]
            else "value"
        )
        primitives_data["attributes"]["branchParentNumber"][value_key] = parents

    # plantNumber (all same tree)
    if "plantNumber" in primitives_data["attributes"]:
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["plantNumber"]
            else "value"
        )
        primitives_data["attributes"]["plantNumber"][value_key] = [0] * num_branches

    # All other attributes (compound, instancer, etc.) remain empty as in Hazel template

    return primitives_data


def _calculate_generation_from_polylines(skeleton: Any) -> List[int]:
    """
    Calculate generation (hierarchy depth) for each point based on poly_lines.

    Points in the main trunk poly_line are generation 0, branches from it are 1, etc.
    """
    num_points = len(skeleton.points)
    poly_lines = skeleton.poly_lines
    num_poly_lines = len(poly_lines)

    # Initialize all points to -1
    generation = [-1] * num_points

    # Assume first poly_line is main trunk (generation 0)
    if num_poly_lines > 0:
        main_trunk = poly_lines[0]
        for i in range(len(main_trunk)):
            generation[main_trunk[i]] = 0

    # Process remaining poly_lines
    for poly_idx in range(1, num_poly_lines):
        poly_line = poly_lines[poly_idx]
        if len(poly_line) > 0:
            # First point connects to parent, check its generation
            first_point = poly_line[0]
            parent_gen = generation[first_point] if first_point < len(generation) else 0

            # All points in this poly_line are parent_gen + 1
            for i in range(len(poly_line)):
                generation[poly_line[i]] = max(generation[poly_line[i]], parent_gen + 1)

    # Fill any remaining -1 with 0
    generation = [max(0, g) for g in generation]

    return generation


def _calculate_length_from_root(skeleton: Any) -> List[float]:
    """Calculate cumulative distance from root for each point."""
    skeleton_points = skeleton.points
    num_points = len(skeleton_points)
    lengths = [0.0] * num_points

    # Process each poly_line
    poly_lines = skeleton.poly_lines
    for poly_line in poly_lines:
        cumulative = 0.0
        for i in range(len(poly_line)):
            point_idx = poly_line[i]

            if i > 0:
                prev_idx = poly_line[i - 1]
                p1 = skeleton_points[prev_idx]
                p2 = skeleton_points[point_idx]

                # Euclidean distance
                dx = p2[0] - p1[0]
                dy = p2[1] - p1[1]
                dz = p2[2] - p1[2]
                distance = (dx * dx + dy * dy + dz * dz) ** 0.5

                cumulative += distance

            lengths[point_idx] = max(lengths[point_idx], cumulative)

    return lengths


def _calculate_branch_gradients(skeleton: Any) -> List[float]:
    """
    Calculate normalized position (0-1) along each branch for each point.
    """
    num_points = len(skeleton.points)
    gradients = [0.0] * num_points

    poly_lines = skeleton.poly_lines
    for poly_line in poly_lines:
        num_pts_in_branch = len(poly_line)

        if num_pts_in_branch > 1:
            for i in range(num_pts_in_branch):
                point_idx = poly_line[i]
                gradient = i / (num_pts_in_branch - 1)
                gradients[point_idx] = gradient
        else:
            # Single point branch
            if num_pts_in_branch == 1:
                gradients[poly_line[0]] = 0.0

    return gradients


def _calculate_branch_generation(skeleton: Any) -> List[int]:
    """
    Calculate generation (depth) for each branch primitive.

    Main trunk is 0, branches from it are 1, etc.
    """
    poly_lines = skeleton.poly_lines
    num_poly_lines = len(poly_lines)
    generations = [0] * num_poly_lines

    # First poly_line is main trunk (generation 0)
    if num_poly_lines > 0:
        generations[0] = 0

    # Calculate for remaining branches
    # Heuristic: branch connects to a point that already has a generation assigned
    point_to_generation = {}

    # Assign main trunk points to generation 0
    if num_poly_lines > 0:
        main_trunk = poly_lines[0]
        for i in range(len(main_trunk)):
            point_to_generation[main_trunk[i]] = 0

    # Process remaining poly_lines
    for poly_idx in range(1, num_poly_lines):
        poly_line = poly_lines[poly_idx]

        if len(poly_line) > 0:
            first_point = poly_line[0]

            # Check if this point already has a generation
            if first_point in point_to_generation:
                branch_gen = point_to_generation[first_point] + 1
            else:
                branch_gen = 1

            generations[poly_idx] = branch_gen

            # Update all points in this poly_line
            for i in range(len(poly_line)):
                point_to_generation[poly_line[i]] = branch_gen

    return generations


def _calculate_branch_parents(skeleton: Any) -> List[int]:
    """
    Calculate parent branch index for each branch.

    Returns -1 for root branch, parent index for others.
    """
    poly_lines = skeleton.poly_lines
    num_poly_lines = len(poly_lines)
    parents = [-1] * num_poly_lines

    # First poly_line is root (no parent)
    if num_poly_lines > 0:
        parents[0] = -1

    # Map points to their poly_line index
    point_to_poly = {}
    for poly_idx in range(num_poly_lines):
        poly_line = poly_lines[poly_idx]
        for i in range(len(poly_line)):
            point_idx = poly_line[i]
            if point_idx not in point_to_poly:
                point_to_poly[point_idx] = poly_idx

    # Find parent for each branch
    for poly_idx in range(1, num_poly_lines):
        poly_line = poly_lines[poly_idx]

        if len(poly_line) > 0:
            # First point should connect to parent branch
            first_point = poly_line[0]

            # Find which poly_line contains this point (other than current)
            parent_poly = -1
            for other_poly_idx in range(poly_idx):
                other_poly_line = poly_lines[other_poly_idx]
                if first_point in other_poly_line:
                    parent_poly = other_poly_idx
                    break

            parents[poly_idx] = parent_poly

    return parents


def generate_pve_from_grove(
    grove: Any,
    output_path: Path,
    species_name: str,
    tree_index: int = 0,
    verbose: bool = True,
) -> Dict:
    """
    Generate PVE preset JSON from Grove simulation using Hazel structure as template.

    Args:
        grove: Grove object after simulation
        output_path: Path to save generated JSON
        species_name: Name of species
        tree_index: Index of tree in grove
        verbose: Whether to print progress messages

    Returns:
        Generated PVE preset dictionary
    """
    # Load Hazel JSON as template
    if verbose:
        print(f"  Creating PVE preset from Grove data using Hazel template...")

    # Find Hazel reference file
    project_root = Path(__file__).parent.parent.parent.parent
    hazel_reference = (
        project_root / "data" / "megaplant" / "json" / "Broadleaf_Hazel_04.json"
    )

    if not hazel_reference.exists():
        if verbose:
            print(
                f"  Warning: Hazel reference not found at {hazel_reference}, using schema"
            )
        template = create_empty_pve_preset()
    else:
        template = create_pve_template_from_reference(hazel_reference)

    # Map Grove data to template
    pve_data = map_grove_to_pve(grove, template, species_name, tree_index)

    # Save to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(pve_data, f, indent=2)

    if verbose:
        print(f"  ✓ PVE preset: {output_path.name}")
    return pve_data
