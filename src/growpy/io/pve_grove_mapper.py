"""
Map Grove API data directly to PVE Preset JSON format.

This module extracts data from Grove simulations and maps it to the
Quixel Megaplants PVE format, avoiding Houdini entirely.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from ..config.pve_species_overrides import apply_species_overrides
from .pve_foliage_extractor import extract_foliage_data
from .pve_growth_defaults import get_default_growth_params, merge_growth_params
from .pve_hierarchy_builder import build_hierarchy_arrays
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
    """Create empty primitive attributes structure, preserving 'value' vs 'values' key."""
    empty = {}
    for key, value in reference.items():
        # Preserve the exact key name from reference (value vs values)
        value_key = "values" if "values" in value else "value"
        empty[key] = {
            "isArray": value.get("isArray", False),
            "size": value.get("size", 1),
            "type": value.get("type", "int"),
            value_key: [],
        }
    return empty


def map_grove_to_pve(
    grove: Any,
    template: Dict,
    species_name: str,
    tree_index: int = 0,
    model: Optional[Any] = None,
    skeleton: Optional[Any] = None,
    bones_info: Optional[List] = None,
    use_default_growth_params: bool = True,
    twig_density: float = 1.0,
    custom_growth_params: Optional[Dict] = None,
    pve_config_dir: Optional[Path] = None,
    verbose: bool = False,
) -> Dict:
    """
    Map Grove simulation data to PVE preset JSON format.

    CRITICAL: Uses pre-built model/skeleton/bones_info from export phase.
    No model rebuilding occurs - all data is extracted from already-built objects.

    Args:
        grove: Grove object after simulation
        template: Empty PVE template from create_pve_template_from_reference()
        species_name: Name of species
        tree_index: Index of tree in grove
        model: Pre-built model (with twigs) from export phase
        skeleton: Pre-built skeleton from export phase
        bones_info: Pre-built bones info from export phase
        use_default_growth_params: If True, use Hazel defaults for growth curves
        twig_density: Foliage density multiplier (0.0-1.0+)
        custom_growth_params: Optional dictionary to override specific parameters
        pve_config_dir: Optional directory for species PVE config files
        verbose: Print detailed information

    Returns:
        Filled PVE preset dictionary
    """
    import the_grove_22_core as gc

    # CRITICAL: Model must be provided from export phase with twigs already built
    if model is None:
        raise ValueError(
            "Model must be provided to generate_pve_from_grove - "
            "no model rebuilding occurs. Pass model from export phase."
        )

    # Get Grove properties
    properties = grove.get_properties()

    # Build skeleton for branch hierarchy (if not provided)
    if skeleton is None:
        skeletons = grove.build_skeletons()
        if tree_index < len(skeletons):
            skeleton = skeletons[tree_index]

    # Fill template with Grove data, ensuring all Hazel attributes are present
    import copy

    pve_data = copy.deepcopy(template)

    # Fill globalAttributes: Grove-fillable attributes get Grove values, others remain empty/default
    # CRITICAL: Preserve Hazel attribute order for Unreal PVE C++ parser compatibility
    filled_attrs = _map_global_attributes(
        grove,
        properties,
        template["globalAttributes"],
        skeleton,
        use_default_growth_params,
        custom_growth_params,
    )

    # Rebuild globalAttributes dict in template order to preserve Hazel ordering
    ordered_global_attrs = {}
    for key in template["globalAttributes"].keys():
        if key in filled_attrs:
            ordered_global_attrs[key] = filled_attrs[key]
        else:
            ordered_global_attrs[key] = template["globalAttributes"][key]

    pve_data["globalAttributes"] = ordered_global_attrs

    # Map point data from skeleton
    if skeleton is not None:
        pve_data["points"] = _map_points_from_skeleton(skeleton, template["points"])

    # Map primitives from skeleton poly_lines
    if skeleton is not None:
        num_branches = len(skeleton.poly_lines)
        pve_data["primitives"] = _map_primitives_from_skeleton(
            skeleton,
            template["primitives"],
            model,
            bones_info,
            species_name,
            num_branches,
        )

    # Apply species-specific overrides from config files
    pve_data = apply_species_overrides(
        pve_data, species_name, pve_config_dir, verbose=verbose
    )

    return pve_data


def _map_global_attributes(
    grove: Any,
    properties: Any,
    template: Dict,
    skeleton: Optional[Any] = None,
    use_default_growth_params: bool = True,
    custom_growth_params: Optional[Dict] = None,
) -> Dict:
    """
    Map Grove properties to PVE globalAttributes with default growth curves.

    Args:
        grove: Grove object
        properties: Grove properties
        template: Template global attributes
        skeleton: Optional pre-built skeleton to avoid redundant API calls
        use_default_growth_params: If True, use Hazel defaults
        custom_growth_params: Optional overrides

    Returns:
        Global attributes with populated growth curves
    """
    import copy

    global_attrs = copy.deepcopy(template)

    # Map basic simulation parameters from Grove
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

    # Fill growth parameter curves with defaults
    if use_default_growth_params:
        defaults = get_default_growth_params(use_hazel_defaults=True)

        # Merge defaults with custom overrides
        if custom_growth_params:
            defaults = merge_growth_params(defaults, custom_growth_params)

        # Apply to global_attrs
        for key, value in defaults.items():
            if key in global_attrs:
                global_attrs[key] = value

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

    # P (position as attribute - array of [x, y, z] arrays, NOT flattened)
    if "P" in points_data["attributes"]:
        # Keep as array of [x, y, z] arrays to match Hazel reference format
        value_key = "values" if "values" in points_data["attributes"]["P"] else "value"
        points_data["attributes"]["P"][value_key] = positions

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

    # Fill remaining attributes with skeleton data where available, otherwise defaults
    # PVE requires all point attributes to have per-point data (not empty arrays)

    # Try to extract additional skeleton attributes
    age_values = None
    if hasattr(skeleton, "point_attribute_age"):
        age_values = list(skeleton.point_attribute_age)

    for attr_name, attr_data in points_data["attributes"].items():
        value_key = "values" if "values" in attr_data else "value"

        # Skip attributes we already filled
        if attr_data[value_key]:
            continue

        # Map Grove skeleton attributes to PVE attributes where possible
        default_value = 0 if attr_data.get("type") == "int" else 0.0

        # Try to use real skeleton data for certain attributes
        if attr_name == "lengthFromSeed" and age_values:
            # Use age as proxy for length from seed (growth order)
            if attr_data.get("isArray", False):
                points_data["attributes"][attr_name][value_key] = [
                    [float(age)] for age in age_values
                ]
            else:
                points_data["attributes"][attr_name][value_key] = [
                    float(age) for age in age_values
                ]
        elif attr_name == "plantGradient" and age_values:
            # Normalize age to 0-1 for plant gradient
            max_age = max(age_values) if age_values else 1.0
            normalized = (
                [age / max_age for age in age_values]
                if max_age > 0
                else [0.0] * num_points
            )
            if attr_data.get("isArray", False):
                points_data["attributes"][attr_name][value_key] = [
                    [v] for v in normalized
                ]
            else:
                points_data["attributes"][attr_name][value_key] = normalized
        else:
            # Fill with default per-point values
            if attr_data.get("isArray", False):
                # Array attributes with size>1: variable-length arrays of size-element groups
                # e.g., budDirection with size=3 → [[0,0,0], [0,0,0], ...] or [[x,y,z, x,y,z, ...], ...]
                attr_size = attr_data.get("size", 1)
                if attr_data.get("type") == "int":
                    points_data["attributes"][attr_name][value_key] = [
                        [0] * attr_size for _ in range(num_points)
                    ]
                else:  # float
                    points_data["attributes"][attr_name][value_key] = [
                        [0.0] * attr_size for _ in range(num_points)
                    ]
            else:
                # Non-array attributes with size > 1: array of size-element arrays per point
                # e.g., uv_base with size=3 → [[0,0,0], [0,0,0], ...]
                attr_size = attr_data.get("size", 1)
                if attr_size > 1:
                    if attr_data.get("type") == "int":
                        points_data["attributes"][attr_name][value_key] = [
                            [0] * attr_size for _ in range(num_points)
                        ]
                    else:  # float
                        points_data["attributes"][attr_name][value_key] = [
                            [0.0] * attr_size for _ in range(num_points)
                        ]
                else:
                    # Scalar attributes: one value per point
                    if attr_data.get("type") == "int":
                        points_data["attributes"][attr_name][value_key] = [
                            0 for _ in range(num_points)
                        ]
                    else:  # float
                        points_data["attributes"][attr_name][value_key] = [
                            0.0 for _ in range(num_points)
                        ]

    return points_data


def _map_primitives_from_skeleton(
    skeleton: Any,
    template: Dict,
    model: Any,
    bones_info: List,
    species_name: str,
    num_branches: int,
) -> Dict:
    """
    Map Grove skeleton poly_lines to PVE primitives with foliage and hierarchy.

    Args:
        skeleton: Grove skeleton
        template: Template primitive attributes
        model: Grove model (with twigs) from export phase
        bones_info: Bones info from export phase
        species_name: Species name for twig naming
        num_branches: Number of branches

    Returns:
        Primitives data with foliage, hierarchy, and branch data
    """
    import copy

    primitives_data = {
        "attributes": copy.deepcopy(template["attributes"]),
        "points": [],
    }

    # Get poly_lines from skeleton
    poly_lines = skeleton.poly_lines
    num_poly_lines = len(poly_lines)

    # Each poly_line is a branch - add to points array
    for poly_line in poly_lines:
        point_indices = list(poly_line)
        primitives_data["points"].append(point_indices)

    # Fill core branch attributes
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
    if "branchGeneration" in primitives_data["attributes"] and model:
        from .pve_hierarchy_builder import get_branch_generation

        generations = get_branch_generation(model, num_branches)
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["branchGeneration"]
            else "value"
        )
        primitives_data["attributes"]["branchGeneration"][value_key] = generations

    # branchParentNumber (parent branch index)
    if "branchParentNumber" in primitives_data["attributes"] and model:
        parents = _calculate_branch_parents_from_model(model, num_branches)
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

    # Add parent/child hierarchy arrays from model face attributes
    hierarchy = build_hierarchy_arrays(model, num_branches)
    if "parents" in primitives_data["attributes"]:
        primitives_data["attributes"]["parents"] = hierarchy["parents"]
    if "children" in primitives_data["attributes"]:
        primitives_data["attributes"]["children"] = hierarchy["children"]

    # Populate remaining required attributes to avoid array index errors in Unreal
    # branchHierarchyNumber: Use same as branchGeneration
    if "branchHierarchyNumber" in primitives_data["attributes"]:
        if "branchGeneration" in primitives_data["attributes"]:
            gen_key = (
                "values"
                if "values" in primitives_data["attributes"]["branchGeneration"]
                else "value"
            )
            generations = primitives_data["attributes"]["branchGeneration"][gen_key]
        else:
            generations = [0] * num_branches
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["branchHierarchyNumber"]
            else "value"
        )
        primitives_data["attributes"]["branchHierarchyNumber"][value_key] = generations

    # branchSourceBudNumber: Not available in Grove data, use 0
    if "branchSourceBudNumber" in primitives_data["attributes"]:
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["branchSourceBudNumber"]
            else "value"
        )
        primitives_data["attributes"]["branchSourceBudNumber"][value_key] = [
            0
        ] * num_branches

    # compoundBranchGeneration: Use same as branchGeneration
    if "compoundBranchGeneration" in primitives_data["attributes"]:
        if "branchGeneration" in primitives_data["attributes"]:
            gen_key = (
                "values"
                if "values" in primitives_data["attributes"]["branchGeneration"]
                else "value"
            )
            generations = primitives_data["attributes"]["branchGeneration"][gen_key]
        else:
            generations = [0] * num_branches
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["compoundBranchGeneration"]
            else "value"
        )
        primitives_data["attributes"]["compoundBranchGeneration"][
            value_key
        ] = generations

    # compoundBranchNumber: Sequential numbering
    if "compoundBranchNumber" in primitives_data["attributes"]:
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["compoundBranchNumber"]
            else "value"
        )
        primitives_data["attributes"]["compoundBranchNumber"][value_key] = list(
            range(num_branches)
        )

    # compoundBranchParentNumber: Use same as branchParentNumber
    if "compoundBranchParentNumber" in primitives_data["attributes"]:
        if "branchParentNumber" in primitives_data["attributes"]:
            parent_key = (
                "values"
                if "values" in primitives_data["attributes"]["branchParentNumber"]
                else "value"
            )
            parents = primitives_data["attributes"]["branchParentNumber"][parent_key]
        else:
            parents = [0] * num_branches
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["compoundBranchParentNumber"]
            else "value"
        )
        primitives_data["attributes"]["compoundBranchParentNumber"][value_key] = parents

    # pivotPointLocation: First point position of each branch
    if "pivotPointLocation" in primitives_data["attributes"] and skeleton:
        from .pve_foliage_extractor import grove_to_pve_position

        pivot_locations = []
        for poly_line in poly_lines:
            if len(poly_line) > 0:
                first_point_idx = poly_line[0]
                if first_point_idx < len(skeleton.points):
                    pos = skeleton.points[first_point_idx]
                    # Convert to PVE coordinates
                    pve_pos = grove_to_pve_position(pos)
                    pivot_locations.append(list(pve_pos))
                else:
                    pivot_locations.append([0.0, 0.0, 0.0])
            else:
                pivot_locations.append([0.0, 0.0, 0.0])
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["pivotPointLocation"]
            else "value"
        )
        primitives_data["attributes"]["pivotPointLocation"][value_key] = pivot_locations

    # shop_materialpath: Use default material path for species
    if "shop_materialpath" in primitives_data["attributes"]:
        material_path = f"/obj/_Datasource/{species_name.replace(' ', '_')}_Trunkmat/Import_Mat_Net/2_0_Material"
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["shop_materialpath"]
            else "value"
        )
        primitives_data["attributes"]["shop_materialpath"][value_key] = [
            material_path
        ] * num_branches

    # Extract foliage/twig instancer data from pre-built model
    # CRITICAL: Pass bones_info for correct branch_id assignment
    foliage_data = extract_foliage_data(
        model, species_name, bones_info=bones_info, verbose=False
    )

    # Merge foliage data into primitives attributes
    for key, value in foliage_data.items():
        if key in primitives_data["attributes"]:
            primitives_data["attributes"][key] = value

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


def _calculate_branch_parents_from_model(model: Any, num_branches: int) -> List[int]:
    """
    Calculate parent branch index for each branch using model face attributes.

    Args:
        model: Grove model with face_attribute_branch_id and face_attribute_branch_id_parent
        num_branches: Total number of branches

    Returns:
        List of parent indices per branch (-1 for root)
    """
    # Extract branch parent relationships from model face attributes
    branch_ids = model.face_attribute_branch_id
    parent_branch_ids = model.face_attribute_branch_id_parent

    # Build branch->parent mapping
    branch_to_parent = {}
    for branch_id, parent_id in zip(branch_ids, parent_branch_ids):
        if branch_id not in branch_to_parent:
            branch_to_parent[branch_id] = parent_id

    # Build parents list
    parents = []
    for branch_idx in range(num_branches):
        parent_idx = branch_to_parent.get(branch_idx, -1)
        parents.append(parent_idx)

    return parents


def generate_pve_from_grove(
    grove: Any,
    output_path: Path,
    species_name: str,
    tree_index: int = 0,
    model: Optional[Any] = None,
    skeleton: Optional[Any] = None,
    bones_info: Optional[List] = None,
    verbose: bool = True,
    use_default_growth_params: bool = True,
    twig_density: float = 1.0,
    custom_growth_params: Optional[Dict] = None,
    pve_config_dir: Optional[Path] = None,
) -> Dict:
    """
    Generate PVE preset JSON from Grove simulation with full foliage and hierarchy.

    CRITICAL: Pass model/skeleton/bones_info from main export phase to avoid rebuilding.
    The model must have twigs already built for foliage extraction to work.

    Args:
        grove: Grove object after simulation
        output_path: Path to save generated JSON
        species_name: Name of species
        tree_index: Index of tree in grove
        model: Pre-built model (with twigs) from export phase - REQUIRED
        skeleton: Pre-built skeleton from export phase - REQUIRED
        bones_info: Pre-built bones info from export phase - REQUIRED
        verbose: Whether to print progress messages
        use_default_growth_params: If True, use Hazel defaults for growth curves
        twig_density: Foliage density multiplier (0.0-1.0+)
        custom_growth_params: Optional dictionary to override specific parameters
        pve_config_dir: Optional directory for species PVE config files

    Returns:
        Generated PVE preset dictionary
    """
    # Load Hazel JSON as template
    if verbose:
        print(f"  Creating PVE preset from Grove data with foliage...")

    # Find Hazel reference file
    project_root = Path(__file__).parent.parent.parent.parent
    hazel_reference = (
        project_root
        / "data"
        / "tmp"
        / "ProceduralVegetationEditor"
        / "Content"
        / "SampleAssets"
        / "Tree_Common_Hazel_01"
        / "Instances"
        / "Broadleaf_Hazel_04.json"
    )

    if not hazel_reference.exists():
        if verbose:
            print(
                f"  Warning: Hazel reference not found at {hazel_reference}, using schema"
            )
        template = create_empty_pve_preset()
    else:
        template = create_pve_template_from_reference(hazel_reference)

    # Map Grove data to template with all features
    pve_data = map_grove_to_pve(
        grove,
        template,
        species_name,
        tree_index,
        model=model,
        skeleton=skeleton,
        bones_info=bones_info,
        use_default_growth_params=use_default_growth_params,
        twig_density=twig_density,
        custom_growth_params=custom_growth_params,
        pve_config_dir=pve_config_dir,
        verbose=verbose,
    )

    # Save to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(pve_data, f, indent=2)

    if verbose:
        print(f"  [OK] PVE preset with foliage: {output_path.name}")
    return pve_data
