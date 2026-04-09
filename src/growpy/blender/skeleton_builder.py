"""Skeleton building for USD export.

Builds UsdSkel hierarchy from Grove bone data, filters unused bones,
and calculates vertex skinning weights with junction blending.
Self-contained -- no imports from growpy.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

UNREAL_MAX_BONE_INDEX = 32767


def filter_bones_for_mesh(
    model: Any,
    bones_info: List[Tuple],
    bone_id_offset: int = 0,
) -> Tuple[List[Tuple], Dict[int, int]]:
    """Filter bones_info to only include bones referenced by mesh vertices.

    Prevents Unreal crashes caused by vertices referencing non-existent bones.

    Returns (filtered_bones_info, old_to_new_bone_map).
    """
    if not hasattr(model, "point_attribute_bone_id"):
        return bones_info, {i + bone_id_offset: i for i in range(len(bones_info))}

    vertex_bone_ids = set(model.point_attribute_bone_id)
    referenced_bones = set()
    bones_dict = {bone_id_offset + i: bone for i, bone in enumerate(bones_info)}

    def _add_with_parents(gid: int) -> None:
        if gid in referenced_bones or gid not in bones_dict:
            return
        referenced_bones.add(gid)
        parent = bones_dict[gid][1]
        if parent != gid:
            _add_with_parents(parent)

    for bid in vertex_bone_ids:
        _add_with_parents(bid)

    if bones_info:
        referenced_bones.add(bone_id_offset)

    original_parent = {bone_id_offset + i: int(b[1]) for i, b in enumerate(bones_info)}

    old_to_new: Dict[int, int] = {}
    filtered = []
    filtered_gids = []
    idx = 0

    for local_idx, bone in enumerate(bones_info):
        gid = bone_id_offset + local_idx
        if gid in referenced_bones:
            old_to_new[gid] = idx
            filtered.append(bone)
            filtered_gids.append(gid)
            idx += 1

    def _find_ancestor(gid: int) -> int:
        visited = set()
        cur = original_parent.get(gid, -1)
        while cur >= 0 and cur != gid:
            if cur in old_to_new:
                return old_to_new[cur]
            if cur in visited:
                break
            visited.add(cur)
            cur = original_parent.get(cur, -1)
        return 0

    updated = []
    for bone, gid in zip(filtered, filtered_gids):
        is_tree_root, parent_id, sp, ep, radius, mass, is_branch_root, branch_id = bone
        new_parent = old_to_new.get(parent_id, _find_ancestor(gid))
        updated.append(
            (is_tree_root, new_parent, sp, ep, radius, mass, is_branch_root, branch_id)
        )

    if len(updated) > UNREAL_MAX_BONE_INDEX:
        raise ValueError(
            f"Tree has {len(updated)} bones, exceeding Unreal's limit of "
            f"{UNREAL_MAX_BONE_INDEX}. Use higher build_cutoff values to reduce bone count."
        )

    return updated, old_to_new


def calculate_vertex_weights(
    model: Any,
    bone_to_joint_map: Dict[int, int],
    bones_info: List[Tuple],
    element_size: int = 2,
    junction_blend_distance: float = 0.5,
    blend_mode: str = "linear",
) -> Tuple[List[int], List[float]]:
    """Calculate vertex skinning weights with reduced branch root weights.

    Returns (joint_indices_flat, joint_weights_flat) with element_size entries per vertex.
    """
    if not hasattr(model, "point_attribute_bone_id") or not hasattr(model, "points"):
        return [], []

    bone_ids = model.point_attribute_bone_id
    points = model.points
    num_vertices = len(points)

    # Build branch topology for junction weight reduction
    branch_info: Dict[int, Tuple] = {}
    for gid, lidx in bone_to_joint_map.items():
        # Find bone in bones_info by local index (gid == lidx after filtering)
        if lidx < len(bones_info):
            bone = bones_info[lidx]
            branch_info[gid] = (
                bone[6],
                bone[1],
                bone[2],
                bone[3],
            )  # is_branch_root, parent, head, tail

    joint_indices = []
    joint_weights = []

    for i in range(num_vertices):
        bid = bone_ids[i]
        joint_idx = bone_to_joint_map.get(bid, 0)

        if element_size == 2:
            # Dual-bone binding: primary bone + parent for junction blending
            parent_joint = 0
            weight = 1.0

            if joint_idx < len(bones_info) and bones_info[joint_idx][6]:
                # Branch root bone: reduce weight based on distance to junction
                bone = bones_info[joint_idx]
                parent_joint = bone[1]
                if junction_blend_distance > 0:
                    sp = bone[2]
                    p = points[i]
                    dx = p.x - sp.x
                    dy = p.y - sp.y
                    dz = p.z - sp.z
                    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                    t = min(1.0, dist / junction_blend_distance)
                    if blend_mode == "smooth":
                        t = t * t * (3.0 - 2.0 * t)
                    elif blend_mode == "cosine":
                        t = (1.0 - math.cos(t * math.pi)) * 0.5
                    weight = 0.5 + 0.5 * t

            joint_indices.extend([joint_idx, parent_joint])
            joint_weights.extend([weight, 1.0 - weight])
        else:
            joint_indices.append(joint_idx)
            joint_weights.append(1.0)

    return joint_indices, joint_weights


def build_joint_hierarchy(
    bones_info: List[Tuple],
    bone_id_offset: int = 0,
) -> Tuple[List[str], List["Any"], List["Any"], Dict[int, str]]:
    """Build joint tokens and transforms from bones_info.

    Returns (joint_tokens, bind_transforms, rest_transforms, bone_id_to_joint_path).
    Transform values are (tx, ty, tz) tuples (translation only).
    """
    joint_tokens = []
    bind_positions = []  # World-space positions
    rest_positions = []  # Parent-relative positions
    bone_id_to_joint_path: Dict[int, str] = {}
    bone_positions: Dict[int, Tuple[float, float, float]] = {}

    branch_id_offset = (
        int(bones_info[0][7]) if bones_info and len(bones_info[0]) >= 8 else 0
    )

    for bone_idx, bone in enumerate(bones_info):
        is_tree_root, parent_id, sp, ep, radius, mass, is_branch_root, branch_id = bone
        gid = bone_id_offset + bone_idx
        local_branch = int(branch_id) - branch_id_offset

        pos = (sp.x, sp.y, sp.z)
        bone_positions[gid] = pos

        if bone_idx == 0:
            joint_path = "tree_root"
        elif is_branch_root:
            parent_path = bone_id_to_joint_path.get(parent_id, "tree_root")
            joint_path = f"{parent_path}/branch_{local_branch}"
        else:
            parent_path = bone_id_to_joint_path.get(parent_id, "tree_root")
            joint_path = f"{parent_path}/joint_{bone_idx}"

        bone_id_to_joint_path[gid] = joint_path
        joint_tokens.append(joint_path)

        # Bind transform: world-space (tree-local)
        bind_positions.append(pos)

        # Rest transform: relative to parent
        if bone_idx == 0:
            rest_positions.append((0.0, 0.0, 0.0))
        else:
            pp = bone_positions.get(parent_id, (0.0, 0.0, 0.0))
            rest_positions.append((pos[0] - pp[0], pos[1] - pp[1], pos[2] - pp[2]))

    return joint_tokens, bind_positions, rest_positions, bone_id_to_joint_path
