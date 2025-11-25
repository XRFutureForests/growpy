#!/usr/bin/env python3
"""Check if both JSON files have all required fields for PVE loading."""

import json
import sys

def check_field_path(obj, path):
    """Check if a field path exists in the object."""
    parts = path.split('.')
    current = obj
    
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return False
            current = current[part]
        else:
            return False
    return True

def load_json(path):
    """Load JSON file."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR loading {path}: {e}")
        return None

# Required paths from PVJSONHelper.h lines 409-425
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
    "primitives.attributes.instancer_scale.values",
    "primitives.attributes.instancer_LFR.values",
    "primitives.attributes.parents.values",
    "primitives.attributes.children.values",
    "primitives.attributes.branchNumber.values",
    "globalAttributes.phyllotaxyLeaf.value"
]

beech_path = "data/output/forest/european_beech/european_beech_tree_0000.json"
hazel_path = "data/tmp/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json"

beech = load_json(beech_path)
hazel = load_json(hazel_path)

if not beech or not hazel:
    sys.exit(1)

print("="*70)
print("REQUIRED FIELD VERIFICATION")
print("="*70)

all_pass = True
for path in REQUIRED_PATHS:
    beech_has = check_field_path(beech, path)
    hazel_has = check_field_path(hazel, path)
    
    status = "✓" if beech_has and hazel_has else "✗"
    
    if not beech_has or not hazel_has:
        all_pass = False
    
    print(f"{status} {path:50} | Beech: {beech_has:5} | Hazel: {hazel_has:5}")

print("="*70)
if all_pass:
    print("SUCCESS: All required fields present in both files")
else:
    print("FAILURE: Some required fields are missing")
