#!/usr/bin/env python3
"""
Validate PVE JSON files against required field paths.
Based on PVE LoadMegaPlantsJsonToCollection validation.
"""

import json
import sys
from pathlib import Path


# Required JSON paths from PVE validation (PVJSONHelper.h)
REQUIRED_PATHS = [
    "points.attributes.pscale",
    "points.positions",
    "points.attributes.lengthFromRoot.values",
    "points.attributes.LOD_totalPscaleGradient.values",
    "points.attributes.budDirection.values",
    "primitives.points",
    "primitives.attributes.instancer_name.values",
    "primitives.attributes.instancer_pivot.values",
    "primitives.attributes.instancer_UP.values",
    "primitives.attributes.instancer_N.values",
    "primitives.attributes.instancer_scale.values",
    "primitives.attributes.instancer_LFR.values",
    "primitives.attributes.parents.values",
    "primitives.attributes.children.values",
    "primitives.attributes.branchNumber.values",
    "globalAttributes.phyllotaxyLeaf.value",
]


def check_json_field_path(data, path):
    """Check if a JSON field path exists."""
    parts = path.split(".")
    current = data

    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return False
            current = current[part]
        else:
            return False

    return True


def validate_json_file(filepath):
    """Validate a JSON file against PVE requirements."""
    print(f"\n{'='*80}")
    print(f"Validating: {filepath}")
    print(f"{'='*80}")

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load JSON: {e}")
        return False

    all_valid = True
    missing_paths = []

    for path in REQUIRED_PATHS:
        if check_json_field_path(data, path):
            print(f"[OK] {path}")
        else:
            print(f"[MISSING] {path}")
            missing_paths.append(path)
            all_valid = False

    # Additional structure checks
    print(f"\n{'-'*80}")
    print("ADDITIONAL CHECKS:")
    print(f"{'-'*80}")

    # Count points
    if "points" in data and "positions" in data["points"]:
        num_points = len(data["points"]["positions"])
        print(f"[OK] Number of points: {num_points}")
    else:
        print("[FAIL] Cannot count points - positions not found")
        all_valid = False

    # Count primitives
    if "primitives" in data and "points" in data["primitives"]:
        num_primitives = len(data["primitives"]["points"])
        print(f"[OK] Number of primitives: {num_primitives}")
    else:
        print("[FAIL] Cannot count primitives - points not found")
        all_valid = False

    # Check for positions structure
    if "points" in data and "positions" in data["points"]:
        positions = data["points"]["positions"]
        if len(positions) > 0:
            first_pos = positions[0]
            print(f"[OK] First position example: {first_pos}")
            if not isinstance(first_pos, list) or len(first_pos) != 3:
                print("  WARNING: Position is not a 3-element array!")
                all_valid = False

    # Check pscale structure
    if "points" in data and "attributes" in data["points"]:
        attrs = data["points"]["attributes"]
        if "pscale" in attrs:
            pscale = attrs["pscale"]
            print(f"[OK] pscale structure: isArray={pscale.get('isArray')}, size={pscale.get('size')}, type={pscale.get('type')}")
            if "values" in pscale and len(pscale["values"]) > 0:
                print(f"  First pscale value: {pscale['values'][0]}")

    # Check budDirection structure
    if "points" in data and "attributes" in data["points"]:
        attrs = data["points"]["attributes"]
        if "budDirection" in attrs:
            bud_dir = attrs["budDirection"]
            print(f"[OK] budDirection structure: isArray={bud_dir.get('isArray')}, size={bud_dir.get('size')}, type={bud_dir.get('type')}")
            if "values" in bud_dir and len(bud_dir["values"]) > 0:
                first_val = bud_dir["values"][0]
                print(f"  First budDirection value: {first_val}")
                if isinstance(first_val, list) and len(first_val) > 0:
                    print(f"  First bud in first point: {first_val[0]}")

    print(f"\n{'='*80}")
    if all_valid:
        print("RESULT: [OK] ALL CHECKS PASSED")
    else:
        print("RESULT: [FAIL] VALIDATION FAILED")
        print(f"\nMissing {len(missing_paths)} required paths:")
        for path in missing_paths:
            print(f"  - {path}")
    print(f"{'='*80}\n")

    return all_valid


def main():
    """Main validation function."""
    reference_file = Path(
        r"C:\Users\Maximilian Sperlich\Git\the-grove\data\tmp\ProceduralVegetationEditor"
        r"\Content\SampleAssets\Tree_Common_Hazel_01\Instances\Broadleaf_Hazel_03.json"
    )

    generated_file = Path(
        r"C:\Users\Maximilian Sperlich\Git\the-grove\data\output\forest\european_beech"
        r"\tree_0013\european_beech_tree_0013.json"
    )

    print("PVE JSON VALIDATION TOOL")
    print("Based on PVJSONHelper.h requirements")

    # Validate reference file
    ref_valid = validate_json_file(reference_file)

    # Validate generated file
    gen_valid = validate_json_file(generated_file)

    # Summary
    print(f"\n{'#'*80}")
    print("VALIDATION SUMMARY")
    print(f"{'#'*80}")
    print(f"Reference (Hazel):  {'PASS' if ref_valid else 'FAIL'}")
    print(f"Generated (Beech):  {'PASS' if gen_valid else 'FAIL'}")
    print(f"{'#'*80}\n")

    return 0 if (ref_valid and gen_valid) else 1


if __name__ == "__main__":
    sys.exit(main())
