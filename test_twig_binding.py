#!/usr/bin/env python3
"""
Test script to validate twig-to-joint bindings in Nanite Assembly USD files.

This script:
1. Parses the Nanite Assembly USD to extract twig positions and bound joints
2. Parses the skeletal USD to extract joint positions (bind transforms)
3. Calculates the expected nearest joint for each twig using point-to-segment distance
4. Compares actual vs expected bindings and reports mismatches
5. Provides detailed diagnostic output for debugging binding issues

Usage:
    python test_twig_binding.py data/output/forest/european_beech/european_beech_tree_0000_nanite_assembly.usda
"""

import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Initialize bpy's bundled USD module
import bpy

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

from pxr import Usd, UsdGeom, UsdSkel


def point_to_segment_distance(
    point: Tuple[float, float, float],
    seg_start: Tuple[float, float, float],
    seg_end: Tuple[float, float, float],
) -> float:
    """Calculate perpendicular distance from point to line segment."""
    px, py, pz = point
    ax, ay, az = seg_start
    bx, by, bz = seg_end

    # Vector from A to B (segment direction)
    abx, aby, abz = bx - ax, by - ay, bz - az

    # Vector from A to P (point)
    apx, apy, apz = px - ax, py - ay, pz - az

    # Segment length squared
    ab_len_sq = abx * abx + aby * aby + abz * abz

    if ab_len_sq == 0:
        # Degenerate segment, return distance to point
        return math.sqrt(apx * apx + apy * apy + apz * apz)

    # Parameter t represents projection of P onto line AB
    t = (apx * abx + apy * aby + apz * abz) / ab_len_sq

    # Clamp t to [0, 1] to stay within segment bounds
    t = max(0.0, min(1.0, t))

    # Find closest point on segment
    closest_x = ax + t * abx
    closest_y = ay + t * aby
    closest_z = az + t * abz

    # Distance from point to closest point on segment
    dx = px - closest_x
    dy = py - closest_y
    dz = pz - closest_z

    return math.sqrt(dx * dx + dy * dy + dz * dz)


def parse_nanite_assembly(usd_path: Path) -> Dict:
    """Parse Nanite Assembly USD to extract twig positions and bindings."""
    stage = Usd.Stage.Open(str(usd_path))

    # Find TwigInstances PointInstancer
    twig_instancer = None
    for prim in stage.Traverse():
        if prim.GetName() == "TwigInstances":
            twig_instancer = UsdGeom.PointInstancer(prim)
            break

    if not twig_instancer:
        raise ValueError("TwigInstances not found in Nanite Assembly USD")

    # Extract twig data
    positions_attr = twig_instancer.GetPositionsAttr()
    positions = positions_attr.Get() if positions_attr else []

    bind_joints_attr = twig_instancer.GetPrim().GetAttribute(
        "primvars:unreal:naniteAssembly:bindJoints"
    )
    bind_joints = bind_joints_attr.Get() if bind_joints_attr else []

    # Convert to Python types
    positions = [tuple(pos) for pos in positions]
    bind_joints = [str(joint) for joint in bind_joints]

    return {
        "positions": positions,
        "bind_joints": bind_joints,
    }


def parse_skeleton(usd_path: Path) -> Dict:
    """Parse skeletal USD to extract joint names and positions."""
    stage = Usd.Stage.Open(str(usd_path))

    # Find skeleton prim
    skeleton = None
    for prim in stage.Traverse():
        if prim.IsA(UsdSkel.Skeleton):
            skeleton = UsdSkel.Skeleton(prim)
            break

    if not skeleton:
        raise ValueError("Skeleton not found in USD")

    # Extract joint names
    joints_attr = skeleton.GetJointsAttr()
    joint_names = [str(name) for name in joints_attr.Get()]

    # Extract bind transforms (world positions)
    bind_transforms_attr = skeleton.GetBindTransformsAttr()
    bind_transforms = bind_transforms_attr.Get()

    # Extract joint positions
    joint_positions = {}
    for joint_name, transform in zip(joint_names, bind_transforms):
        translation = transform.ExtractTranslation()
        joint_positions[joint_name] = (
            float(translation[0]),
            float(translation[1]),
            float(translation[2]),
        )

    # Build bone segments (start, end) for each joint
    joint_segments = {}
    for joint_name in joint_names:
        if "/" in joint_name:
            # Joint has parent - create segment from parent to this joint
            parent_path = joint_name.rsplit("/", 1)[0]
            if parent_path in joint_positions and joint_name in joint_positions:
                joint_segments[joint_name] = (
                    joint_positions[parent_path],  # start (parent)
                    joint_positions[joint_name],  # end (this joint)
                )
        else:
            # Root joint - segment from origin to root
            if joint_name in joint_positions:
                joint_segments[joint_name] = (
                    (0.0, 0.0, 0.0),  # start (origin)
                    joint_positions[joint_name],  # end (root)
                )

    return {
        "joint_names": joint_names,
        "joint_positions": joint_positions,
        "joint_segments": joint_segments,
    }


def find_nearest_joint_globally(
    twig_position: Tuple[float, float, float],
    joint_segments: Dict[
        str, Tuple[Tuple[float, float, float], Tuple[float, float, float]]
    ],
) -> Tuple[str, float]:
    """Find the nearest joint to a twig position across ALL joints."""
    min_distance = float("inf")
    nearest_joint = None

    for joint_path, (start_point, end_point) in joint_segments.items():
        distance = point_to_segment_distance(twig_position, start_point, end_point)

        if distance < min_distance:
            min_distance = distance
            nearest_joint = joint_path

    return nearest_joint, min_distance


def extract_branch_id_from_joint(joint_path: str) -> int | None:
    """Extract branch_id from joint path (e.g., 'tree_root/joint_1/branch_2' -> 2)."""
    parts = joint_path.split("/")
    for part in reversed(parts):
        if part.startswith("branch_"):
            try:
                return int(part.split("_")[1])
            except (ValueError, IndexError):
                pass
    return None


def find_joints_in_branch_lineage(branch_id: int, joint_names: List[str]) -> List[str]:
    """Find all joints that are part of a branch's lineage (ancestors + descendants)."""
    branch_name = f"branch_{branch_id}"

    # Find the branch root joint
    branch_root = None
    for joint_path in joint_names:
        if joint_path.endswith(f"/{branch_name}") or joint_path == branch_name:
            branch_root = joint_path
            break

    if not branch_root:
        return []

    # Include all ancestors of branch root (trunk path to this branch)
    branch_joints = []
    parts = branch_root.split("/")
    for i in range(1, len(parts) + 1):
        ancestor = "/".join(parts[:i])
        if ancestor in joint_names:
            branch_joints.append(ancestor)

    # Add all descendants of branch root (joints within the branch)
    for joint_path in joint_names:
        if joint_path.startswith(f"{branch_root}/"):
            branch_joints.append(joint_path)

    return branch_joints


def find_nearest_joint_in_branch(
    twig_position: Tuple[float, float, float],
    branch_id: int,
    joint_names: List[str],
    joint_segments: Dict[
        str, Tuple[Tuple[float, float, float], Tuple[float, float, float]]
    ],
) -> Tuple[str, float]:
    """Find the nearest joint to a twig position within its branch lineage."""
    branch_joints = find_joints_in_branch_lineage(branch_id, joint_names)

    if not branch_joints:
        return "tree_root", float("inf")

    min_distance = float("inf")
    nearest_joint = branch_joints[0]

    for joint_path in branch_joints:
        if joint_path not in joint_segments:
            continue

        start_point, end_point = joint_segments[joint_path]
        distance = point_to_segment_distance(twig_position, start_point, end_point)

        if distance < min_distance:
            min_distance = distance
            nearest_joint = joint_path

    return nearest_joint, min_distance


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_twig_binding.py <nanite_assembly.usda>")
        sys.exit(1)

    assembly_path = Path(sys.argv[1])
    if not assembly_path.exists():
        print(f"Error: {assembly_path} not found")
        sys.exit(1)

    # Derive skeletal USD path
    skeletal_path = assembly_path.parent / assembly_path.name.replace(
        "_nanite_assembly.usda", "_skeletal.usda"
    )
    if not skeletal_path.exists():
        print(f"Error: {skeletal_path} not found")
        sys.exit(1)

    print("=" * 80)
    print("TWIG BINDING VALIDATION TEST")
    print("=" * 80)
    print(f"Assembly: {assembly_path.name}")
    print(f"Skeleton: {skeletal_path.name}")
    print()

    # Parse files
    print("Parsing USD files...")
    assembly_data = parse_nanite_assembly(assembly_path)
    skeleton_data = parse_skeleton(skeletal_path)

    positions = assembly_data["positions"]
    actual_bindings = assembly_data["bind_joints"]
    joint_names = skeleton_data["joint_names"]
    joint_segments = skeleton_data["joint_segments"]

    print(f"Found {len(positions)} twigs")
    print(f"Found {len(joint_names)} joints")
    print()

    # Analyze each twig
    print("=" * 80)
    print("TWIG BINDING ANALYSIS")
    print("=" * 80)

    mismatches = 0
    for i, (pos, actual_joint) in enumerate(zip(positions, actual_bindings)):
        print(f"\nTwig #{i}:")
        print(f"  Position: ({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f})")
        print(f"  Actual binding: {actual_joint}")

        # Always find globally nearest joint first
        global_nearest, global_dist = find_nearest_joint_globally(pos, joint_segments)
        print(f"  Global nearest: {global_nearest} (distance: {global_dist:.4f})")

        # Calculate distance to actual binding
        if actual_joint in joint_segments:
            start, end = joint_segments[actual_joint]
            actual_dist = point_to_segment_distance(pos, start, end)
            print(f"  Distance to actual binding: {actual_dist:.4f}")

            # Check if actual is significantly farther than global nearest
            if actual_dist > global_dist * 1.5:  # 50% tolerance
                print(
                    f"  ⚠️  POTENTIAL ISSUE: Bound joint is {actual_dist/global_dist:.1f}x farther than nearest!"
                )
                mismatches += 1

                # Show top 5 nearest joints for debugging
                distances = []
                for joint_path, (start_pt, end_pt) in joint_segments.items():
                    dist = point_to_segment_distance(pos, start_pt, end_pt)
                    distances.append((joint_path, dist))
                distances.sort(key=lambda x: x[1])

                print(f"  Top 5 nearest joints:")
                for j, d in distances[:5]:
                    marker = " <-- ACTUAL" if j == actual_joint else ""
                    marker += " <-- NEAREST" if j == global_nearest else ""
                    print(f"    {d:.4f}  {j}{marker}")
            else:
                print(f"  ✓ Binding seems reasonable")

        # Extract branch_id from actual joint
        branch_id = extract_branch_id_from_joint(actual_joint)
        if branch_id is not None:
            print(f"  Branch ID (from joint): {branch_id}")

            # Find expected nearest joint within branch lineage
            expected_joint, expected_dist = find_nearest_joint_in_branch(
                pos, branch_id, joint_names, joint_segments
            )
            print(
                f"  Expected (branch lineage): {expected_joint} (distance: {expected_dist:.4f})"
            )

            # Check if actual matches expected
            if actual_joint != expected_joint:
                print(f"  ⚠️  Within branch lineage, should be: {expected_joint}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total twigs: {len(positions)}")
    print(f"Correct bindings: {len(positions) - mismatches}")
    print(f"Incorrect bindings: {mismatches}")

    if mismatches > 0:
        print("\n⚠️  VALIDATION FAILED - Binding issues detected!")
        sys.exit(1)
    else:
        print("\n✓ VALIDATION PASSED - All bindings correct!")
        sys.exit(0)


if __name__ == "__main__":
    main()
