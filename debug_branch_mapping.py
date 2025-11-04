"""Debug script to check branch_id mapping in bones_info."""

import sys
from pathlib import Path

import bpy

# Expose bundled modules
if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import the_grove_22_core as gc

from growpy.config import get_config

# Initialize
config = get_config()
grove = gc.Grove()

# Load seed
seed_path = Path("data/assets/presets/european_beech.seed.json")
grove.load_seed(str(seed_path))

# Add tree
grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

# Simulate
print("Simulating 2 growth cycles...")
for _ in range(2):
    grove.simulate()

# Build skeleton and tag bones
print("\nBuilding skeleton...")
grove.build_skeletons()
grove.tag_bone_id()

# Build models
print("Building models...")
build_options = {
    "resolution": 24,
    "resolution_reduce": 0.8,
    "texture_repeat": 3,
    "build_cutoff_age": 0,
    "build_cutoff_thickness": 0.001,
    "build_blend": True,
    "build_end_cap": True,
}
models = grove.build_models(build_options)
model = models[0]

# Get bones info
bones_info_list = grove.bones_info
bones_info = bones_info_list[0]  # First tree

print(f"\n=== BONES INFO ({len(bones_info)} bones) ===")
print(
    "Format: (is_tree_root, parent_bone_id, start_point, end_point, radius, mass, is_branch_root, branch_id)"
)

# Calculate offsets
first_bone = bones_info[0]
is_tree_root, parent_bone_id = first_bone[0], first_bone[1]
first_branch_id = first_bone[7]

if is_tree_root and parent_bone_id == 0:
    bone_id_offset = 0
elif is_tree_root:
    bone_id_offset = parent_bone_id
else:
    bone_id_offset = 0

branch_id_offset = first_branch_id

print(f"\nOffsets:")
print(f"  bone_id_offset: {bone_id_offset}")
print(f"  branch_id_offset: {branch_id_offset}")

# Build branch root mapping
branch_root_bones = {}
for bone_idx, bone in enumerate(bones_info):
    if len(bone) >= 8:
        is_branch_root = bone[6]
        global_branch_id = int(bone[7])
        local_branch_id = global_branch_id - branch_id_offset
        if is_branch_root:
            branch_root_bones[local_branch_id] = bone_idx

print(f"\n=== BRANCH ROOT MAPPING ({len(branch_root_bones)} branch roots) ===")
print("local_branch_id → bone_idx:")
for local_branch_id in sorted(branch_root_bones.keys()):
    bone_idx = branch_root_bones[local_branch_id]
    bone = bones_info[bone_idx]
    global_branch_id = int(bone[7])
    print(f"  {local_branch_id} → bone {bone_idx} (global branch {global_branch_id})")

# Check face branch IDs
if hasattr(model, "face_attribute_branch_id"):
    face_branch_ids = model.face_attribute_branch_id
    print(f"\n=== FACE BRANCH IDs ({len(face_branch_ids)} faces) ===")
    unique_global = sorted(set(face_branch_ids))
    print(f"Unique global branch IDs: {unique_global}")
    unique_local = sorted(set(b - branch_id_offset for b in face_branch_ids))
    print(f"Unique local branch IDs: {unique_local}")

    # Check for mismatches
    print("\n=== CHECKING FOR MISSING MAPPINGS ===")
    for face_idx, global_face_branch_id in enumerate(face_branch_ids):
        local_face_branch_id = global_face_branch_id - branch_id_offset
        if local_face_branch_id not in branch_root_bones:
            print(
                f"WARNING: Face {face_idx} has branch_id {local_face_branch_id} (global {global_face_branch_id}) but no branch root bone found!"
            )

# Check twig faces
print("\n=== TWIG FACE ANALYSIS ===")
for twig_type in ["twig_long", "twig_short", "twig_upward"]:
    attr_name = f"face_attribute_{twig_type}"
    if hasattr(model, attr_name):
        twig_values = getattr(model, attr_name)
        twig_face_indices = [i for i, v in enumerate(twig_values) if v > 0]
        print(f"\n{twig_type}: {len(twig_face_indices)} faces")

        if twig_face_indices and hasattr(model, "face_attribute_branch_id"):
            # Show first 10 twig faces
            for face_idx in twig_face_indices[:10]:
                global_branch_id = face_branch_ids[face_idx]
                local_branch_id = global_branch_id - branch_id_offset
                bone_idx = branch_root_bones.get(local_branch_id, None)
                print(
                    f"  Face {face_idx}: global_branch={global_branch_id}, local_branch={local_branch_id}, bone={bone_idx}"
                )

print("\n=== FIRST 20 BONES (with is_branch_root flag) ===")
for bone_idx in range(min(20, len(bones_info))):
    bone = bones_info[bone_idx]
    (
        is_tree_root,
        parent_bone_id,
        start_point,
        end_point,
        radius,
        mass,
        is_branch_root,
        global_branch_id,
    ) = bone
    local_branch_id = global_branch_id - branch_id_offset
    marker = "*** BRANCH ROOT ***" if is_branch_root else ""
    print(
        f"Bone {bone_idx}: parent={parent_bone_id}, global_branch={global_branch_id}, local_branch={local_branch_id}, is_branch_root={is_branch_root} {marker}"
    )
    marker = "*** BRANCH ROOT ***" if is_branch_root else ""
    print(
        f"Bone {bone_idx}: parent={parent_bone_id}, global_branch={global_branch_id}, local_branch={local_branch_id}, is_branch_root={is_branch_root} {marker}"
    )
