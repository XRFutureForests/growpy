#!/usr/bin/env python3
"""
Standalone skeleton export script.

This script MUST be run in a separate process without bpy to avoid DLL conflicts.
Do NOT import growpy or any module that imports bpy.
"""

import sys
from pathlib import Path


def export_skeleton_only(
    grove_json_path: Path,
    output_path: Path,
) -> bool:
    """Export skeleton-only USD file using pure pxr without bpy.

    Loads grove state from JSON to ensure exact matching with tree mesh.

    Args:
        grove_json_path: Path to grove JSON state file
        output_path: Path to save skeleton USD

    Returns:
        bool: True if export successful
    """
    try:
        # Import USD FIRST before any Grove imports
        from pxr import Gf, Sdf, Usd, UsdSkel, Vt

        # NOW import Grove API (but NOT growpy which imports bpy)
        sys.path.insert(
            0, str(Path(__file__).parent.parent.parent / "the_grove_22" / "modules")
        )
        import the_grove_22_core as gc

        # Load grove state from JSON
        with open(grove_json_path, "r") as f:
            grove_json = f.read()

        properties = gc.io.properties_from_json_string(grove_json)
        grove = gc.Grove()
        grove.set_properties(properties)

        # Build skeleton
        skeletons = grove.build_skeletons()
        if not skeletons or len(skeletons) == 0:
            print(f"    Warning: No skeleton data available")
            return False

        skeleton_data = skeletons[0]

        # Create USD stage
        stage = Usd.Stage.CreateNew(str(output_path))

        # Create SkelRoot
        skel_root_path = Sdf.Path("/SkelRoot")
        skel_root_prim = UsdSkel.Root.Define(stage, skel_root_path)

        # Create skeleton
        skel_path = skel_root_path.AppendChild("Skeleton")
        skel_prim = UsdSkel.Skeleton.Define(stage, skel_path)

        # Build joint hierarchy
        points = skeleton_data.points
        poly_lines = skeleton_data.poly_lines

        joints = []
        joint_parents = []
        bind_transforms = []
        rest_transforms = []

        joints.append("Root")
        joint_parents.append(-1)
        root_transform = Gf.Matrix4d().SetIdentity()
        bind_transforms.append(root_transform)
        rest_transforms.append(root_transform)

        joint_positions = {}
        joint_positions[0] = Gf.Vec3d(0, 0, 0)
        point_to_joint = {}

        for line in poly_lines:
            parent_joint_idx = 0
            for i, point_idx in enumerate(line):
                if point_idx not in point_to_joint:
                    joint_name = f"Joint_{point_idx}"
                    joint_idx = len(joints)
                    joints.append(joint_name)
                    joint_parents.append(parent_joint_idx)

                    point_pos = points[point_idx]
                    parent_pos = joint_positions[parent_joint_idx]
                    relative_pos = Gf.Vec3d(
                        point_pos[0] - parent_pos[0],
                        point_pos[1] - parent_pos[1],
                        point_pos[2] - parent_pos[2],
                    )

                    local_transform = Gf.Matrix4d().SetIdentity()
                    local_transform.SetTranslateOnly(relative_pos)
                    bind_transforms.append(local_transform)
                    rest_transforms.append(local_transform)

                    joint_positions[joint_idx] = Gf.Vec3d(
                        point_pos[0], point_pos[1], point_pos[2]
                    )
                    point_to_joint[point_idx] = joint_idx

                    parent_joint_idx = joint_idx
                else:
                    parent_joint_idx = point_to_joint[point_idx]

        # Set skeleton attributes
        skel_prim.CreateJointsAttr().Set(Vt.TokenArray(joints))
        skel_prim.CreateBindTransformsAttr().Set(Vt.Matrix4dArray(bind_transforms))
        skel_prim.CreateRestTransformsAttr().Set(Vt.Matrix4dArray(rest_transforms))

        # Create SkelAnimation
        anim_path = skel_root_path.AppendChild("Animation")
        anim = UsdSkel.Animation.Define(stage, anim_path)
        anim.CreateJointsAttr().Set(Vt.TokenArray(joints))
        anim.CreateTranslationsAttr().Set(
            Vt.Vec3fArray([Gf.Vec3f(0, 0, 0)] * len(joints))
        )
        anim.CreateRotationsAttr().Set(
            Vt.QuatfArray([Gf.Quatf(1, 0, 0, 0)] * len(joints))
        )
        anim.CreateScalesAttr().Set(Vt.Vec3hArray([Gf.Vec3h(1, 1, 1)] * len(joints)))

        skel_prim.GetPrim().GetRelationship("skel:animationSource").SetTargets(
            [anim_path]
        )

        stage.Save()
        print(f"    ✓ Exported skeleton USD ({len(joints)} joints): {output_path.name}")
        return True

    except ImportError as e:
        print(f"    ERROR: Cannot import USD - {e}")
        return False
    except Exception as e:
        print(f"    ERROR: Failed to export skeleton - {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """CLI entry point for standalone skeleton export."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Export skeleton-only USD from grove JSON (no bpy dependency)"
    )
    parser.add_argument(
        "grove_json_path", type=Path, help="Path to grove JSON state file"
    )
    parser.add_argument("output_path", type=Path, help="Output USD file path")

    args = parser.parse_args()

    success = export_skeleton_only(args.grove_json_path, args.output_path)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
