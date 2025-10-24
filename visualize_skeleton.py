"""Visualize bone hierarchy from USD skeletal file."""

import bpy

bpy.utils.expose_bundled_modules()

from pxr import Usd, UsdSkel

stage = Usd.Stage.Open("data/output/test_tree_skeletal.usda")
skel_prim = stage.GetPrimAtPath("/Tree/Skeleton/TreeSkel")
skel = UsdSkel.Skeleton(skel_prim)
joints = skel.GetJointsAttr().Get()
bind_transforms = skel.GetBindTransformsAttr().Get()

print("Bone Hierarchy Visualization:")
print("=" * 60)
for i, joint in enumerate(joints):
    depth = joint.count("/")
    indent = "  " * depth
    bone_name = joint.split("/")[-1]
    pos = bind_transforms[i].ExtractTranslation()
    print(f"{indent}{bone_name} @ ({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f})")

print("=" * 60)
print(f"Total bones: {len(joints)}")
print(f"Total bones: {len(joints)}")
