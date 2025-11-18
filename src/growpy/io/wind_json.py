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
        joints_data.append({"SimulationGroupIndex": group_index})

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
    Classify joint into simulation group using adaptive thresholds.

    Classification strategy (in priority order):
    1. If skeleton attributes available: use age + mass percentile-based thresholds
    2. Fallback: use joint name hierarchy depth (branch_X counting)

    Args:
        joint_name: Full joint path (e.g., "tree_root/joint_1/branch_0")
        joint_index: Index into skeleton arrays
        skeleton_attrs: Optional dict with 'age', 'mass', 'radius' arrays

    Returns:
        SimulationGroupIndex: 0 (trunk/rigid), 1 (primary/medium), 2 (tips/flexible)
    """
    # Strategy 1: Age + Mass percentile-based classification
    if skeleton_attrs and joint_index < len(skeleton_attrs.get("age", [])):
        age = skeleton_attrs["age"][joint_index]
        mass = skeleton_attrs["mass"][joint_index]

        # Calculate adaptive thresholds from data distribution
        all_ages = skeleton_attrs["age"]
        all_masses = skeleton_attrs["mass"]

        max_age = max(all_ages)
        age_threshold_trunk = max_age * 0.5  # Upper 50% of age range = trunk

        # Mass percentiles for young growth (age < threshold)
        young_masses = [
            m for a, m in zip(all_ages, all_masses) if a < age_threshold_trunk
        ]
        if young_masses:
            # Use 90th and 50th percentiles for better distribution
            # This ensures ~10% go to trunk continuation, ~40% to primary, ~50% to tips
            mass_90th = np.percentile(
                young_masses, 90
            )  # Heavy young = trunk continuation
            mass_50th = np.percentile(young_masses, 50)  # Medium = primary branches
        else:
            mass_90th = np.percentile(all_masses, 90)
            mass_50th = np.percentile(all_masses, 50)

        # Debug first joint only
        if joint_index == 0:
            print(
                f"[Wind JSON Classification] Using skeleton attributes: "
                + f"age_threshold={age_threshold_trunk:.2f}, "
                + f"mass_90th={mass_90th:.2f}, mass_50th={mass_50th:.2f}"
            )

        # Classify by age first
        if age >= age_threshold_trunk:
            return 0  # Old growth = trunk (most rigid)

        # Within young growth, use mass
        if mass >= mass_90th:
            return 0  # Heavy young segments = trunk continuation
        elif mass >= mass_50th:
            return 1  # Medium mass = primary branches
        else:
            return 2  # Light = branch tips (most flexible)

    # Strategy 2: Hierarchy depth from joint name (fallback)
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
    Extract age, mass, and radius attributes directly from Grove skeleton and bones.

    Args:
        skeleton: Grove skeleton object from grove.build_skeletons()
        bones_info: List of bone tuples from grove.tag_bone_id()

    Returns:
        Dictionary with 'age', 'mass', 'radius' arrays
    """
    try:
        # Extract attributes from skeleton - these are arrays, not per-point attributes
        age_array = (
            skeleton.point_attribute_age
            if hasattr(skeleton, "point_attribute_age")
            else []
        )
        mass_array = (
            skeleton.point_attribute_mass
            if hasattr(skeleton, "point_attribute_mass")
            else []
        )
        radius_array = (
            skeleton.point_attribute_radius
            if hasattr(skeleton, "point_attribute_radius")
            else []
        )

        # Convert to float lists
        result = {
            "age": [float(a) for a in age_array],
            "mass": [float(m) for m in mass_array],
            "radius": [float(r) for r in radius_array],
        }

        # Debug output
        if result["age"]:
            print(
                f"[Wind JSON] Extracted {len(result['age'])} skeleton points: "
                + f"age range [{min(result['age']):.2f}-{max(result['age']):.2f}], "
                + f"mass range [{min(result['mass']):.2f}-{max(result['mass']):.2f}]"
            )

        return result

    except Exception as e:
        print(f"Warning: Could not extract skeleton attributes from Grove: {e}")
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
