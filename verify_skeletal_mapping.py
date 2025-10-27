#!/usr/bin/env python3
"""
Verify skeletal mapping quality by analyzing vertex-to-joint assignments.
"""

import sys

from pxr import Sdf, Usd, UsdGeom, UsdSkel


def verify_skeletal_mapping(usd_file):
    """Analyze and report on skeletal mapping quality."""
    stage = Usd.Stage.Open(usd_file)
    if not stage:
        print(f"ERROR: Failed to open {usd_file}")
        return False

    # Find the tree mesh
    tree_mesh_path = None
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            tree_mesh_path = prim.GetPath()
            break

    if not tree_mesh_path:
        print("ERROR: No mesh found in USD file")
        return False

    mesh = UsdGeom.Mesh(stage.GetPrimAtPath(tree_mesh_path))
    points = mesh.GetPointsAttr().Get()

    # Get skeleton
    skel_path = None
    for prim in stage.Traverse():
        if prim.IsA(UsdSkel.Skeleton):
            skel_path = prim.GetPath()
            break

    if not skel_path:
        print("ERROR: No skeleton found")
        return False

    skeleton = UsdSkel.Skeleton(stage.GetPrimAtPath(skel_path))
    joints = skeleton.GetJointsAttr().Get()
    bind_transforms = skeleton.GetBindTransformsAttr().Get()

    print(f"\n=== Skeletal Mapping Analysis ===")
    print(f"File: {usd_file}")
    print(f"Mesh: {tree_mesh_path}")
    print(f"Skeleton: {skel_path}")
    print(f"Total Vertices: {len(points)}")
    print(f"Total Joints: {len(joints)}")
    print(f"\nJoint Hierarchy:")

    for i, joint in enumerate(joints):
        bind_pos = bind_transforms[i].ExtractTranslation()
        print(
            f"  {joint}: position = ({bind_pos[0]:.4f}, {bind_pos[1]:.4f}, {bind_pos[2]:.4f})"
        )

    # Get joint indices and weights
    primvars_api = UsdGeom.PrimvarsAPI(mesh.GetPrim())
    joint_indices_primvar = primvars_api.GetPrimvar("skel:jointIndices")
    joint_weights_primvar = primvars_api.GetPrimvar("skel:jointWeights")

    if not joint_indices_primvar or not joint_weights_primvar:
        print("\nERROR: Missing joint indices or weights")
        return False

    joint_indices = joint_indices_primvar.Get()
    joint_weights = joint_weights_primvar.Get()

    print(f"\n=== Vertex-to-Joint Binding Analysis ===")

    # Count vertices per joint
    joint_vertex_counts = {}
    for i, joint_idx in enumerate(joint_indices):
        if joint_idx not in joint_vertex_counts:
            joint_vertex_counts[joint_idx] = []
        joint_vertex_counts[joint_idx].append(i)

    print(f"\nVertices per Joint:")
    for joint_idx in sorted(joint_vertex_counts.keys()):
        vertex_list = joint_vertex_counts[joint_idx]
        joint_name = joints[joint_idx]

        # Calculate Z-range for vertices bound to this joint
        z_values = [points[v][2] for v in vertex_list]
        min_z = min(z_values)
        max_z = max(z_values)

        print(f"  {joint_name} (joint_{joint_idx}): {len(vertex_list)} vertices")
        print(f"    Z-range: [{min_z:.4f}, {max_z:.4f}]")
        print(f"    Vertex indices: {min(vertex_list)}-{max(vertex_list)}")

    # Check for issues
    print(f"\n=== Quality Checks ===")

    # Check 1: Are all vertices assigned?
    if len(joint_indices) != len(points):
        print(
            f"  WARNING: Joint indices count ({len(joint_indices)}) != vertex count ({len(points)})"
        )
    else:
        print(f"  OK: All {len(points)} vertices have joint assignments")

    # Check 2: Are weights normalized?
    weight_issues = 0
    for i, weight in enumerate(joint_weights):
        if abs(weight - 1.0) > 0.01:
            weight_issues += 1

    if weight_issues > 0:
        print(f"  WARNING: {weight_issues} vertices have non-unit weights")
    else:
        print(f"  OK: All weights are 1.0 (rigid binding)")

    # Check 3: Z-ordering consistency
    print(f"\n  Z-Ordering Check:")
    consistent = True
    for joint_idx in sorted(joint_vertex_counts.keys()):
        vertex_list = joint_vertex_counts[joint_idx]
        z_values = [points[v][2] for v in vertex_list]
        min_z = min(z_values)
        max_z = max(z_values)

        # Check if this joint's Z-range overlaps with previous joint
        if joint_idx > 0 and joint_idx - 1 in joint_vertex_counts:
            prev_vertices = joint_vertex_counts[joint_idx - 1]
            prev_z_max = max([points[v][2] for v in prev_vertices])

            if min_z < prev_z_max:
                print(
                    f"    WARNING: {joints[joint_idx]} Z-range overlaps with {joints[joint_idx-1]}"
                )
                consistent = False

    if consistent:
        print(f"    OK: Z-ordering is consistent (no overlaps)")

    print(f"\n=== Summary ===")
    print(
        f"Skeletal binding appears {'CORRECT' if consistent and weight_issues == 0 else 'to have ISSUES'}"
    )

    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python verify_skeletal_mapping.py <usd_file>")
        sys.exit(1)

    success = verify_skeletal_mapping(sys.argv[1])
    sys.exit(0 if success else 1)
    sys.exit(0 if success else 1)
