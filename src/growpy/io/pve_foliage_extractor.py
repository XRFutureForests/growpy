"""
Extract foliage/twig instancer data from Grove models.

Converts Grove twig instances to PVE instancer format with proper
coordinate system conversion and grouping by branch.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


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
        Asset name (e.g., "SM_European_Oak_Foliage_Apical")
    """
    # Format species name for asset naming
    species_formatted = species_name.replace("_", " ").title().replace(" ", "_")

    # Try to use variant name if available (apical, lateral, etc.)
    if variant_name:
        variant_formatted = variant_name.replace("_", " ").title().replace(" ", "_")
        return f"SM_{species_formatted}_Foliage_{variant_formatted}"

    # Fallback to type ID
    return f"SM_{species_formatted}_Foliage_{twig_type_id:02d}"


def extract_foliage_data(
    model: Any,
    species_name: str,
    bones_info: Optional[List] = None,
    num_branches: Optional[int] = None,
    verbose: bool = False,
    profile: bool = False,
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
        num_branches: Number of branches from skeleton (poly_lines count). If None, calculated from model.
        verbose: Print detailed extraction information
        profile: Enable timing output

    Returns:
        Dictionary with instancer_* attribute structures
    """
    import time

    from ..core.twig import extract_twig_placements_from_model

    timings = {} if profile else None

    # Extract twig placements using the same method as USD export
    # CRITICAL: Pass bones_info so branch_id is correctly calculated
    t0 = time.perf_counter() if profile else 0
    twig_placements_by_type = extract_twig_placements_from_model(
        model, bones_info=bones_info
    )
    if profile:
        timings["extract_twig_placements"] = time.perf_counter() - t0

    # Count total twigs across all types
    total_twigs = sum(
        len(placements) for placements in twig_placements_by_type.values()
    )

    # Use provided num_branches (from skeleton poly_lines) or calculate from model
    # CRITICAL: num_branches from skeleton is the authoritative count for PVE arrays
    if num_branches is None:
        if hasattr(model, "face_attribute_branch_id"):
            num_branches = len(set(model.face_attribute_branch_id))
        else:
            num_branches = 0
            logger.warning("Model has no branch IDs, cannot extract foliage")
            return _create_empty_instancer_arrays(0)

    if num_branches == 0:
        logger.warning("num_branches is 0, cannot extract foliage")
        return _create_empty_instancer_arrays(0)

    if total_twigs == 0:
        logger.warning(
            "No twigs extracted, returning empty arrays for %d branches",
            num_branches,
        )
        return _create_empty_instancer_arrays(num_branches)

    logger.info(
        "Extracting foliage from model with %d twigs for %d branches",
        total_twigs,
        num_branches,
    )

    # Group twigs by branch_id - flatten all twig types into one list
    # CRITICAL: Handle None branch_ids (assign to branch 0 as fallback)
    t0 = time.perf_counter() if profile else 0
    twigs_by_branch = {}
    skipped_none_branch = 0
    for twig_type, placements in twig_placements_by_type.items():
        for placement in placements:
            branch_id = placement.branch_id
            # Handle None or negative branch_id - assign to branch 0
            if branch_id is None or branch_id < 0:
                branch_id = 0
                skipped_none_branch += 1
            # Clamp branch_id to valid range (0 to num_branches-1)
            if branch_id >= num_branches:
                branch_id = num_branches - 1 if num_branches > 0 else 0
            if branch_id not in twigs_by_branch:
                twigs_by_branch[branch_id] = []
            # Store twig_type with placement for filename construction
            twigs_by_branch[branch_id].append((twig_type, placement))
    if profile:
        timings["group_by_branch"] = time.perf_counter() - t0

    if skipped_none_branch > 0:
        logger.warning(
            "PVE: %d twigs had None/invalid branch_id, assigned to branch 0",
            skipped_none_branch,
        )
    logger.info(
        "PVE: Grouped %d twigs into %d branches", total_twigs, len(twigs_by_branch)
    )
    logger.info(
        "PVE: num_branches=%d, branch_ids in data: %s",
        num_branches,
        sorted(list(twigs_by_branch.keys()))[:10],
    )

    # Build instancer arrays
    t0 = time.perf_counter() if profile else 0
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
                # TwigPlacement has: type, position, normal, orientation, scale, bone_id, branch_id
                position = placement.position  # Tuple (x, y, z)
                normal = placement.normal  # Tuple (x, y, z) - facing direction
                orientation = placement.orientation  # Tuple (x, y, z) - up vector
                scale_value = placement.scale

                # Build twig filename to match our USD export naming convention
                # Map twig_type to variant name that matches our exported files
                # twig_long -> a, twig_upward -> c, twig_short -> b, twig_dead -> b
                variant_map = {
                    "twig_long": "a",
                    "twig_short": "b",
                    "twig_upward": "c",
                    "twig_dead": "b",
                }
                variant = variant_map.get(twig_type, "a")

                # Construct full twig filename (without _skeletal.usda extension)
                species_clean = species_name.replace(" ", "_").lower()
                twig_name = f"{species_clean}_foliage_{variant}"

                # Convert to PVE format (Y-up, meters for positions; Y-up for vectors)
                pve_pos = grove_to_pve_position(position)

                # Convert direction vectors (no scaling, just axis swap)
                pve_normal = grove_to_pve_vector(normal)
                pve_up = grove_to_pve_vector(orientation)

                # Normalize the normal (facing direction) for instancer_N
                nx, ny, nz = pve_normal
                mag_sq = nx * nx + ny * ny + nz * nz
                if mag_sq > 1e-10:
                    inv_mag = 1.0 / math.sqrt(mag_sq)
                    pve_normal = (nx * inv_mag, ny * inv_mag, nz * inv_mag)
                else:
                    pve_normal = (0.0, 0.0, 1.0)

                # Normalize the up vector for instancer_UP
                ux, uy, uz = pve_up
                mag_sq = ux * ux + uy * uy + uz * uz
                if mag_sq > 1e-10:
                    inv_mag = 1.0 / math.sqrt(mag_sq)
                    pve_up = (ux * inv_mag, uy * inv_mag, uz * inv_mag)
                else:
                    pve_up = (0.0, 1.0, 0.0)  # Default Y-up in PVE space

                # Append to arrays
                names.append(twig_name)
                pivots.extend(pve_pos)  # Flatten xyz
                ups.extend(pve_up)  # Flatten xyz - UP vector
                normals.extend(pve_normal)  # Flatten xyz - Normal/facing vector
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

    if profile:
        timings["build_instancer_arrays"] = time.perf_counter() - t0
        total = sum(timings.values())
        logger.debug("extract_foliage_data breakdown (%.3fs):", total)
        for step, elapsed in sorted(timings.items(), key=lambda x: -x[1]):
            pct = (elapsed / total * 100) if total > 0 else 0
            logger.debug("  %s: %.3fs (%.1f%%)", step, elapsed, pct)

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
