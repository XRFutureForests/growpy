"""Validate Blender-calculated skinning weights."""

from pxr import Usd, UsdGeom, UsdSkel

stage = Usd.Stage.Open("data/output/test_assembly/western_redcedar_tree.usda")
mesh = UsdGeom.Mesh.Get(stage, "/western_redcedar/tree")
weights = mesh.GetPrim().GetAttribute("primvars:skel:jointWeights").Get()
indices = mesh.GetPrim().GetAttribute("primvars:skel:jointIndices").Get()

print("Skinning weight validation:")
print(f"Total weight entries: {len(weights)}")
print(f"Total index entries: {len(indices)}")
print(f"Vertices: {len(weights)//2}")
print()
print("First 10 vertices (joint pairs with weights):")
for i in range(0, 20, 2):
    j1, j2 = indices[i], indices[i + 1]
    w1, w2 = weights[i], weights[i + 1]
    total = w1 + w2
    print(
        f"  V{i//2}: joints[{j1:3d}, {j2:3d}] weights[{w1:.4f}, {w2:.4f}] sum={total:.4f}"
    )
print()
print("Weight statistics:")
print(f"  Min weight: {min(weights):.4f}")
print(f"  Max weight: {max(weights):.4f}")

# Check if all weights sum to ~1.0 per vertex pair
sums = [weights[i] + weights[i + 1] for i in range(0, len(weights), 2)]
print(f"  Sum range: {min(sums):.4f} - {max(sums):.4f}")
print(f"  Avg sum: {sum(sums)/len(sums):.4f}")

# Show weight distribution
non_uniform = sum(1 for i in range(0, len(weights), 2) if abs(weights[i] - 0.5) > 0.1)
print(
    f"  Non-uniform weights (>0.1 diff from 0.5): {non_uniform}/{len(weights)//2} ({100*non_uniform/(len(weights)//2):.1f}%)"
)
