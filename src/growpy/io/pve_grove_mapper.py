"""
Map Grove API data directly to PVE Preset JSON format.

This module extracts data from Grove simulations and maps it to the
Quixel Megaplants PVE format, avoiding Houdini entirely.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    profile: bool = False,
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

    timings = {} if profile else None

    # CRITICAL: Model must be provided from export phase with twigs already built
    if model is None:
        raise ValueError(
            "Model must be provided to generate_pve_from_grove - "
            "no model rebuilding occurs. Pass model from export phase."
        )

    # Get Grove properties
    t0 = time.perf_counter() if profile else 0
    properties = grove.get_properties()
    if profile:
        timings["get_properties"] = time.perf_counter() - t0

    # Build skeleton for branch hierarchy (if not provided)
    t0 = time.perf_counter() if profile else 0
    if skeleton is None:
        skeletons = grove.build_skeletons()
        if tree_index < len(skeletons):
            skeleton = skeletons[tree_index]
    if profile:
        timings["build_skeleton"] = time.perf_counter() - t0

    # Fill template with Grove data, ensuring all Hazel attributes are present
    import copy

    t0 = time.perf_counter() if profile else 0
    pve_data = copy.deepcopy(template)
    if profile:
        timings["copy_template"] = time.perf_counter() - t0

    # Fill globalAttributes: Grove-fillable attributes get Grove values, others remain empty/default
    # CRITICAL: Preserve Hazel attribute order for Unreal PVE C++ parser compatibility
    t0 = time.perf_counter() if profile else 0
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
    if profile:
        timings["map_global_attrs"] = time.perf_counter() - t0

    # Map point data from skeleton
    t0 = time.perf_counter() if profile else 0
    if skeleton is not None:
        pve_data["points"] = _map_points_from_skeleton(skeleton, template["points"])
    if profile:
        timings["map_points"] = time.perf_counter() - t0

    # Map primitives from skeleton poly_lines
    t0 = time.perf_counter() if profile else 0
    if skeleton is not None:
        num_branches = len(skeleton.poly_lines)
        pve_data["primitives"] = _map_primitives_from_skeleton(
            skeleton,
            template["primitives"],
            model,
            bones_info,
            species_name,
            num_branches,
            profile=profile,
        )
    if profile:
        timings["map_primitives"] = time.perf_counter() - t0

    # Apply species-specific overrides from config files
    t0 = time.perf_counter() if profile else 0
    pve_data = apply_species_overrides(
        pve_data, species_name, pve_config_dir, verbose=verbose
    )
    if profile:
        timings["apply_overrides"] = time.perf_counter() - t0

    if profile and verbose:
        total = sum(timings.values())
        print(f"    map_grove_to_pve breakdown ({total:.3f}s):")
        for step, elapsed in sorted(timings.items(), key=lambda x: -x[1]):
            pct = (elapsed / total * 100) if total > 0 else 0
            print(f"      {step}: {elapsed:.3f}s ({pct:.1f}%)")

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

    Converts from Grove coordinate system (Z-up, world coords) to PVE format (Y-up, local coords).
    Only fills position and core attributes, keeps other attributes empty like Hazel.
    """
    import copy

    points_data = {"attributes": copy.deepcopy(template["attributes"]), "positions": []}

    # CRITICAL: PVE bud attribute inner array sizes from Hazel reference
    # These are per-point arrays containing data for multiple buds
    # The "size" field in schema is metadata, not the actual array length
    BUD_ATTR_INNER_SIZES = {
        "budDirection": 18,  # 6 buds x 3 floats (xyz direction per bud)
        "budHormoneLevels": 6,  # Per-bud hormone levels
        "budLateralMeristem": 7,  # Per-bud lateral meristem data
        "budLightDetected": 4,  # Per-bud light detection
        "budStatus": 10,  # Per-bud status flags
        "budDevelopment": 6,  # Per-bud development: [gen, cycle, age, 0, 0, max_age]
    }

    # Extract skeleton points (these are branch joints)
    skeleton_points = skeleton.points  # List of (x, y, z) tuples in Grove coords (Z-up)
    num_points = len(skeleton_points)

    if num_points == 0:
        points_data["positions"] = []
        return points_data

    # Find tree origin (first point - base of trunk) for world-to-local conversion
    # Grove stores points in world coordinates, PVE expects local coordinates
    origin = skeleton_points[0]
    origin_x, origin_y, origin_z = origin[0], origin[1], origin[2]

    # Convert positions:
    # 1. Subtract origin (world to local)
    # 2. Swap Y and Z axes (Grove Z-up to PVE Y-up)
    # Grove: (X, Y, Z) where Z is up
    # PVE:   (X, Z, Y) where Y is up (swap Y<->Z)
    positions = []
    for p in skeleton_points:
        local_x = p[0] - origin_x
        local_y = p[1] - origin_y
        local_z = p[2] - origin_z
        # Swap Y and Z for PVE Y-up coordinate system
        positions.append([local_x, local_z, local_y])

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

    # Get generation values if already computed
    generation_values = None
    if "generation" in points_data["attributes"]:
        gen_value_key = (
            "values" if "values" in points_data["attributes"]["generation"] else "value"
        )
        generation_values = points_data["attributes"]["generation"].get(gen_value_key)

    # budDevelopment requires 6-element arrays per point for PVMaterialSettings
    # Structure: [generation, cycle, age, 0, 0, max_age]
    # PVMaterialSettings.cpp accesses: BudDevelopment[0]=generation, BudDevelopment[2]=age
    if "budDevelopment" in points_data["attributes"]:
        value_key = (
            "values"
            if "values" in points_data["attributes"]["budDevelopment"]
            else "value"
        )
        # Get max cycle/age for the tree
        max_age = max(age_values) if age_values else num_points
        bud_development_data = []
        for i in range(num_points):
            gen = generation_values[i] if generation_values else 0
            age = age_values[i] if age_values else i
            # 6-element array: [generation, cycle, age, 0, 0, max_age]
            bud_development_data.append(
                [int(gen), int(max_age), int(age), 0, 0, int(max_age)]
            )
        points_data["attributes"]["budDevelopment"][value_key] = bud_development_data

    # budDirection - Calculate from skeleton poly_lines
    if "budDirection" in points_data["attributes"]:
        bud_directions = _calculate_bud_directions(skeleton)
        value_key = (
            "values"
            if "values" in points_data["attributes"]["budDirection"]
            else "value"
        )
        points_data["attributes"]["budDirection"][value_key] = bud_directions

    # budNumber - Assign sequential IDs
    if "budNumber" in points_data["attributes"]:
        bud_numbers = list(range(1, num_points + 1))  # Start from 1
        value_key = (
            "values" if "values" in points_data["attributes"]["budNumber"] else "value"
        )
        points_data["attributes"]["budNumber"][value_key] = bud_numbers

    # LOD gradients - Calculate from pscale and age
    if age_values and "pscale" in points_data["attributes"]:
        pscale_key = (
            "values" if "values" in points_data["attributes"]["pscale"] else "value"
        )
        pscales = points_data["attributes"]["pscale"][pscale_key]

        lod_gradients = _calculate_lod_gradients(skeleton, pscales, age_values)

        # Populate each LOD gradient attribute
        for lod_name, lod_values in lod_gradients.items():
            if lod_name in points_data["attributes"]:
                value_key = (
                    "values"
                    if "values" in points_data["attributes"][lod_name]
                    else "value"
                )
                points_data["attributes"][lod_name][value_key] = lod_values

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
            # CRITICAL: Use BUD_ATTR_INNER_SIZES for bud attributes, not schema "size"
            if attr_name in BUD_ATTR_INNER_SIZES:
                inner_size = BUD_ATTR_INNER_SIZES[attr_name]
                if attr_data.get("type") == "int":
                    points_data["attributes"][attr_name][value_key] = [
                        [0] * inner_size for _ in range(num_points)
                    ]
                else:  # float
                    points_data["attributes"][attr_name][value_key] = [
                        [0.0] * inner_size for _ in range(num_points)
                    ]
            elif attr_data.get("isArray", False):
                # Array attributes with size>1: variable-length arrays of size-element groups
                # e.g., budDirection with size=3 -> [[0,0,0], [0,0,0], ...] or [[x,y,z, x,y,z, ...], ...]
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
                # e.g., uv_base with size=3 -> [[0,0,0], [0,0,0], ...]
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
    profile: bool = False,
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
        profile: Enable timing output

    Returns:
        Primitives data with foliage, hierarchy, and branch data
    """
    import copy

    timings = {} if profile else None
    total_start = time.perf_counter() if profile else 0

    t0 = time.perf_counter() if profile else 0
    primitives_data = {
        "attributes": copy.deepcopy(template["attributes"]),
        "points": [],
    }
    if profile:
        timings["copy_template"] = time.perf_counter() - t0

    # Get poly_lines from skeleton
    poly_lines = skeleton.poly_lines
    num_poly_lines = len(poly_lines)

    # CRITICAL: Rebase poly_line indices to start at 0
    # Grove skeleton poly_lines use global indices across all skeletons in the grove.
    # When exporting a single skeleton, its points array is 0-indexed, but poly_lines
    # may start at a non-zero index (e.g., if there are other skeletons before this one).
    # We must subtract the minimum index to make poly_line indices match points array.
    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0

    # Each poly_line is a branch - add rebased indices to points array
    for poly_line in poly_lines:
        point_indices = [idx - index_offset for idx in poly_line]
        primitives_data["points"].append(point_indices)
    if profile:
        timings["setup_polylines"] = time.perf_counter() - t0

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
    t0 = time.perf_counter() if profile else 0
    if "branchGeneration" in primitives_data["attributes"] and model:
        from .pve_hierarchy_builder import get_branch_generation

        generations = get_branch_generation(model, num_branches, skeleton)
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["branchGeneration"]
            else "value"
        )
        primitives_data["attributes"]["branchGeneration"][value_key] = generations
    if profile:
        timings["branch_generation"] = time.perf_counter() - t0

    # branchParentNumber (parent branch index) - use skeleton for accurate hierarchy
    t0 = time.perf_counter() if profile else 0
    if "branchParentNumber" in primitives_data["attributes"]:
        parents = _calculate_branch_parents_from_skeleton(skeleton, num_branches)
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["branchParentNumber"]
            else "value"
        )
        primitives_data["attributes"]["branchParentNumber"][value_key] = parents
    if profile:
        timings["branch_parents"] = time.perf_counter() - t0

    # plantNumber (all same tree)
    if "plantNumber" in primitives_data["attributes"]:
        value_key = (
            "values"
            if "values" in primitives_data["attributes"]["plantNumber"]
            else "value"
        )
        primitives_data["attributes"]["plantNumber"][value_key] = [0] * num_branches

    # Add parent/child hierarchy arrays from skeleton poly_line connectivity
    t0 = time.perf_counter() if profile else 0
    hierarchy = build_hierarchy_arrays(model, num_branches, skeleton)
    if "parents" in primitives_data["attributes"]:
        primitives_data["attributes"]["parents"] = hierarchy["parents"]
    if "children" in primitives_data["attributes"]:
        primitives_data["attributes"]["children"] = hierarchy["children"]
    if profile:
        timings["hierarchy_arrays"] = time.perf_counter() - t0

    # Populate remaining required attributes to avoid array index errors in Unreal
    t0 = time.perf_counter() if profile else 0
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
    if profile:
        timings["populate_attrs"] = time.perf_counter() - t0

    # pivotPointLocation: First point position of each branch
    t0 = time.perf_counter() if profile else 0
    if "pivotPointLocation" in primitives_data["attributes"] and skeleton:
        # Pre-fetch all skeleton points for fast access (avoiding repeated attribute lookup)
        skel_points = skeleton.points
        num_skel_points = len(skel_points)

        pivot_locations = []
        for poly_line in poly_lines:
            if len(poly_line) > 0:
                first_point_idx = poly_line[0]
                if first_point_idx < num_skel_points:
                    pos = skel_points[first_point_idx]
                    # Inline coordinate conversion (Grove Z-up meters -> PVE Y-up centimeters)
                    pivot_locations.append(
                        [pos[0] * 100.0, pos[2] * 100.0, pos[1] * 100.0]
                    )
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
    if profile:
        timings["pivot_locations"] = time.perf_counter() - t0

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
    # CRITICAL: Pass num_branches from skeleton (poly_lines count), not from model branch IDs
    t0 = time.perf_counter() if profile else 0
    foliage_data = extract_foliage_data(
        model,
        species_name,
        bones_info=bones_info,
        num_branches=num_branches,
        verbose=False,
        profile=profile,
    )
    if profile:
        timings["extract_foliage"] = time.perf_counter() - t0

    # Merge foliage data into primitives attributes
    for key, value in foliage_data.items():
        if key in primitives_data["attributes"]:
            primitives_data["attributes"][key] = value

    if profile:
        total_elapsed = time.perf_counter() - total_start
        accounted = sum(timings.values())
        unaccounted = total_elapsed - accounted
        if unaccounted > 0.001:
            timings["other_untracked"] = unaccounted
        print(
            f"      _map_primitives_from_skeleton breakdown ({total_elapsed:.3f}s total):"
        )
        for step, elapsed in sorted(timings.items(), key=lambda x: -x[1]):
            pct = (elapsed / total_elapsed * 100) if total_elapsed > 0 else 0
            print(f"        {step}: {elapsed:.3f}s ({pct:.1f}%)")

    return primitives_data


def _calculate_generation_from_polylines(skeleton: Any) -> List[int]:
    """
    Calculate generation (hierarchy depth) for each point based on poly_lines.

    Points in the main trunk poly_line are generation 0, branches from it are 1, etc.
    """
    num_points = len(skeleton.points)
    poly_lines = skeleton.poly_lines
    num_poly_lines = len(poly_lines)

    if num_poly_lines == 0:
        return [0] * num_points

    # Calculate index offset for rebasing (poly_lines use global indices)
    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0

    # Initialize generation array for rebased indices
    generation = [-1] * num_points

    # Assume first poly_line is main trunk (generation 0)
    main_trunk = poly_lines[0]
    for pt_idx in main_trunk:
        rebased_idx = pt_idx - index_offset
        if 0 <= rebased_idx < num_points:
            generation[rebased_idx] = 0

    # Process remaining poly_lines
    for poly_idx in range(1, num_poly_lines):
        poly_line = poly_lines[poly_idx]
        if len(poly_line) > 0:
            # First point connects to parent, check its generation
            first_point = poly_line[0]
            rebased_first = first_point - index_offset
            parent_gen = (
                generation[rebased_first] if 0 <= rebased_first < num_points else 0
            )

            # All points in this poly_line are parent_gen + 1
            for pt_idx in poly_line:
                rebased_idx = pt_idx - index_offset
                if 0 <= rebased_idx < num_points:
                    generation[rebased_idx] = max(
                        generation[rebased_idx], parent_gen + 1
                    )

    # Fill any remaining -1 with 0
    return [max(0, g) for g in generation]


def _calculate_length_from_root(skeleton: Any) -> List[float]:
    """Calculate cumulative distance from root for each point."""
    skeleton_points = skeleton.points
    num_points = len(skeleton_points)
    poly_lines = skeleton.poly_lines

    if not poly_lines:
        return [0.0] * num_points

    # Calculate index offset for rebasing (poly_lines use global indices)
    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0

    lengths = [0.0] * num_points

    # Process each poly_line with rebased indices
    for poly_line in poly_lines:
        cumulative = 0.0
        for i in range(len(poly_line)):
            point_idx = poly_line[i]
            rebased_idx = point_idx - index_offset

            if i > 0:
                prev_idx = poly_line[i - 1]
                rebased_prev = prev_idx - index_offset
                # Bounds check for skeleton_points access with rebased indices
                if 0 <= rebased_prev < num_points and 0 <= rebased_idx < num_points:
                    p1 = skeleton_points[rebased_prev]
                    p2 = skeleton_points[rebased_idx]

                    # Euclidean distance
                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    dz = p2[2] - p1[2]
                    distance = (dx * dx + dy * dy + dz * dz) ** 0.5

                    cumulative += distance

            if 0 <= rebased_idx < num_points:
                lengths[rebased_idx] = max(lengths[rebased_idx], cumulative)

    return lengths


def _calculate_branch_gradients(skeleton: Any) -> List[float]:
    """
    Calculate normalized position (0-1) along each branch for each point.
    """
    num_points = len(skeleton.points)
    poly_lines = skeleton.poly_lines

    if not poly_lines:
        return [0.0] * num_points

    # Calculate index offset for rebasing (poly_lines use global indices)
    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0

    gradients = [0.0] * num_points

    for poly_line in poly_lines:
        num_pts_in_branch = len(poly_line)

        if num_pts_in_branch > 1:
            for i in range(num_pts_in_branch):
                point_idx = poly_line[i]
                rebased_idx = point_idx - index_offset
                gradient = i / (num_pts_in_branch - 1)
                if 0 <= rebased_idx < num_points:
                    gradients[rebased_idx] = gradient
        elif num_pts_in_branch == 1:
            # Single point branch
            point_idx = poly_line[0]
            rebased_idx = point_idx - index_offset
            if 0 <= rebased_idx < num_points:
                gradients[rebased_idx] = 0.0

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


def _calculate_branch_parents_from_skeleton(
    skeleton: Any, num_branches: int
) -> List[int]:
    """
    Calculate parent branch index for each branch using skeleton poly_line connectivity.

    PVE format: Root branch (0) has parent 0 (self-reference), not -1.

    Uses skeleton (not model) because model only has faces for branches passing cutoff.

    Args:
        skeleton: Grove skeleton with poly_lines
        num_branches: Total number of branches

    Returns:
        List of parent indices per branch (self-reference for roots)
    """
    from .pve_hierarchy_builder import _derive_parents_from_skeleton

    immediate_parents = _derive_parents_from_skeleton(skeleton)

    # Convert to PVE format: -1 becomes self-reference
    parents = []
    for branch_idx in range(num_branches):
        if branch_idx < len(immediate_parents):
            parent = immediate_parents[branch_idx]
            if parent == -1:
                # Root - use self-reference for PVE format
                parents.append(branch_idx)
            else:
                parents.append(parent)
        else:
            parents.append(branch_idx)

    return parents


def _calculate_branch_parents_from_model(model: Any, num_branches: int) -> List[int]:
    """
    DEPRECATED: Calculate parent branch index for each branch using model face attributes.

    NOTE: This function uses model.face_attribute_branch_id which only contains
    branches passing cutoff. Use _calculate_branch_parents_from_skeleton instead.

    PVE format: Root branch (0) has parent 0 (self-reference), not -1.

    Args:
        model: Grove model with face_attribute_branch_id and face_attribute_branch_id_parent
        num_branches: Total number of branches (from skeleton poly_lines)

    Returns:
        List of parent indices per branch (0 for root = self-reference)
    """
    # Extract branch parent relationships from model face attributes
    branch_ids = model.face_attribute_branch_id
    parent_branch_ids = model.face_attribute_branch_id_parent

    # Build branch->parent mapping using raw branch IDs
    branch_to_parent_raw = {}
    for branch_id, parent_id in zip(branch_ids, parent_branch_ids):
        if branch_id not in branch_to_parent_raw:
            branch_to_parent_raw[branch_id] = parent_id

    # Build remapping from model branch IDs to skeleton indices (0 to num_branches-1)
    unique_branch_ids = sorted(set(branch_ids))
    branch_id_to_idx = {bid: idx for idx, bid in enumerate(unique_branch_ids)}

    # Build parents list
    parents = []
    for branch_idx in range(num_branches):
        # Get original branch ID for this index
        if branch_idx < len(unique_branch_ids):
            original_branch_id = unique_branch_ids[branch_idx]
            parent_raw = branch_to_parent_raw.get(original_branch_id, -1)

            # Remap parent to index
            if parent_raw == -1 or parent_raw not in branch_id_to_idx:
                # Root branch - use self-reference (branch_idx) for PVE format
                parent_idx = branch_idx
            else:
                parent_idx = branch_id_to_idx[parent_raw]
        else:
            # Fallback - use self-reference
            parent_idx = branch_idx

        parents.append(parent_idx)

    return parents


def _calculate_bud_directions(skeleton: Any) -> List[List[float]]:
    """
    Calculate bud direction vectors from skeleton poly_lines.

    Each point gets up to 6 bud direction vectors (18 floats total).
    Directions are computed from point-to-point connections in poly_lines.

    Args:
        skeleton: Grove skeleton with points and poly_lines

    Returns:
        List of 18-float arrays (6 buds × 3D vector) per point
    """
    import math

    skeleton_points = skeleton.points
    num_points = len(skeleton_points)
    poly_lines = skeleton.poly_lines

    if not poly_lines:
        return [[0.0] * 18 for _ in range(num_points)]

    # Calculate index offset for rebasing
    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0

    # Initialize with zero vectors (6 buds per point, 3 floats per bud)
    bud_directions = [[0.0] * 18 for _ in range(num_points)]

    # Build a map from point index to all poly_lines it belongs to
    point_to_polylines = {}
    for pl_idx, poly_line in enumerate(poly_lines):
        for pt_idx in poly_line:
            rebased_idx = pt_idx - index_offset
            if rebased_idx not in point_to_polylines:
                point_to_polylines[rebased_idx] = []
            point_to_polylines[rebased_idx].append((pl_idx, poly_line))

    # Calculate direction vectors for each point
    for point_idx in range(num_points):
        if point_idx not in point_to_polylines:
            continue

        directions = []

        # For each poly_line containing this point
        for pl_idx, poly_line in point_to_polylines[point_idx]:
            # Find this point's position in the poly_line
            global_idx = point_idx + index_offset
            if global_idx not in poly_line:
                continue

            pos_in_line = poly_line.index(global_idx)

            # Calculate forward direction (to next point)
            if pos_in_line < len(poly_line) - 1:
                next_global_idx = poly_line[pos_in_line + 1]
                next_idx = next_global_idx - index_offset

                if 0 <= next_idx < num_points:
                    p1 = skeleton_points[point_idx]
                    p2 = skeleton_points[next_idx]

                    # Calculate direction vector (Grove Z-up coords)
                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    dz = p2[2] - p1[2]

                    # Normalize
                    length = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if length > 0.0001:
                        dx /= length
                        dy /= length
                        dz /= length

                        # Convert to PVE Y-up coords (swap Y and Z)
                        # Grove: (X, Y, Z) where Z is up
                        # PVE:   (X, Z, Y) where Y is up
                        pve_x = dx
                        pve_y = dz  # Grove Z becomes PVE Y
                        pve_z = dy  # Grove Y becomes PVE Z

                        directions.extend([pve_x, pve_y, pve_z])

        # Fill bud_directions array (up to 6 buds = 18 floats)
        for i in range(min(len(directions), 18)):
            bud_directions[point_idx][i] = directions[i]

        # If we have fewer than 6 buds worth of directions, pad with zeros
        # (already initialized to zeros, so no action needed)

    return bud_directions


def _calculate_lod_gradients(
    skeleton: Any, pscales: List[float], age_values: List[int]
) -> Dict[str, List[float]]:
    """
    Calculate LOD (Level of Detail) gradient values from skeleton data.

    PVE uses these gradients to control mesh density and material properties.
    Gradients range from ~1.0 at base to ~0.0 at tips.

    Args:
        skeleton: Grove skeleton
        pscales: Point scale (radius) values
        age_values: Point age values

    Returns:
        Dictionary with LOD gradient arrays
    """
    num_points = len(skeleton.points)

    if not pscales or not age_values:
        # Fallback if data is missing
        return {
            "LOD_totalPscaleGradient": [0.0] * num_points,
            "LOD_plantPscaleGradient": [0.0] * num_points,
            "LOD_branchPscaleGradient": [0.0] * num_points,
            "LOD_groundGradient": [0.0] * num_points,
            "LOD_hullGradient": [0.0] * num_points,
            "LOD_mainTrunkGradient": [0.0] * num_points,
            "LOD_canopyGradient": [0.0] * num_points,
        }

    # Calculate max values for normalization
    max_pscale = max(pscales) if pscales else 1.0
    max_age = max(age_values) if age_values else 1.0

    # Avoid division by zero
    if max_pscale < 0.0001:
        max_pscale = 1.0
    if max_age < 0.0001:
        max_age = 1.0

    # LOD_totalPscaleGradient: Based on pscale ratio (thick = high, thin = low)
    # Range from ~1.0 at base to ~0.0 at tips
    lod_total_pscale_gradient = [pscale / max_pscale for pscale in pscales]

    # LOD_plantPscaleGradient: Similar to total, but inverted age contribution
    # Older points (closer to base) have higher values
    lod_plant_pscale_gradient = [
        pscales[i] / max_pscale * (1.0 - age_values[i] / max_age)
        for i in range(num_points)
    ]

    # LOD_branchPscaleGradient: Per-branch thickness gradient
    lod_branch_pscale_gradient = [pscale / max_pscale for pscale in pscales]

    # LOD_groundGradient: Proximity to ground (inverse age)
    lod_ground_gradient = [1.0 - age / max_age for age in age_values]

    # LOD_hullGradient: Tree envelope/silhouette (based on pscale)
    lod_hull_gradient = [pscale / max_pscale for pscale in pscales]

    # LOD_mainTrunkGradient: Main trunk identification (highest pscale points)
    # Threshold: consider points with pscale > 50% of max as main trunk
    trunk_threshold = max_pscale * 0.5
    lod_main_trunk_gradient = [
        1.0 if pscale >= trunk_threshold else 0.0 for pscale in pscales
    ]

    # LOD_canopyGradient: Canopy/crown region (younger, thinner branches)
    # Inverse of ground gradient
    lod_canopy_gradient = [age / max_age for age in age_values]

    return {
        "LOD_totalPscaleGradient": lod_total_pscale_gradient,
        "LOD_plantPscaleGradient": lod_plant_pscale_gradient,
        "LOD_branchPscaleGradient": lod_branch_pscale_gradient,
        "LOD_groundGradient": lod_ground_gradient,
        "LOD_hullGradient": lod_hull_gradient,
        "LOD_mainTrunkGradient": lod_main_trunk_gradient,
        "LOD_canopyGradient": lod_canopy_gradient,
    }


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
    profile: bool = False,
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
    timings = {} if profile else None

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

    t0 = time.perf_counter() if profile else 0
    if not hazel_reference.exists():
        if verbose:
            print(
                f"  Warning: Hazel reference not found at {hazel_reference}, using schema"
            )
        template = create_empty_pve_preset()
    else:
        template = create_pve_template_from_reference(hazel_reference)
    if profile:
        timings["load_template"] = time.perf_counter() - t0

    # Map Grove data to template with all features
    t0 = time.perf_counter() if profile else 0
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
        profile=profile,
    )
    if profile:
        timings["map_grove_to_pve"] = time.perf_counter() - t0

    # Save to file
    t0 = time.perf_counter() if profile else 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(pve_data, f, indent=2)
    if profile:
        timings["write_json"] = time.perf_counter() - t0

    if profile and verbose:
        total = sum(timings.values())
        print(f"  PVE Generation Timing (total: {total:.3f}s):")
        for step, elapsed in sorted(timings.items(), key=lambda x: -x[1]):
            pct = (elapsed / total * 100) if total > 0 else 0
            print(f"    {step}: {elapsed:.3f}s ({pct:.1f}%)")

    if verbose:
        print(f"  [OK] PVE preset with foliage: {output_path.name}")
    return pve_data
