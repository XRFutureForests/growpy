"""Grove bone-based skeleton generation for USD export.

This module provides the correct implementation for building USD skeletons
from Grove's tag_bone_id() output, which returns actual bone segments with
head/tail positions.

Reference: The Grove 2.2 Blender Addon OperatorBuildSkeleton.py
"""

from pathlib import Path
from typing import Any, Optional

from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt


def add_skeleton_from_grove_bones(
    usd_path: Path,
    grove: Any,
    species_name: str,
    model: Optional[Any] = None,
    skeleton_length: float = 1.0,
    skeleton_reduce: float = 0.1,
    skeleton_bias: float = 0.5,
    skeleton_connected: bool = True,
) -> bool:
    """Add skeleton to USD file using Grove's tag_bone_id() bone data.

    This is the CORRECT approach - using Grove's actual bone segments with
    head/tail positions instead of trying to reconstruct from points/poly_lines.

    Args:
        usd_path: Path to USD file (should already have materials)
        grove: Grove instance with tree data
        species_name: Species name for identification
        model: Optional model for skinning weights
        skeleton_length: Bone length multiplier (default: 1.0)
        skeleton_reduce: Bone reduction factor (default: 0.1, higher=fewer bones)
        skeleton_bias: Weight bias for skinning (default: 0.5, range 0-1)
        skeleton_connected: Use connected bone hierarchy (default: True)

    Returns:
        bool: True if skeleton added successfully

    Note:
        Grove's tag_bone_id() returns: [(bone_idx, parent_idx, head_Vector, tail_Vector, radius), ...]
        Each bone is a segment with:
        - bone[0]: bone index
        - bone[1]: parent bone index (-1 for root)
        - bone[2]: head position (Grove Vector)
        - bone[3]: tail position (Grove Vector)
        - bone[4]: radius
    """
    try:
        # Open USD stage
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            print(f"    Error: Could not open USD file: {usd_path}")
            return False

        # Stage should already be Z-up from mesh conversion
        # Just verify it's set correctly
        if UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.z:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

        # Find tree mesh and parent transform
        tree_mesh_prim = None
        tree_xform_prim = None
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                tree_mesh_prim = prim
                tree_xform_prim = stage.GetPrimAtPath(prim.GetPath().GetParentPath())
                break

        if not tree_mesh_prim or not tree_xform_prim:
            print(f"    Error: Could not find tree mesh in USD file")
            return False

        mesh = UsdGeom.Mesh(tree_mesh_prim)
        original_xform_path = tree_xform_prim.GetPath()

        print(f"  Adding skeleton to USD using Grove bone data...")

        # Get bone data from Grove (THE CORRECT WAY)
        bones_info = grove.tag_bone_id(
            skeleton_length, skeleton_reduce, skeleton_bias, skeleton_connected
        )

        if not bones_info or len(bones_info) == 0:
            print(f"    Warning: tag_bone_id() returned no bones")
            return False

        print(
            f"    [OK] Grove returned {len(bones_info)} bones with head/tail positions"
        )

        # Create SkelRoot
        skel_root_path = original_xform_path.AppendChild("SkelRoot")
        skel_root_prim = UsdSkel.Root.Define(stage, skel_root_path)
        UsdSkel.BindingAPI.Apply(skel_root_prim.GetPrim())

        # Create Skeleton
        skel_path = skel_root_path.AppendChild("Skeleton")
        skel_prim = UsdSkel.Skeleton.Define(stage, skel_path)

        # Apply Unreal Engine Control Rig API
        skel_api_schemas = Sdf.TokenListOp()
        skel_api_schemas.prependedItems = ["ControlRigAPI"]
        skel_prim.GetPrim().SetMetadata("apiSchemas", skel_api_schemas)

        # Build joint hierarchy from bone data
        joints = []
        joint_parents = []
        bind_transforms = []
        rest_transforms = []

        # Root joint
        joints.append("joint_0")
        joint_parents.append(-1)
        root_transform = Gf.Matrix4d().SetIdentity()
        bind_transforms.append(root_transform)
        rest_transforms.append(root_transform)

        # Map bone indices to joint indices for parent lookup
        bone_to_joint = {-1: 0}  # -1 (root bone) maps to joint 0

        # Track world-space positions for calculating relatives
        # Root joint (index 0) is at origin with zero length
        world_head_positions = {0: Gf.Vec3d(0, 0, 0)}
        world_tail_positions = {0: Gf.Vec3d(0, 0, 0)}

        # Process each bone
        # Grove returns list of tuples: (bone_id, parent_id, head_Vector, tail_Vector, radius)
        for i, bone in enumerate(bones_info):
            bone_idx = i  # Use enumeration index as bone ID
            parent_bone_idx = int(bone[1]) if bone[1] >= 0 else -1  # bone[1] is parent
            head_vec = bone[2]  # Grove Vector
            tail_vec = bone[3]  # Grove Vector
            radius = bone[4]

            # TEMP: No conversion - check what Grove actually returns
            head_tuple = head_vec.as_tuple()
            tail_tuple = tail_vec.as_tuple()
            world_head = Gf.Vec3d(head_tuple[0], head_tuple[1], head_tuple[2])
            world_tail = Gf.Vec3d(tail_tuple[0], tail_tuple[1], tail_tuple[2])

            # Find parent joint index
            parent_joint_idx = bone_to_joint.get(parent_bone_idx, 0)
            joint_parents.append(parent_joint_idx)

            # Create FLAT joint name (no hierarchy in name - use topology array instead)
            joint_idx = len(joints)
            joint_name = f"joint_{joint_idx}"
            joints.append(joint_name)
            bone_to_joint[bone_idx] = joint_idx

            # Get parent's position (where the parent bone starts)
            # For root, this is origin. For others, it's the parent bone's head position
            parent_pos = world_head_positions.get(parent_joint_idx, Gf.Vec3d(0, 0, 0))

            # Calculate position relative to parent's position
            # This is the offset from where parent bone starts to where this bone starts
            relative_pos = world_head - parent_pos

            # Calculate bone direction (from head to tail)
            bone_vector = world_tail - world_head
            bone_length = bone_vector.GetLength()

            if bone_length > 0.0001:  # Avoid division by zero
                bone_dir = bone_vector / bone_length

                # Default bone direction is +Z (Z-up vertical)
                default_dir = Gf.Vec3d(0, 0, 1)

                # Calculate rotation to align default direction with bone direction
                rotation = Gf.Rotation()
                rotation.SetRotateInto(default_dir, bone_dir)
                rotation_matrix = Gf.Matrix3d(rotation.GetQuat())

                # Create transform with both translation and rotation
                transform_with_rotation = Gf.Matrix4d().SetIdentity()
                transform_with_rotation.SetRotate(rotation_matrix)
                transform_with_rotation.SetTranslateOnly(relative_pos)

                bind_transforms.append(transform_with_rotation)
                rest_transforms.append(transform_with_rotation)
            else:
                # Zero-length bone, use identity
                local_transform = Gf.Matrix4d().SetIdentity()
                local_transform.SetTranslateOnly(relative_pos)
                bind_transforms.append(local_transform)
                rest_transforms.append(local_transform)

            # Store positions for child bones
            # Store this bone's HEAD (start) position, not tail
            # Children will calculate their offset from this position
            world_head_positions[joint_idx] = world_head
            world_tail_positions[joint_idx] = world_tail

        print(f"    [OK] Created {len(joints)} joints from {len(bones_info)} bones")

        # Set skeleton attributes with flat names
        skel_prim.CreateJointsAttr().Set(Vt.TokenArray(joints))
        skel_prim.CreateBindTransformsAttr().Set(Vt.Matrix4dArray(bind_transforms))
        skel_prim.CreateRestTransformsAttr().Set(Vt.Matrix4dArray(rest_transforms))

        # Add topology array (jointIndices) to preserve hierarchy with flat joint names
        # This is the USD-standard way to encode skeleton hierarchy
        try:
            # Try using official API first (newer USD versions)
            skel_prim.CreateJointIndicesAttr().Set(Vt.IntArray(joint_parents))
        except AttributeError:
            # Fallback for older USD versions
            from pxr import Sdf

            joint_indices_attr = skel_prim.GetPrim().CreateAttribute(
                "jointIndices",
                Sdf.ValueTypeNames.IntArray,
                custom=False,
                variability=Sdf.VariabilityUniform,
            )
            joint_indices_attr.Set(Vt.IntArray(joint_parents))

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

        # Link animation to skeleton
        skel_prim.GetPrim().GetRelationship("skel:animationSource").SetTargets(
            [anim_path]
        )

        # Calculate skinning weights if model provided
        if model is not None and hasattr(model, "point_attribute_bone_id"):
            print(f"    Adding skinning weights...")
            joint_indices_array = []
            joint_weights_array = []

            bone_ids = model.point_attribute_bone_id
            weights = (
                model.point_attribute_bone_weight
                if hasattr(model, "point_attribute_bone_weight")
                else [1.0] * len(bone_ids)
            )

            # CRITICAL: Use elementSize=2 to match reference USD format
            # Each vertex needs 2 joint influences (pad with 0/0.0 if only one)
            for bone_id, weight in zip(bone_ids, weights):
                joint_idx = bone_to_joint.get(bone_id, 0)
                joint_indices_array.extend([joint_idx, 0])  # Primary joint + padding
                joint_weights_array.extend([weight, 0.0])  # Primary weight + padding

            # Apply to mesh with elementSize=2
            binding = UsdSkel.BindingAPI.Apply(mesh.GetPrim())
            binding.CreateJointIndicesPrimvar(False, 2).Set(
                Vt.IntArray(joint_indices_array)
            )
            binding.CreateJointWeightsPrimvar(False, 2).Set(
                Vt.FloatArray(joint_weights_array)
            )
            binding.CreateGeomBindTransformAttr().Set(Gf.Matrix4d().SetIdentity())
            binding.CreateSkeletonRel().SetTargets([skel_path])

            print(
                f"    [OK] Added skinning weights for {len(joint_indices_array)//2} vertices with elementSize=2"
            )

        # Move mesh under SkelRoot
        new_mesh_path = skel_root_path.AppendChild(tree_mesh_prim.GetName())
        old_mesh_path = tree_mesh_prim.GetPath()

        if not Sdf.CopySpec(
            stage.GetRootLayer(),
            str(old_mesh_path),
            stage.GetRootLayer(),
            str(new_mesh_path),
        ):
            print(f"    Warning: Could not move mesh under SkelRoot")
            return False

        # Remove old mesh
        stage.RemovePrim(old_mesh_path)

        # Save
        stage.Save()
        print(f"  [OK] Skeleton added to USD file")

        return True

    except Exception as e:
        print(f"  Error adding skeleton: {e}")
        import traceback

        traceback.print_exc()
        return False
        return False
