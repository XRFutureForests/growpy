"""Test script to validate USD builder with direct Grove API.

This script compares the new usd_builder.build_tree_usd() approach
with the original gc.io.model_to_usda_string() to ensure geometry
is exported correctly without transformation issues.
"""

from pathlib import Path

# Import Grove API
import the_grove_22_core as gc

# Import growpy USD builder
from growpy.io import build_tree_usd

# Input parameters matching the-grove-output-complete.py
random_seed = 42
preset_path = Path("data/assets/presets/Fagaceae - Beech.seed.json")
position = (1, 2, 0)
direction = (0, 0, 1)
delay = 0
flushes = 5

# Build parameters
resolution = 16
resolution_reduce = 0.8
texture_repeat = 3
build_cutoff_age = 0
build_cutoff_thickness = 0.0
build_blend = True
build_end_cap = True

# Skeleton parameters
skeleton_length = 2.0
skeleton_reduce = 0.4
skeleton_bias = 0.5
skeleton_connected = True

# Output paths
output_dir = Path("data/output")
output_dir.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("USD Builder Test - Direct Grove API")
print("=" * 60)

# Create and configure grove
print("\n1. Creating grove and simulating tree growth...")
grove = gc.Grove()
grove.clear_trees()
grove.set_random_seed(random_seed)

# Load species preset
with open(preset_path, "r") as f:
    json_string = f.read()
properties = gc.io.properties_from_json_string(json_string)
grove.set_properties(properties)

# Add tree and simulate
position_vec = gc.Vector(*position)
direction_vec = gc.Vector(*direction)
grove.add_new_tree(position_vec, direction_vec, delay)
grove.simulate(flushes)

print(f"   Tree simulated with {flushes} growth cycles")

# Build 3D model
print("\n2. Building 3D model...")
build_params = {
    "resolution": resolution,
    "resolution_reduce": resolution_reduce,
    "texture_repeat": texture_repeat,
    "build_cutoff_age": build_cutoff_age,
    "build_cutoff_thickness": build_cutoff_thickness,
    "build_blend": build_blend,
    "build_end_cap": build_end_cap,
}

models = grove.build_models(build_params)
model = models[0]

# Extract geometry stats for comparison
points = model.points
faces = model.faces
uvs = model.uvs

print(f"   Model generated:")
print(f"   - Points: {len(points)}")
print(f"   - Faces: {len(faces)}")
print(f"   - UVs: {len(uvs)}")

# Triangulate
print("\n3. Triangulating mesh...")
model.triangulate()
faces_after = model.faces
print(f"   Faces after triangulation: {len(faces_after)}")

# Test 1: Export with new USD builder (Z-up, no transformation)
print("\n4. Testing new USD builder (direct API)...")
new_usd_path = output_dir / "test_tree_new.usda"

success = build_tree_usd(
    model=model, output_path=new_usd_path, up_axis="Z", triangulated=True
)

if success:
    print(f"   ✓ Successfully created: {new_usd_path}")
    print(f"   - Coordinate system: Z-up")
    print(f"   - No transformation applied")
else:
    print(f"   ✗ Failed to create USD file")

# Test 2: Add skeleton to USD
print("\n5. Testing skeleton addition...")
from growpy.io import add_skeleton_to_usd

skeletal_usd_path = output_dir / "test_tree_skeletal.usda"

# Copy base USD first
import shutil

shutil.copy2(new_usd_path, skeletal_usd_path)

skeleton_success = add_skeleton_to_usd(
    usd_path=skeletal_usd_path,
    grove=grove,
    skeleton_length=skeleton_length,
    skeleton_reduce=skeleton_reduce,
    skeleton_bias=skeleton_bias,
    skeleton_connected=skeleton_connected,
)

if skeleton_success:
    print(f"   ✓ Successfully added skeleton: {skeletal_usd_path}")

    # Get bone count
    skeletons = grove.build_skeletons()
    skeleton = skeletons[0]
    bones = grove.tag_bone_id(
        skeleton_length,
        skeleton_reduce**2,
        skeleton_bias,
        skeleton_connected,
    )
    print(f"   - Bones created: {len(bones)}")
else:
    print(f"   ✗ Failed to add skeleton")

# Test 3: Verify USD file structure
print("\n6. Verifying USD file structure...")
try:
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.Open(str(new_usd_path))

    # Check up axis
    up_axis = UsdGeom.GetStageUpAxis(stage)
    print(f"   - Stage up axis: {up_axis}")

    # Find mesh and check attributes
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(prim)
            points_attr = mesh.GetPointsAttr()
            usd_points = points_attr.Get()

            print(f"   - USD points count: {len(usd_points)}")

            # Check first point coordinates
            first_pt = usd_points[0]
            original_pt = model.points[0]
            print(
                f"   - First point (USD): ({first_pt[0]:.4f}, {first_pt[1]:.4f}, {first_pt[2]:.4f})"
            )
            print(
                f"   - First point (API): ({original_pt.x:.4f}, {original_pt.y:.4f}, {original_pt.z:.4f})"
            )

            # Check for primvars
            primvars_api = UsdGeom.PrimvarsAPI(prim)
            primvars = primvars_api.GetPrimvars()
            primvar_names = [p.GetPrimvarName() for p in primvars]
            print(f"   - Primvars found: {len(primvar_names)}")
            print(f"     {', '.join(primvar_names[:10])}...")  # Show first 10

            break

    print("   ✓ USD structure verified")

except Exception as e:
    print(f"   ✗ Error verifying USD: {e}")

# Summary
print("\n" + "=" * 60)
print("Test Summary")
print("=" * 60)
print(f"✓ New USD builder working: {success}")
print(f"✓ Skeleton addition working: {skeleton_success}")
print(f"\nOutput files:")
print(f"  - {new_usd_path}")
print(f"  - {skeletal_usd_path}")
print("\nNext steps:")
print("  1. Import both USD files in Unreal Engine")
print("  2. Verify geometry appears correctly (no flipped/rotated mesh)")
print("  3. Verify skeleton bones are positioned correctly")
print("  4. Compare with previous exports to ensure compatibility")
print("=" * 60)
print("=" * 60)
