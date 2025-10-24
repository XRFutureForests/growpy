"""Inspect Grove skeleton API to understand full skeleton data structure."""

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
skeletons = grove.build_skeletons()
skeleton = skeletons[0]

print("Skeleton Object Inspection")
print("=" * 80)
print(f"Type: {type(skeleton)}")
print(f"\nAvailable attributes/methods:")
for attr in dir(skeleton):
    if not attr.startswith("_"):
        print(f"  - {attr}")

print("\n" + "=" * 80)
print("Skeleton Data:")
print("=" * 80)

# Check points
if hasattr(skeleton, "points"):
    points = skeleton.points
    print(f"\nPoints: {len(points)} total")
    print("First 5 points:")
    for i, pt in enumerate(points[:5]):
        print(f"  {i}: ({pt.x:.4f}, {pt.y:.4f}, {pt.z:.4f})")

# Check edges
if hasattr(skeleton, "edges"):
    edges = skeleton.edges
    print(f"\nEdges: {len(edges)} total")
    print("First 5 edges:")
    for i, edge in enumerate(edges[:5]):
        print(f"  {i}: {edge}")

# Check faces
if hasattr(skeleton, "faces"):
    faces = skeleton.faces
    print(f"\nFaces: {len(faces)} total")

# Check bone data
skeleton_length = 2.0
skeleton_reduce = 0.4
skeleton_bias = 0.5
skeleton_connected = True

bones = grove.tag_bone_id(
    skeleton_length,
    skeleton_reduce**2,
    skeleton_bias,
    skeleton_connected,
)

print(f"\nBones (tagged): {len(bones)} total")
print("\nFirst 3 bones:")
for i, bone in enumerate(bones[:3]):
    is_root, branch_id, start_pt, end_pt, r1, r2, connected, parent_branch = bone
    print(f"\nBone {i}:")
    print(f"  Branch: {branch_id}, Parent Branch: {parent_branch}")
    print(f"  Start: ({start_pt.x:.4f}, {start_pt.y:.4f}, {start_pt.z:.4f})")
    print(f"  End: ({end_pt.x:.4f}, {end_pt.y:.4f}, {end_pt.z:.4f})")
    print(f"  Connected: {connected}")

# Check if skeleton has connectivity info
print("\n" + "=" * 80)
print("Skeleton Connectivity:")
print("=" * 80)

if hasattr(skeleton, "edges") and len(skeleton.edges) > 0:
    print(f"\nEdges define connectivity between points")
    print("Sample edges (point_index1, point_index2):")
    for i, edge in enumerate(skeleton.edges[:10]):
        print(f"  Edge {i}: {edge}")
        print(f"  Edge {i}: {edge}")
