#!/usr/bin/env python3
"""Verify BranchIndex primvar is correctly populated in generated USD tree."""
from pxr import Usd, UsdGeom

stage = Usd.Stage.Open("data/output/test_assembly/western_redcedar_tree.usda")
mesh = UsdGeom.Mesh.Get(stage, "/TreeMesh")
primvars = mesh.GetPrimvars()

print("=== Primvars on TreeMesh ===")
for pv in primvars:
    if "Branch" in pv.GetName():
        print(f"\n{pv.GetName()}:")
        print(f"  Type: {pv.GetTypeName()}")
        print(f"  Interpolation: {pv.GetInterpolation()}")

        vals = pv.Get()
        if vals:
            print(f"  Total values: {len(vals)}")
            print(f"  Sample values (first 10): {list(vals[:10])}")

            if pv.GetName() == "primvars:BranchIndex":
                unique_ids = sorted(set(vals))
                print(f"  Unique branch IDs: {unique_ids}")
                print(f"  Total unique branches: {len(unique_ids)}")

                # Verify no zeros (0 indicates unmapped faces)
                if 0 in unique_ids:
                    print("  [WARN] Found unmapped faces (branch ID = 0)")
                else:
                    print("  [OK] All faces mapped to branches")
