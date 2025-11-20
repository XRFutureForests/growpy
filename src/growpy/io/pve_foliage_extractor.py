"""
Extract foliage/twig instancer data from Grove models.

Converts Grove twig instances to PVE instancer format with proper
coordinate system conversion and grouping by branch.
"""

from typing import Any, Dict, List, Tuple

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
    quat: Tuple[float, float, float, float]
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
    models: List[Any],
    tree_index: int,
    species_name: str,
    num_branches: int,
) -> Dict[str, Dict]:
    """
    Extract foliage instancer data from Grove models.
    
    Args:
        models: List of Grove tree models from build_models()
        tree_index: Index of tree to extract
        species_name: Species name for asset naming
        num_branches: Number of branches (for array sizing)
    
    Returns:
        Dictionary with instancer_* attribute structures
    """
    if tree_index >= len(models):
        # No model - return empty arrays
        return _create_empty_instancer_arrays(num_branches)
    
    model = models[tree_index]
    
    # Check if model has twigs
    if not hasattr(model, "twigs") or not model.twigs:
        return _create_empty_instancer_arrays(num_branches)
    
    # Group twigs by branch_id
    twigs_by_branch = {}
    for twig in model.twigs:
        branch_id = getattr(twig, "branch_id", 0)
        if branch_id not in twigs_by_branch:
            twigs_by_branch[branch_id] = []
        twigs_by_branch[branch_id].append(twig)
    
    # Build instancer arrays
    instancer_names = []
    instancer_pivots = []
    instancer_ups = []
    instancer_normals = []
    instancer_scales = []
    instancer_lfrs = []
    
    for branch_idx in range(num_branches):
        if branch_idx in twigs_by_branch:
            branch_twigs = twigs_by_branch[branch_idx]
            
            # Extract data for this branch's twigs
            names = []
            pivots = []
            ups = []
            normals = []
            scales = []
            lfrs = []
            
            for twig in branch_twigs:
                # Get twig properties
                position = twig.position if hasattr(twig, "position") else (0, 0, 0)
                rotation = twig.rotation if hasattr(twig, "rotation") else (0, 0, 0, 1)
                scale = twig.scale if hasattr(twig, "scale") else 1.0
                type_id = twig.type_id if hasattr(twig, "type_id") else 0
                lfr = twig.length_from_root if hasattr(twig, "length_from_root") else 0.0
                
                # Get variant name if available
                variant_name = None
                if hasattr(twig, "variant_name"):
                    variant_name = twig.variant_name
                
                # Convert to PVE format
                pve_pos = grove_to_pve_position(position)
                up, normal = quaternion_to_up_normal(rotation)
                twig_name = get_twig_name_for_species(species_name, type_id, variant_name)
                
                # Append to arrays
                names.append(twig_name)
                pivots.extend(pve_pos)  # Flatten xyz
                ups.extend(up)  # Flatten xyz
                normals.extend(normal)  # Flatten xyz
                scales.append(scale)
                lfrs.append(lfr)
            
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
            "value": instancer_names,
        },
        "instancer_pivot": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "value": instancer_pivots,
        },
        "instancer_UP": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "value": instancer_ups,
        },
        "instancer_N": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "value": instancer_normals,
        },
        "instancer_scale": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": instancer_scales,
        },
        "instancer_LFR": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": instancer_lfrs,
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
            "value": empty_arrays.copy(),
        },
        "instancer_pivot": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "value": empty_arrays.copy(),
        },
        "instancer_UP": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "value": empty_arrays.copy(),
        },
        "instancer_N": {
            "isArray": True,
            "size": 3,
            "type": "float",
            "value": empty_arrays.copy(),
        },
        "instancer_scale": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": empty_arrays.copy(),
        },
        "instancer_LFR": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": empty_arrays.copy(),
        },
    }
    }
