#!/usr/bin/env python3
"""
Verify UsdSkel hierarchy structure in generated USD files.

This script checks that skeletal USD files have the correct UsdSkel attributes
with proper naming and structure.

Usage:
    python verify_skeleton_hierarchy.py <path_to_skeletal.usda>
"""

import sys
from pathlib import Path

from pxr import Sdf, Usd, UsdSkel


def verify_skeleton_hierarchy(usd_path: Path) -> dict:
    """Verify skeleton hierarchy in USD file.

    Args:
        usd_path: Path to USD file to verify

    Returns:
        Dictionary with verification results
    """
    results = {
        "file": str(usd_path),
        "errors": [],
        "warnings": [],
        "info": {},
        "valid": False,
    }

    if not usd_path.exists():
        results["errors"].append(f"File not found: {usd_path}")
        return results

    try:
        stage = Usd.Stage.Open(str(usd_path))
    except Exception as e:
        results["errors"].append(f"Failed to open USD file: {e}")
        return results

    # Find skeleton prim
    skeleton_prim = None
    for prim in stage.Traverse():
        if prim.IsA(UsdSkel.Skeleton):
            skeleton_prim = prim
            break

    if not skeleton_prim:
        results["errors"].append("No Skeleton prim found in file")
        return results

    skeleton = UsdSkel.Skeleton(skeleton_prim)
    results["info"]["skeleton_path"] = str(skeleton.GetPath())

    # Check required attributes
    joints_attr = skeleton.GetJointsAttr()
    if not joints_attr:
        results["errors"].append("Missing 'joints' attribute")
    else:
        joints = joints_attr.Get()
        results["info"]["joint_count"] = len(joints) if joints else 0
        results["info"]["joints"] = list(joints[:5]) if joints else []  # Show first 5

    bind_transforms_attr = skeleton.GetBindTransformsAttr()
    if not bind_transforms_attr:
        results["errors"].append("Missing 'bindTransforms' attribute")
    else:
        bind_transforms = bind_transforms_attr.Get()
        results["info"]["bind_transform_count"] = (
            len(bind_transforms) if bind_transforms else 0
        )

    rest_transforms_attr = skeleton.GetRestTransformsAttr()
    if not rest_transforms_attr:
        results["errors"].append("Missing 'restTransforms' attribute")
    else:
        rest_transforms = rest_transforms_attr.Get()
        results["info"]["rest_transform_count"] = (
            len(rest_transforms) if rest_transforms else 0
        )

    # Check for jointIndices (topology array)
    joint_indices_attr = skeleton.GetPrim().GetAttribute("jointIndices")
    if not joint_indices_attr:
        results["errors"].append(
            "Missing 'jointIndices' topology attribute (parent hierarchy)"
        )
    else:
        # Check if it's uniform
        if joint_indices_attr.GetVariability() != Sdf.VariabilityUniform:
            results["warnings"].append("jointIndices should have 'uniform' variability")

        joint_indices = joint_indices_attr.Get()
        if joint_indices:
            results["info"]["topology_array_length"] = len(joint_indices)
            results["info"]["topology_sample"] = list(
                joint_indices[:10]
            )  # Show first 10

            # Verify topology makes sense
            if len(joint_indices) != results["info"].get("joint_count", 0):
                results["errors"].append(
                    f"Topology array length ({len(joint_indices)}) doesn't match joint count "
                    f"({results['info'].get('joint_count', 0)})"
                )

            # Check root joint
            if joint_indices[0] != -1:
                results["errors"].append(
                    f"First joint should have parent -1 (root), got {joint_indices[0]}"
                )

            # Check for invalid parent indices
            for i, parent_idx in enumerate(joint_indices):
                if parent_idx >= i:
                    results["errors"].append(
                        f"Joint {i} has invalid parent index {parent_idx} (must be < {i} or -1)"
                    )
        else:
            results["errors"].append("jointIndices attribute is empty")

    # Check for old incorrect naming
    joint_parents_attr = skeleton.GetPrim().GetAttribute("jointParents")
    if joint_parents_attr:
        results["warnings"].append(
            "Found deprecated 'jointParents' attribute - should be 'jointIndices'"
        )

    # Find bound mesh
    skel_root = None
    for prim in stage.Traverse():
        if prim.IsA(UsdSkel.Root):
            skel_root = prim
            break

    if skel_root:
        results["info"]["skel_root_path"] = str(skel_root.GetPath())

        # Find mesh with binding
        for prim in skel_root.GetChildren():
            if prim.IsA(UsdGeom.Mesh):
                binding_api = UsdSkel.BindingAPI(prim)
                if binding_api:
                    skel_rel = binding_api.GetSkeletonRel()
                    if skel_rel:
                        targets = skel_rel.GetTargets()
                        results["info"]["mesh_bound_to"] = [str(t) for t in targets]

                    # Check vertex skinning data
                    from pxr import UsdGeom

                    primvars_api = UsdGeom.PrimvarsAPI(prim)

                    joint_indices_primvar = primvars_api.GetPrimvar("skel:jointIndices")
                    if joint_indices_primvar:
                        results["info"]["vertex_binding_present"] = True
                        joint_indices_values = joint_indices_primvar.Get()
                        if joint_indices_values:
                            results["info"]["bound_vertex_count"] = len(
                                joint_indices_values
                            )
                            results["info"]["joint_index_range"] = (
                                min(joint_indices_values),
                                max(joint_indices_values),
                            )
                    else:
                        results["warnings"].append(
                            "Mesh has no skel:jointIndices (vertex binding)"
                        )
    else:
        results["warnings"].append("No SkelRoot found")

    # Overall validation
    results["valid"] = len(results["errors"]) == 0

    return results


def print_results(results: dict):
    """Print verification results in a readable format."""
    print("\n" + "=" * 60)
    print(f"Skeleton Hierarchy Verification")
    print("=" * 60)
    print(f"\nFile: {results['file']}")
    print(f"Status: {'✓ VALID' if results['valid'] else '✗ INVALID'}")

    if results["info"]:
        print("\n--- Information ---")
        for key, value in results["info"].items():
            print(f"  {key}: {value}")

    if results["warnings"]:
        print("\n--- Warnings ---")
        for warning in results["warnings"]:
            print(f"  ⚠ {warning}")

    if results["errors"]:
        print("\n--- Errors ---")
        for error in results["errors"]:
            print(f"  ✗ {error}")

    print("\n" + "=" * 60)

    if results["valid"]:
        print("✓ Skeleton structure is valid and ready for Unreal Engine!")
    else:
        print("✗ Skeleton has issues that need to be fixed.")
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nExample:")
        print(
            "  python verify_skeleton_hierarchy.py data/output/joint_indices_fix_test/Western_redcedar/Western_redcedar_tree_0000_tree_only_skeletal.usda"
        )
        sys.exit(1)

    usd_path = Path(sys.argv[1])
    results = verify_skeleton_hierarchy(usd_path)
    print_results(results)

    sys.exit(0 if results["valid"] else 1)


if __name__ == "__main__":
    main()
    main()
