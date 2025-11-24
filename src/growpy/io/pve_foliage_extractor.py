"""
Extract foliage/twig instancer data from Grove models.

Converts Grove twig instances to PVE instancer format with proper
coordinate system conversion and grouping by branch.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def grove_to_pve_position(grove_pos: Tuple[float, float, float]) -> List[float]:
    """
    Convert Grove position to PVE format.

    Grove uses Z-up meters, PVE uses Y-up centimeters.

    Args:
        grove_pos: (x, y, z) in meters, Z-up

    Returns:
        [x, z, y] in centimeters, Y-up
    """
    x, y, z = grove_pos
    return [x * 100.0, z * 100.0, y * 100.0]


def grove_to_pve_vector(grove_vec: Tuple[float, float, float]) -> List[float]:
    """
    Convert Grove direction vector to PVE format.

    Args:
        grove_vec: (x, y, z) normalized vector, Z-up

    Returns:
        [x, z, y] normalized vector, Y-up
    """
    x, y, z = grove_vec
    return [x, z, y]


def quaternion_to_up_normal(
    quat: Tuple[float, float, float, float],
) -> Tuple[List[float], List[float]]:
    """
    Convert quaternion to up and normal vectors for PVE.

    Args:
        quat: (x, y, z, w) quaternion

    Returns:
        Tuple of (up_vector, normal_vector) in PVE format
    """
    try:
        from scipy.spatial.transform import Rotation
    except ImportError:
        # Fallback - use default up/normal
        return [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]

    # Convert to rotation matrix
    rot = Rotation.from_quat([quat[0], quat[1], quat[2], quat[3]])

    # Extract up and normal in Grove space
    up_grove = rot.apply([0, 0, 1])  # Local Z
    normal_grove = rot.apply([0, 1, 0])  # Local Y

    # Convert to PVE space
    up_pve = grove_to_pve_vector(up_grove)
    normal_pve = grove_to_pve_vector(normal_grove)

    return up_pve, normal_pve


def get_twig_name_for_species(
    species_name: str, twig_type_id: int, variant_name: str = None
) -> str:
    """
    Get Unreal asset name for a twig type.

    Maps Grove twig type IDs to Unreal Static Mesh asset names.

    Args:
        species_name: Species name (e.g., "european_oak")
        twig_type_id: Grove twig type index
        variant_name: Optional variant name from twig data

    Returns:
        Asset name (e.g., "SM_European_Oak_Twig_Apical")
    """
    # Format species name for asset naming
    species_formatted = species_name.replace("_", " ").title().replace(" ", "_")

    # Try to use variant name if available (apical, lateral, etc.)
    if variant_name:
        variant_formatted = variant_name.replace("_", " ").title().replace(" ", "_")
        return f"SM_{species_formatted}_Twig_{variant_formatted}"

    # Fallback to type ID
    return f"SM_{species_formatted}_Twig_{twig_type_id:02d}"


def extract_foliage_data(
    model: Any,
    species_name: str,
    bones_info: Optional[List] = None,
    verbose: bool = False,
) -> Dict[str, Dict]:
    """
    Extract foliage instancer data from a Grove model.

    CRITICAL: Model must be pre-built with twigs from export phase.
    Uses the same twig extraction as USD assembly export.
    bones_info is required for correct branch_id assignment!

    Args:
        model: Grove tree model (with twigs) from build_models()
        species_name: Species name for twig filename construction (e.g., "european_beech")
        bones_info: Bones info from export phase for branch_id calculation - REQUIRED
        verbose: Print detailed extraction information

    Returns:
        Dictionary with instancer_* attribute structures
    """
    from ..core.twig import extract_twig_placements_from_model

    # Extract twig placements using the same method as USD export
    # CRITICAL: Pass bones_info so branch_id is correctly calculated
    twig_placements_by_type = extract_twig_placements_from_model(
        model, bones_info=bones_info
    )

    # Count total twigs across all types
    total_twigs = sum(
        len(placements) for placements in twig_placements_by_type.values()
    )

    # Get num_branches from model face attributes
    if hasattr(model, "face_attribute_branch_id"):
        num_branches = len(set(model.face_attribute_branch_id))
    else:
        num_branches = 0
        if verbose:
            print("  Warning: Model has no branch IDs, cannot extract foliage")
        return _create_empty_instancer_arrays(0)

    if total_twigs == 0:
        if verbose:
            print(
                f"  Warning: No twigs extracted, returning empty arrays for {num_branches} branches"
            )
        return _create_empty_instancer_arrays(num_branches)

    if verbose:
        print(
            f"  Extracting foliage from model with {total_twigs} twigs for {num_branches} branches"
        )

    # Group twigs by branch_id - flatten all twig types into one list
    twigs_by_branch = {}
    for twig_type, placements in twig_placements_by_type.items():
        for placement in placements:
            branch_id = placement.branch_id
            if branch_id not in twigs_by_branch:
                twigs_by_branch[branch_id] = []
            # Store twig_type with placement for filename construction
            twigs_by_branch[branch_id].append((twig_type, placement))

    print(f"  PVE: Grouped {total_twigs} twigs into {len(twigs_by_branch)} branches")
    print(
        f"  PVE: num_branches={num_branches}, branch_ids in data: {sorted(list(twigs_by_branch.keys()))[:10]}"
    )

    # Build instancer arrays
    instancer_names = []
    instancer_pivots = []
    instancer_ups = []
    instancer_normals = []
    instancer_scales = []
    instancer_lfrs = []

    branches_with_twigs = 0
    for branch_idx in range(num_branches):
        if branch_idx in twigs_by_branch:
            branches_with_twigs += 1
            branch_twigs = twigs_by_branch[branch_idx]

            # Extract data for this branch's twigs
            names = []
            pivots = []
            ups = []
            normals = []
            scales = []
            lfrs = []

            for twig_type, placement in branch_twigs:
                # TwigPlacement has: type, position, normal, scale, bone_id, branch_id
                position = placement.position  # Tuple (x, y, z)
                normal = placement.normal  # Tuple (x, y, z) - direction vector
                scale_value = placement.scale

                # Build twig filename to match our USD export naming convention
                # Map twig_type to variant name that matches our exported files
                # twig_long → var_a/var_c, twig_upward → var_c, twig_short → var_b, twig_dead → var_b
                variant_map = {
                    "twig_long": "var_a",
                    "twig_short": "var_b",
                    "twig_upward": "var_c",
                    "twig_dead": "var_b",
                }
                variant = variant_map.get(twig_type, "var_a")

                # Construct full twig filename (without _skeletal.usda extension)
                species_clean = species_name.replace(" ", "_").lower()
                twig_name = f"{species_clean}_twig_{variant}"

                # Convert to PVE format
                pve_pos = grove_to_pve_position(position)
                # TwigPlacement.normal is the direction vector - use it as the "up" vector
                # For PVE, we need "up" (growth direction) and "normal" (surface normal)
                # Use the twig direction as "up" and derive normal from it
                pve_normal = grove_to_pve_position(normal)  # Convert direction vector
                # For now, use the same vector for both (PVE can handle this)
                up = pve_normal
                pve_normal_out = pve_normal

                # Append to arrays
                names.append(twig_name)
                pivots.extend(pve_pos)  # Flatten xyz
                ups.extend(up)  # Flatten xyz
                normals.extend(pve_normal_out)  # Flatten xyz
                scales.append(scale_value)
                lfrs.append(
                    0.0
                )  # Length from root - not available in TwigPlacement, use 0.0

            instancer_names.append(names)
            instancer_pivots.append(pivots)
            instancer_ups.append(ups)
            instancer_normals.append(normals)
            instancer_scales.append(scales)
            instancer_lfrs.append(lfrs)
        else:
            # Branch has no twigs - empty arrays
            instancer_names.append([])
            instancer_pivots.append([])
            instancer_ups.append([])
            instancer_normals.append([])
            instancer_scales.append([])
            instancer_lfrs.append([])

    return {
        "instancer_name": {
            "isArray": True,
            "size": 1,
            "type": "string",
            "values": instancer_names,
        },
        "instancer_pivot": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "values": instancer_pivots,
        },
        "instancer_UP": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "values": instancer_ups,
        },
        "instancer_N": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "values": instancer_normals,
        },
        "instancer_scale": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "values": instancer_scales,
        },
        "instancer_LFR": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "values": instancer_lfrs,
        },
    }


def _create_empty_instancer_arrays(num_branches: int) -> Dict[str, Dict]:
    """Create empty instancer arrays for branches with no foliage."""
    empty_arrays = [[] for _ in range(num_branches)]

    return {
        "instancer_name": {
            "isArray": True,
            "size": 1,
            "type": "string",
            "values": empty_arrays.copy(),
        },
        "instancer_pivot": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "values": empty_arrays.copy(),
        },
        "instancer_UP": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "values": empty_arrays.copy(),
        },
        "instancer_N": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "values": empty_arrays.copy(),
        },
        "instancer_scale": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "values": empty_arrays.copy(),
        },
        "instancer_LFR": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "values": empty_arrays.copy(),
        },
    }
