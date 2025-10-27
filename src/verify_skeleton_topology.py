#!/usr/bin/env python3
"""
Verify USD skeleton topology for tree and twig files.

Checks for presence of all required UsdSkel attributes:
- uniform token[] joints
- uniform int[] jointIndices (CRITICAL for Unreal)
- uniform matrix4d[] bindTransforms
- uniform matrix4d[] restTransforms
"""

import sys
from pathlib import Path

try:
    from pxr import Sdf, Usd, UsdSkel
except ImportError:
    print("ERROR: USD Python library not available")
    print("Install with: pip install usd-core")
    sys.exit(1)


def check_skeleton_topology(usd_file):
    """Check if USD file has complete skeleton topology."""

    stage = Usd.Stage.Open(str(usd_file))
    if not stage:
        return False, "Failed to open USD file"

    # Find all Skeleton prims
    skeletons = []
    for prim in stage.Traverse():
        if prim.IsA(UsdSkel.Skeleton):
            skeletons.append(prim)

    if not skeletons:
        return False, "No Skeleton prims found"

    results = []
    all_valid = True

    for skel_prim in skeletons:
        skel = UsdSkel.Skeleton(skel_prim)
        path = skel_prim.GetPath()

        # Check for required attributes
        has_joints = skel.GetJointsAttr() is not None
        has_joint_indices = skel_prim.HasAttribute("jointIndices")
        has_bind_transforms = skel.GetBindTransformsAttr() is not None
        has_rest_transforms = skel.GetRestTransformsAttr() is not None

        # Get attribute values for reporting
        joints = []
        joint_indices = []

        if has_joints:
            joints = skel.GetJointsAttr().Get()

        if has_joint_indices:
            joint_indices_attr = skel_prim.GetAttribute("jointIndices")
            joint_indices = joint_indices_attr.Get()

        # Check variability of jointIndices
        joint_indices_uniform = False
        if has_joint_indices:
            attr = skel_prim.GetAttribute("jointIndices")
            joint_indices_uniform = attr.GetVariability() == Sdf.VariabilityUniform

        is_valid = all(
            [
                has_joints,
                has_joint_indices,
                has_bind_transforms,
                has_rest_transforms,
                joint_indices_uniform,
            ]
        )

        results.append(
            {
                "path": str(path),
                "is_valid": is_valid,
                "has_joints": has_joints,
                "has_joint_indices": has_joint_indices,
                "has_bind_transforms": has_bind_transforms,
                "has_rest_transforms": has_rest_transforms,
                "joint_indices_uniform": joint_indices_uniform,
                "joints": joints,
                "joint_indices": joint_indices,
            }
        )

        if not is_valid:
            all_valid = False

    return all_valid, results


def print_results(usd_file, is_valid, results):
    """Print verification results."""

    print(f"\n{'='*80}")
    print(f"File: {usd_file.name}")
    print(f"{'='*80}")

    if isinstance(results, str):
        # Error message
        print(f"✗ ERROR: {results}")
        return

    # Print skeleton details
    for result in results:
        status = "✓ VALID" if result["is_valid"] else "✗ INVALID"
        print(f"\n{status} - Skeleton: {result['path']}")
        print(f"  Joints: {len(result['joints'])} joints")
        print(
            f"    Names: {list(result['joints'][:5])}"
            + (
                f" ... (+{len(result['joints'])-5})"
                if len(result["joints"]) > 5
                else ""
            )
        )

        print(f"\n  Required Attributes:")
        print(f"    {'✓' if result['has_joints'] else '✗'} uniform token[] joints")
        print(
            f"    {'✓' if result['has_joint_indices'] and result['joint_indices_uniform'] else '✗'} uniform int[] jointIndices {'' if result['joint_indices_uniform'] else '(NOT UNIFORM!)' if result['has_joint_indices'] else '(MISSING!)'}"
        )
        print(
            f"    {'✓' if result['has_bind_transforms'] else '✗'} uniform matrix4d[] bindTransforms"
        )
        print(
            f"    {'✓' if result['has_rest_transforms'] else '✗'} uniform matrix4d[] restTransforms"
        )

        if result["has_joint_indices"]:
            print(f"\n  Joint Topology (parent indices):")
            print(f"    {list(result['joint_indices'])}")
        else:
            print(
                f"\n  ✗ MISSING jointIndices - Unreal Engine will NOT parse skeleton correctly!"
            )

    # Overall summary
    print(f"\n{'='*80}")
    if is_valid:
        print("✓ ALL SKELETONS VALID - Ready for Unreal Engine")
    else:
        print("✗ SKELETON VALIDATION FAILED - Fix required before Unreal import")
    print(f"{'='*80}\n")


def main():
    """Main entry point."""

    if len(sys.argv) < 2:
        print("Usage: python verify_skeleton_topology.py <usd_file_or_directory>")
        print("\nExamples:")
        print("  python verify_skeleton_topology.py tree_skel.usda")
        print(
            "  python verify_skeleton_topology.py data/output/minimal_clean/Western_redcedar/"
        )
        sys.exit(1)

    path = Path(sys.argv[1])

    if not path.exists():
        print(f"ERROR: Path not found: {path}")
        sys.exit(1)

    # Collect USD files
    usd_files = []
    if path.is_file():
        usd_files = [path]
    else:
        # Find all skeletal USD files
        usd_files = sorted(path.glob("*_skel.usda"))
        if not usd_files:
            usd_files = sorted(path.glob("*.usda"))

    if not usd_files:
        print(f"ERROR: No USD files found in: {path}")
        sys.exit(1)

    print(f"\nVerifying {len(usd_files)} USD file(s)...\n")

    # Check each file
    all_valid = True
    for usd_file in usd_files:
        is_valid, results = check_skeleton_topology(usd_file)
        print_results(usd_file, is_valid, results)
        if not is_valid:
            all_valid = False

    # Exit with appropriate code
    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
