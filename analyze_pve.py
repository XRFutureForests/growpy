import json
import os
from collections import Counter

# Working preset: Norway Spruce competition h03m_d03cm
working_path = r"D:\Git\growpy\data\output\forest\norway_spruce\competition\Norway_Spruce_comp_h03m_d03cm_full_stems_unreal_pve.json"

# Non-working preset: Norway Spruce competition h06m_d09cm
nonworking_path = r"D:\Git\growpy\data\output\forest\norway_spruce\competition\Norway_Spruce_comp_h06m_d09cm_full_stems_unreal_pve.json"

# Also check a beech one
beech_path = r"D:\Git\growpy\data\output\forest\european_beech\competition\European_Beech_comp_h03m_d02cm_full_stems_unreal_pve.json"

for label, path in [("WORKING (Spruce h03d03)", working_path), ("NON-WORKING (Spruce h06d09)", nonworking_path), ("NON-WORKING (Beech h03d02)", beech_path)]:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  File: {os.path.basename(path)}")
    print(f"  Size: {os.path.getsize(path)} bytes")
    print(f"{'='*60}")
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    # Points analysis
    positions = data.get("points", {}).get("positions", [])
    print(f"\nPoints count: {len(positions)}")
    if positions:
        # Show first 5 positions
        print(f"First 5 positions: {positions[:5]}")
        # Show position range
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        zs = [p[2] for p in positions]
        print(f"X range: [{min(xs):.4f}, {max(xs):.4f}]")
        print(f"Y range: [{min(ys):.4f}, {max(ys):.4f}]")
        print(f"Z range: [{min(zs):.4f}, {max(zs):.4f}]")
    
    # pscale analysis
    pscale = data.get("points", {}).get("attributes", {}).get("pscale", {})
    pscale_vals = pscale.get("values", pscale.get("value", []))
    if pscale_vals:
        print(f"\npscale count: {len(pscale_vals)}")
        print(f"pscale range: [{min(pscale_vals):.6f}, {max(pscale_vals):.6f}]")
        print(f"pscale first 5: {pscale_vals[:5]}")
        # Check for zeros
        zero_count = sum(1 for v in pscale_vals if v == 0 or v <= 0.001)
        print(f"pscale near-zero count (<=0.001): {zero_count}/{len(pscale_vals)}")
    
    # Primitives analysis
    prim_points = data.get("primitives", {}).get("points", [])
    print(f"\nPrimitives (branches) count: {len(prim_points)}")
    if prim_points:
        # Show sizes of first 5 branches
        sizes = [len(p) for p in prim_points[:10]]
        print(f"First 10 branch point counts: {sizes}")
        # Show first branch indices
        print(f"First branch indices: {prim_points[0][:10] if prim_points[0] else 'empty'}")
        # Check for empty branches
        empty_count = sum(1 for p in prim_points if len(p) == 0)
        single_count = sum(1 for p in prim_points if len(p) == 1)
        print(f"Empty branches: {empty_count}, Single-point branches: {single_count}")
    
    # Key global attributes
    global_attrs = data.get("globalAttributes", {})
    for key in ["cycle", "cycleTime", "randomSeed", "maxBranchNumber", "maxBudNumber", "maxPscale", "max_curve_length"]:
        if key in global_attrs:
            val = global_attrs[key].get("value", "N/A")
            print(f"  {key}: {val}")
    
    # Check branchGeneration and generation attributes
    branch_gen = data.get("primitives", {}).get("attributes", {}).get("branchGeneration", {})
    bg_vals = branch_gen.get("values", branch_gen.get("value", []))
    if bg_vals:
        gen_counts = Counter(bg_vals)
        print(f"\nBranch generation distribution: {dict(sorted(gen_counts.items()))}")
    
    # Check branchParentNumber
    branch_parent = data.get("primitives", {}).get("attributes", {}).get("branchParentNumber", {})
    bp_vals = branch_parent.get("values", branch_parent.get("value", []))
    if bp_vals:
        print(f"Branch parent first 10: {bp_vals[:10]}")
        root_branches = sum(1 for v in bp_vals if v == -1 or v == 0)
        print(f"Root branches (parent=-1 or 0): {root_branches}")
    
    # Check pivotPointLocation
    pivot = data.get("primitives", {}).get("attributes", {}).get("pivotPointLocation", {})
    pivot_vals = pivot.get("values", pivot.get("value", []))
    if pivot_vals:
        print(f"\npivotPointLocation first 3: {pivot_vals[:3]}")
    
    # Check P (position attribute)
    P = data.get("points", {}).get("attributes", {}).get("P", {})
    P_vals = P.get("values", P.get("value", []))
    if P_vals:
        print(f"\nP attribute first 3: {P_vals[:3]}")
    
    # Check budDirection
    bud_dir = data.get("points", {}).get("attributes", {}).get("budDirection", {})
    bd_vals = bud_dir.get("values", bud_dir.get("value", []))
    if bd_vals:
        print(f"\nbudDirection first 2: {bd_vals[:2]}")
        # Check if all zeros
        all_zeroed = all(all(v == 0 for v in bd) for bd in bd_vals[:10])
        print(f"budDirection first 10 all-zero: {all_zeroed}")

print("\n\nDONE")
