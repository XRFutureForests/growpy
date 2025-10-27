#!/usr/bin/env python3
"""
Verify skeleton hierarchy in tree USD file.
Checks that jointIndices properly define parent-child relationships.
"""

import re

# Read the USD file
with open(
    "data/output/skeletal_test/Western_redcedar/Western_redcedar_tree_0000_tree_only_skeletal.usda",
    "r",
) as f:
    content = f.read()

# Extract joint names
joints_match = re.search(r"uniform token\[\] joints = \[(.*?)\]", content, re.DOTALL)
if joints_match:
    joints_str = joints_match.group(1)
    joints = re.findall(r'"(joint_\d+)"', joints_str)
    print(f"✓ Found {len(joints)} joints")
else:
    print("✗ No joints found")
    exit(1)

# Extract joint indices (parent indices)
indices_match = re.search(
    r"uniform int\[\] jointIndices = \[(.*?)\]", content, re.DOTALL
)
if indices_match:
    indices_str = indices_match.group(1)
    joint_indices = [int(x.strip()) for x in indices_str.split(",")]
    print(f"✓ Found {len(joint_indices)} joint indices")
else:
    print("✗ No joint indices found")
    exit(1)

# Verify lengths match
if len(joints) != len(joint_indices):
    print(f"✗ Mismatch: {len(joints)} joints but {len(joint_indices)} indices")
    exit(1)

print(f"\n✓ Joint count matches index count")

# Build hierarchy
print("\n" + "=" * 60)
print("SKELETON HIERARCHY (first 20 joints)")
print("=" * 60)

for i in range(min(20, len(joints))):
    parent_idx = joint_indices[i]
    indent = "  " * (i // 5)  # Simple indent for visualization
    if parent_idx == -1:
        print(f"{indent}{i}: {joints[i]} (ROOT)")
    else:
        parent_name = (
            joints[parent_idx] if parent_idx < len(joints) else f"INVALID_{parent_idx}"
        )
        print(f"{indent}{i}: {joints[i]} ← parent: {parent_name} ({parent_idx})")

# Check for invalid parent indices
print("\n" + "=" * 60)
print("VALIDATION")
print("=" * 60)

invalid_count = 0
for i, parent_idx in enumerate(joint_indices):
    if parent_idx != -1 and (parent_idx < 0 or parent_idx >= len(joints)):
        print(f"✗ Joint {i} ({joints[i]}) has invalid parent index: {parent_idx}")
        invalid_count += 1
    elif parent_idx >= i:
        print(
            f"✗ Joint {i} ({joints[i]}) has parent {parent_idx} that comes after it (circular reference)"
        )
        invalid_count += 1

if invalid_count == 0:
    print("✓ All parent indices are valid")
    print("✓ No circular references detected")
else:
    print(f"✗ Found {invalid_count} invalid parent relationships")

# Count root joints (should be 1)
root_count = sum(1 for idx in joint_indices if idx == -1)
print(f"\n{'✓' if root_count == 1 else '✗'} Root joints: {root_count} (expected: 1)")

# Check mesh binding
mesh_joint_indices_match = re.search(
    r"int\[\] primvars:skel:jointIndices = \[(.*?)\]", content, re.DOTALL
)
if mesh_joint_indices_match:
    mesh_indices_str = mesh_joint_indices_match.group(1)
    # Count unique joints referenced by mesh
    mesh_joint_values = [
        int(x.strip()) for x in mesh_indices_str.split(",") if x.strip().isdigit()
    ]
    unique_mesh_joints = set(mesh_joint_values)
    print(
        f"\n✓ Mesh vertices reference {len(unique_mesh_joints)} unique joints (out of {len(joints)} total)"
    )

    # Check if all mesh joint indices are valid
    invalid_mesh_joints = [j for j in unique_mesh_joints if j < 0 or j >= len(joints)]
    if invalid_mesh_joints:
        print(f"✗ Mesh has invalid joint indices: {invalid_mesh_joints[:10]}")
    else:
        print("✓ All mesh joint indices are valid")
else:
    print("✗ No mesh joint indices found")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Joints: {len(joints)}")
print(f"Joint hierarchy indices: {len(joint_indices)}")
print(f"Root joints: {root_count}")
print(f"Invalid parent indices: {invalid_count}")
print(
    "\nSkeleton structure appears "
    + ("✓ VALID" if invalid_count == 0 and root_count == 1 else "✗ INVALID")
)
