"""Debug Grove bone structure to understand the data format."""

from pathlib import Path

import the_grove_22_core as gc

# Setup
random_seed = 42
preset_path = Path("data/assets/presets/Fagaceae - Beech.seed.json")
flushes = 2

# Create grove
grove = gc.Grove()
grove.clear_trees()
grove.set_random_seed(random_seed)

with open(preset_path, "r") as f:
    json_string = f.read()
properties = gc.io.properties_from_json_string(json_string)
grove.set_properties(properties)

# Add tree and simulate
position_vec = gc.Vector(0, 0, 0)
direction_vec = gc.Vector(0, 0, 1)
grove.add_new_tree(position_vec, direction_vec, 0)
grove.simulate(flushes)

# Build skeleton
skeleton_length = 0.05
skeleton_reduce = 0.01
skeleton_bias = 0.5
skeleton_connected = True

skeletons = grove.build_skeletons()
skeleton = skeletons[0]
bones = grove.tag_bone_id(
    skeleton_length,
    skeleton_reduce**2,
    skeleton_bias,
    skeleton_connected,
)

print("Bone Structure Analysis")
print("=" * 80)
print(f"Total bones: {len(bones)}")
print()

# Analyze first 15 bones
for i, bone in enumerate(bones[:15]):
    is_root, branch_id, start_pt, end_pt, r1, r2, connected, parent_branch = bone
    print(f"Bone {i}:")
    print(f"  Branch ID: {branch_id}, Parent Branch: {parent_branch}")
    print(f"  Start: ({start_pt.x:.4f}, {start_pt.y:.4f}, {start_pt.z:.4f})")
    print(f"  End:   ({end_pt.x:.4f}, {end_pt.y:.4f}, {end_pt.z:.4f})")
    print(f"  Connected: {connected}, Is Root: {is_root}")
    print()
    print()
