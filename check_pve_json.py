import json
import sys
from pathlib import Path

# Check beech JSON structure - use command line arg if provided
if len(sys.argv) > 1:
    beech_json = Path(sys.argv[1])
else:
    beech_json = Path("data/output/forest/european_beech/european_beech_tree_0000.json")

print(f"Validating: {beech_json}")
with open(beech_json) as f:
    data = json.load(f)

required_paths = [
    "points.attributes.pscale",
    "points.positions",
    "points.attributes.lengthFromRoot",
    "points.attributes.LOD_totalPscaleGradient",
    "points.attributes.budDirection",
    "primitives.points",
    "primitives.attributes.instancer_name",
    "primitives.attributes.instancer_pivot",
    "primitives.attributes.instancer_UP",
    "primitives.attributes.instancer_scale",
    "primitives.attributes.instancer_LFR",
    "primitives.attributes.parents",
    "primitives.attributes.children",
    "primitives.attributes.branchNumber",
    "globalAttributes.phyllotaxyLeaf",
]

print("\nChecking required JSON paths:")
for path in required_paths:
    parts = path.split(".")
    current = data
    found = True
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            found = False
            break

    status = "✓ FOUND" if found else "✗ MISSING"
    # Check if it has data (for arrays/lists)
    if found and isinstance(current, dict):
        if "value" in current or "values" in current:
            value_key = "values" if "values" in current else "value"
            has_data = bool(current[value_key])
            status += f" ({'with data' if has_data else 'EMPTY'})"
    print(f"  {path}: {status}")

print(f"\nGlobalAttributes count: {len(data.get('globalAttributes', {}))}")
print(
    f"PlantProfiles populated: {bool(data.get('globalAttributes', {}).get('plantProfile_1', {}).get('value', []))}"
)
