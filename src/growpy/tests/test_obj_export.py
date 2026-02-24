"""Quick test for OBJ export on existing USDA files."""

from pathlib import Path

# First, inspect the assembly to see its structure
from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema

ensure_pxr_with_unreal_schema()
from pxr import Usd, UsdGeom

assembly_path = Path("data/output/forest/beech/tree_0001/beech_c040_h12m8_d17cm.usda")
print(f"Assembly: {assembly_path}")
stage = Usd.Stage.Open(str(assembly_path))
print("Prims in assembly:")
for prim in stage.Traverse():
    print(f"  {prim.GetPath()} ({prim.GetTypeName()})")

print()
from growpy.io.obj_export import convert_tree_to_obj

print(f"Exists: {assembly_path.exists()}")

result = convert_tree_to_obj(
    assembly_usda_path=assembly_path,
    species_name="European Beech",
    decimate_ratio=0.3,
    helios_spectra_leaves="deciduous",
)
print(f"Result: {result}")

if result and result.exists():
    # Show first few lines of OBJ
    with open(result) as f:
        for i, line in enumerate(f):
            if i >= 15:
                break
            print(line.rstrip())

    # Show MTL
    mtl_path = result.with_suffix(".mtl")
    if mtl_path.exists():
        print(f"\n--- {mtl_path.name} ---")
        print(mtl_path.read_text())
