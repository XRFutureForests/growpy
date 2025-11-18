"""
Wind JSON generation for Unreal Engine DynamicWind system.

Generates DynamicWind JSON files that assign SimulationGroupIndex values to skeleton joints
based on Grove skeleton attributes (age, mass, hierarchy). Compatible with Nanite skeletal meshes.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def generate_wind_json(
    tree_usd_path: Path,
    skeleton: Optional[Any] = None,
    bones_info: Optional[List] = None,
    output_path: Optional[Path] = None,
) -> Dict:
    """
    Generate DynamicWind JSON for a tree USD file using Grove skeleton data.

    Args:
        tree_usd_path: Path to tree skeletal USD file
        skeleton: Optional Grove skeleton object from grove.build_skeletons()
        bones_info: Optional list of bone tuples from grove.tag_bone_id()
        output_path: Optional output path for JSON file. If None, returns dict only.

    Returns:
        Dictionary with DynamicWind JSON structure
    """
    # Convert paths to Path objects if they're strings
    tree_usd_path = (
        Path(tree_usd_path) if isinstance(tree_usd_path, str) else tree_usd_path
    )
    if output_path:
        output_path = Path(output_path) if isinstance(output_path, str) else output_path

    # Extract joint names from USD
    joint_names = _extract_joint_names_from_usd(tree_usd_path)

    if not joint_names:
        raise ValueError(f"No skeleton joints found in {tree_usd_path}")

    # Extract skeleton attributes from Grove skeleton if available
    skeleton_attrs = None
    if skeleton and bones_info:
        skeleton_attrs = _extract_skeleton_attrs_from_grove(skeleton, bones_info)

    # Classify each joint
    joints_data = []
    for idx, joint_name in enumerate(joint_names):
        group_index = _classify_joint(
            joint_name=joint_name,
            joint_index=idx,
            skeleton_attrs=skeleton_attrs,
        )
        joints_data.append(
            {"JointName": joint_name, "SimulationGroupIndex": group_index}
        )

    # Build wind JSON structure
    wind_json = {
        "Joints": joints_data,
        "SimulationGroups": [],
        "bIsGroundCover": False,
        "GustAttenuation": 0.0,
    }

    # Write to file if output path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(wind_json, f, indent=2)

    return wind_json


def _classify_joint(
    joint_name: str,
    joint_index: int,
    skeleton_attrs: Optional[Dict],
) -> int:
    """
    Classify joint into simulation group based on branch hierarchy and age.

    Classification strategy:
    - Group 0 (rigid/trunk): Main trunk - oldest growth (max age)
    - Group 1 (medium): Primary branches - medium age growth
    - Group 2 (flexible): Secondary+ branches and tips - young age growth

    This uses Grove's age attribute which directly represents growth order:
    - Higher age = older growth = trunk/main structure
    - Lower age = newer growth = flexible branches and tips

    Args:
        joint_name: Full joint path (e.g., "tree_root/joint_1/branch_0")
        joint_index: Index into skeleton arrays
        skeleton_attrs: Optional dict with 'age', 'branch_depth', 'is_branch_root' arrays

    Returns:
        SimulationGroupIndex: 0 (trunk/rigid), 1 (primary/medium), 2 (tips/flexible)
    """
    # Strategy 1: Age-based classification (primary method)
    # Age directly represents growth order in Grove - simpler and more reliable than mass
    if skeleton_attrs and joint_index < len(skeleton_attrs.get("age", [])):
        age = skeleton_attrs["age"][joint_index]
        branch_depth = skeleton_attrs.get(
            "branch_depth", [0] * len(skeleton_attrs["age"])
        )[joint_index]
        is_branch_root = skeleton_attrs.get(
            "is_branch_root", [False] * len(skeleton_attrs["age"])
        )[joint_index]

        all_ages = skeleton_attrs["age"]
        max_age = max(all_ages)

        # Debug first joint only
        if joint_index == 0:
            unique_ages = sorted(set(all_ages), reverse=True)
            print(
                f"[Wind JSON Classification] Using age-based grouping: "
                f"max_age={max_age}, unique_ages={unique_ages}"
            )

        # Classification based on age tiers
        # Trunk: Maximum age (oldest growth)
        if age == max_age:
            return 0  # Main trunk structure

        # Primary branches: Medium age OR branch roots at medium depth
        # This catches first-order branches that fork from trunk
        elif age >= max_age * 0.5 or (is_branch_root and branch_depth <= 1):
            return 1  # Primary branches

        # Everything else: Tips and secondary branches (youngest growth)
        else:
            return 2  # Flexible tips and secondary branches

    # Strategy 2: Hierarchy depth from joint name (fallback when no skeleton data)
    if joint_index == 0:
        print(
            f"[Wind JSON Classification] Using hierarchy fallback (no skeleton attrs)"
        )
    return _classify_by_hierarchy_depth(joint_name)


def _classify_by_hierarchy_depth(joint_name: str) -> int:
    """
    Classify joint by counting branch depth in hierarchical path.

    Args:
        joint_name: Joint path like "tree_root/joint_1/branch_0/joint_2"

    Returns:
        SimulationGroupIndex based on branch depth
    """
    # Count branch markers in path
    branch_depth = joint_name.count("/branch_")

    if branch_depth == 0:
        return 0  # Trunk (tree_root/joint_N only)
    elif branch_depth == 1:
        return 1  # Primary branches
    else:
        return 2  # Secondary+ branches


def _extract_joint_names_from_usd(tree_usd_path: Path) -> List[str]:
    """
    Extract joint names array from tree USD skeleton.

    Args:
        tree_usd_path: Path to tree USD with skeleton

    Returns:
        List of joint names in skeleton order
    """
    try:
        # Use bpy's bundled USD (pxr module)
        import bpy
        from pxr import Usd, UsdSkel

        stage = Usd.Stage.Open(str(tree_usd_path))

        # Find skeleton prim
        for prim in stage.Traverse():
            if prim.IsA(UsdSkel.Skeleton):
                skeleton = UsdSkel.Skeleton(prim)
                joints_attr = skeleton.GetJointsAttr()

                if joints_attr:
                    joint_names = joints_attr.Get()
                    return [str(name) for name in joint_names]

        return []

    except Exception as e:
        print(f"Warning: Could not extract joints from USD: {e}")
        return []


def _extract_skeleton_attrs_from_grove(
    skeleton: Any, bones_info: List
) -> Dict[str, List[float]]:
    """
    Extract age and branch hierarchy from Grove skeleton and bones.

    This extracts:
    - age: Growth order (higher = older trunk, lower = newer branches)
    - branch_depth: Number of branch forks from trunk (0 = trunk, 1 = primary, 2+ = secondary)
    - is_branch_root: Whether this point starts a new branch

    Args:
        skeleton: Grove skeleton object from grove.build_skeletons()
        bones_info: List of bone tuples from grove.tag_bone_id()
                   Format: (is_tree_root, parent_id, start_point, end_point, radius, mass, is_branch_root, branch_id)

    Returns:
        Dictionary with 'age', 'branch_depth', 'is_branch_root' arrays
    """
    try:
        # Extract age from skeleton
        age_array = (
            skeleton.point_attribute_age
            if hasattr(skeleton, "point_attribute_age")
            else []
        )

        # Extract branch hierarchy from bones_info
        # bones_info format: (is_tree_root, parent_id, start_point, end_point, radius, mass, is_branch_root, branch_id)
        branch_depth_map = {}
        is_branch_root_map = {}
        branch_id_map = {}

        # Build hierarchy map from bones_info
        if bones_info:
            # First pass: calculate branch depth for each bone
            bone_depths = {}
            bone_branch_ids = {}

            for bone_idx, bone in enumerate(bones_info):
                is_tree_root = bone[0]
                parent_bone_id = bone[1]
                is_branch_root = bone[6]
                branch_id = bone[7]

                # Store branch ID for this bone
                bone_branch_ids[bone_idx] = branch_id

                # Tree root is depth 0 (main trunk)
                if is_tree_root:
                    bone_depths[bone_idx] = 0
                # Branch root means we fork off into new branch - increment depth
                elif is_branch_root:
                    parent_depth = bone_depths.get(parent_bone_id, 0)
                    bone_depths[bone_idx] = parent_depth + 1
                # Continuation of parent's branch - keep same depth
                else:
                    bone_depths[bone_idx] = bone_depths.get(parent_bone_id, 0)

            # Second pass: map point indices to depths using branch_id
            # Points are numbered sequentially within each polyline/branch
            # We group bones by branch_id and assign depths to all points in that branch
            from collections import defaultdict

            branch_to_depth = {}
            branch_to_has_root = defaultdict(bool)

            for bone_idx, bone in enumerate(bones_info):
                branch_id = bone_branch_ids[bone_idx]
                depth = bone_depths[bone_idx]
                is_branch_root = bone[6]

                # Track minimum depth for this branch (in case it varies)
                if branch_id not in branch_to_depth:
                    branch_to_depth[branch_id] = depth
                else:
                    branch_to_depth[branch_id] = min(branch_to_depth[branch_id], depth)

                # Mark if this branch has a branch root
                if is_branch_root:
                    branch_to_has_root[branch_id] = True

            # Now map all points by looking up their position in the skeleton
            # Since we don't have direct point->branch mapping, we use sequential indexing
            # Bones are exported in depth-first order matching point order
            point_idx = 0
            for bone_idx, bone in enumerate(bones_info):
                branch_id = bone_branch_ids[bone_idx]
                depth = branch_to_depth[branch_id]
                is_branch_root = bone[6]

                # Each bone maps to its start point
                # (end point is the start of next bone or leaf)
                if point_idx < len(age_array):
                    branch_depth_map[point_idx] = depth
                    is_branch_root_map[point_idx] = is_branch_root
                    branch_id_map[point_idx] = branch_id
                    point_idx += 1

            # Handle last point (end of last bone)
            if point_idx < len(age_array) and bones_info:
                last_bone = bones_info[-1]
                last_branch_id = bone_branch_ids[len(bones_info) - 1]
                branch_depth_map[point_idx] = branch_to_depth[last_branch_id]
                is_branch_root_map[point_idx] = (
                    False  # End points are never branch roots
                )
                branch_id_map[point_idx] = last_branch_id

        # Build arrays aligned with age array
        num_points = len(age_array)
        branch_depth_array = [branch_depth_map.get(i, 0) for i in range(num_points)]
        is_branch_root_array = [
            is_branch_root_map.get(i, False) for i in range(num_points)
        ]

        # Convert to lists
        result = {
            "age": [float(a) for a in age_array],
            "branch_depth": branch_depth_array,
            "is_branch_root": is_branch_root_array,
        }

        # Debug output
        if result["age"]:
            unique_ages = len(set(result["age"]))
            max_depth = max(result["branch_depth"]) if result["branch_depth"] else 0
            num_branch_roots = sum(result["is_branch_root"])
            print(
                f"[Wind JSON] Extracted {len(result['age'])} skeleton points: "
                f"age range [{min(result['age']):.0f}-{max(result['age']):.0f}] ({unique_ages} unique), "
                f"max_branch_depth={max_depth}, branch_roots={num_branch_roots}"
            )

        return result

    except Exception as e:
        print(f"Warning: Could not extract skeleton attributes from Grove: {e}")
        import traceback

        traceback.print_exc()
        return {}


def generate_wind_json_for_species(
    species_output_dir: Path,
    tree_prefix: str = "tree",
) -> List[Path]:
    """
    Generate wind JSON files for all skeletal trees in a species output directory.

    Note: This is a fallback method that reads USD files. Prefer calling generate_wind_json()
    directly from export code with Grove skeleton/bones_info for better accuracy.

    Args:
        species_output_dir: Directory containing tree USD files (e.g., data/output/forest/european_beech/)
        tree_prefix: Prefix for tree files (default: "tree")

    Returns:
        List of generated wind JSON file paths
    """
    generated_files = []

    # Find all skeletal USD files
    skeletal_usds = list(species_output_dir.glob(f"*{tree_prefix}_*_skeletal.usda"))

    for skeletal_usd in skeletal_usds:
        # Extract tree identifier (e.g., "tree_0000" from "european_beech_tree_0000_skeletal.usda")
        stem = skeletal_usd.stem.replace("_skeletal", "")

        # Generate output path for wind JSON
        wind_json_path = skeletal_usd.parent / f"{stem}_DynamicWind.json"

        # Generate wind JSON (no Grove data available, will use hierarchy fallback)
        try:
            generate_wind_json(
                tree_usd_path=skeletal_usd,
                skeleton=None,
                bones_info=None,
                output_path=wind_json_path,
            )
            generated_files.append(wind_json_path)
            print(f"Generated: {wind_json_path.name}")
        except Exception as e:
            print(f"Error generating wind JSON for {skeletal_usd.name}: {e}")

    return generated_files
    return generated_files
