"""Blender-based automatic weight calculation for skeletal meshes.

Uses Blender's automatic weights algorithm (heat diffusion) to calculate
skinning weights that consider mesh topology, not just point-to-bone distance.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import bmesh
    import bpy
    from mathutils import Vector

    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False


def calculate_blender_weights(
    vertices: List[Tuple[float, float, float]],
    faces: List[List[int]],
    skeleton_points: List[Tuple[float, float, float]],
    skeleton_hierarchy: List[Tuple[int, int]],  # (child_idx, parent_idx) pairs
    point_to_joint: Dict[int, int],  # skeleton point index -> joint index
) -> Dict[int, List[Tuple[int, float]]]:
    """Calculate skinning weights using Blender's automatic weights.

    Args:
        vertices: List of (x, y, z) vertex positions
        faces: List of face vertex indices
        skeleton_points: List of (x, y, z) skeleton point positions
        skeleton_hierarchy: Parent relationships for skeleton
        point_to_joint: Mapping from skeleton point to joint index

    Returns:
        Dictionary mapping vertex index to list of (joint_index, weight) tuples
        sorted by descending weight
    """
    if not BLENDER_AVAILABLE:
        raise ImportError("Blender (bpy) is required for automatic weight calculation")

    # Clear existing scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Create mesh
    mesh = bpy.data.meshes.new("TreeMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    # Create mesh object
    obj = bpy.data.objects.new("TreeMesh", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Create armature
    armature = bpy.data.armatures.new("TreeSkeleton")
    armature_obj = bpy.data.objects.new("TreeSkeleton", armature)
    bpy.context.collection.objects.link(armature_obj)

    # Build bone hierarchy
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode="EDIT")

    # Create bones for each skeleton point
    bone_names = {}
    edit_bones = armature.edit_bones

    # First pass: create all bones
    for skel_idx, pos in enumerate(skeleton_points):
        joint_idx = point_to_joint.get(skel_idx)
        if joint_idx is None:
            continue

        bone_name = f"joint_{joint_idx}"
        bone = edit_bones.new(bone_name)
        bone.head = Vector(pos)

        # Set tail slightly offset (Blender requires head != tail)
        bone.tail = Vector((pos[0], pos[1], pos[2] + 0.1))

        bone_names[joint_idx] = bone_name

    # Second pass: set parent relationships
    for child_idx, parent_idx in skeleton_hierarchy:
        if child_idx in bone_names and parent_idx in bone_names:
            child_bone = edit_bones[bone_names[child_idx]]
            parent_bone = edit_bones[bone_names[parent_idx]]
            child_bone.parent = parent_bone

            # Connect child head to parent position
            child_bone.head = parent_bone.head

            # Set tail to actual child position
            child_pos = skeleton_points[child_idx]
            child_bone.tail = Vector(child_pos)

    bpy.ops.object.mode_set(mode="OBJECT")

    # Parent mesh to armature with automatic weights
    bpy.context.view_layer.objects.active = armature_obj
    obj.select_set(True)
    armature_obj.select_set(True)

    # Use automatic weights
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")

    # Extract weights from vertex groups
    vertex_weights = {}

    for v_idx in range(len(vertices)):
        vertex = obj.data.vertices[v_idx]
        weights = []

        for group in vertex.groups:
            # Get vertex group name
            group_name = obj.vertex_groups[group.group].name

            # Extract joint index from name (format: "joint_N")
            if group_name.startswith("joint_"):
                joint_idx = int(group_name.split("_")[1])
                weight = group.weight

                if weight > 0.0001:  # Skip negligible weights
                    weights.append((joint_idx, weight))

        # Sort by weight descending
        weights.sort(key=lambda x: x[1], reverse=True)

        # Normalize to ensure sum = 1.0
        if weights:
            total = sum(w for _, w in weights)
            if total > 0:
                weights = [(j, w / total) for j, w in weights]

        vertex_weights[v_idx] = weights

    return vertex_weights


def blender_weights_to_dual_joint(
    blender_weights: Dict[int, List[Tuple[int, float]]],
    num_vertices: int,
) -> Dict[int, List[Tuple[int, float]]]:
    """Convert Blender's multi-influence weights to dual-joint format.

    Blender can assign many bones per vertex. USD skeletal mesh typically
    uses 2 influences per vertex (elementSize=2). This function takes the
    top 2 influences and renormalizes.

    Args:
        blender_weights: Output from calculate_blender_weights
        num_vertices: Total number of vertices

    Returns:
        Dictionary with exactly 2 weights per vertex, summing to 1.0
    """
    dual_weights = {}

    for v_idx in range(num_vertices):
        weights = blender_weights.get(v_idx, [])

        if not weights:
            # No weights assigned - bind to root
            dual_weights[v_idx] = [(0, 1.0), (0, 0.0)]
        elif len(weights) == 1:
            # Only one influence - duplicate it
            joint_idx, weight = weights[0]
            dual_weights[v_idx] = [(joint_idx, 1.0), (joint_idx, 0.0)]
        else:
            # Take top 2 influences and renormalize
            top_two = weights[:2]
            total = sum(w for _, w in top_two)

            if total > 0:
                normalized = [(j, w / total) for j, w in top_two]
                dual_weights[v_idx] = normalized
            else:
                # Fallback to root
                dual_weights[v_idx] = [(0, 1.0), (0, 0.0)]

    return dual_weights
