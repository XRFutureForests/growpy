"""Create a minimal Y-shaped tree from Epic's Hazel file.

Takes the original Broadleaf_Hazel_04.json and reduces it to:
- 3 branches (trunk + 2 side branches)
- ~3-4 points per branch (9-12 total points)
- Preserves all attribute formats from the original
"""

import json
from pathlib import Path


def get_values(attr_data):
    """Get values from attribute (Epic uses 'values' plural)."""
    return attr_data.get("values", attr_data.get("value", []))


def reduce_to_y_shape(input_path: Path, output_path: Path):
    """Reduce Hazel tree to minimal Y-shape."""
    with open(input_path) as f:
        data = json.load(f)

    orig_positions = data["points"]["positions"]
    orig_point_attrs = data["points"]["attributes"]
    orig_prims = data["primitives"]
    orig_branch_pts = orig_prims["points"]
    orig_branch_attrs = orig_prims["attributes"]

    print(f"Original: {len(orig_positions)} points, {len(orig_branch_pts)} branches")

    # For a proper Y-shape, we need:
    # - Trunk points from base up to where branches connect (~y=0.7-0.8)
    # - A few points from each side branch
    # Find trunk points that reach the branch heights

    # Sample trunk: every 30th point to get ~5-6 points spanning the height
    trunk_samples = [0, 30, 60, 90, 120, 140, 160, 170]
    trunk_sample_pts = [
        orig_branch_pts[0][i] for i in trunk_samples if i < len(orig_branch_pts[0])
    ]

    # Take first 3 points from each side branch
    branch1_pts = orig_branch_pts[1][:3]
    branch2_pts = orig_branch_pts[2][:3]

    branch_selections = [
        trunk_sample_pts,
        branch1_pts,
        branch2_pts,
    ]

    # Build new point list and mapping
    new_positions = []
    old_to_new = {}
    new_branch_points = []

    for old_pts in branch_selections:
        new_pts = []
        for old_idx in old_pts:
            if old_idx not in old_to_new:
                old_to_new[old_idx] = len(new_positions)
                new_positions.append(orig_positions[old_idx])
            new_pts.append(old_to_new[old_idx])
        new_branch_points.append(new_pts)

    print(f"New: {len(new_positions)} points, {len(new_branch_points)} branches")
    print(f"Branch point indices: {new_branch_points}")

    old_indices = sorted(old_to_new.keys())
    num_new_points = len(new_positions)

    # Extract point attributes for selected points
    new_point_attrs = {}
    for attr_name, attr_data in orig_point_attrs.items():
        new_attr = {
            "type": attr_data["type"],
            "size": attr_data["size"],
            "isArray": attr_data.get("isArray", False),
        }

        orig_values = get_values(attr_data)
        if len(orig_values) == 0:
            new_attr["values"] = []
        else:
            # Check if values are nested arrays (like budDirection)
            if orig_values and isinstance(orig_values[0], list):
                # Nested arrays: one array per point, pick selected points
                new_attr["values"] = [orig_values[old_idx] for old_idx in old_indices]
            else:
                # Flat array: size values per point
                size = attr_data["size"]
                values_per_point = size
                new_values = []

                for old_idx in old_indices:
                    start = old_idx * values_per_point
                    end = start + values_per_point
                    if end <= len(orig_values):
                        new_values.extend(orig_values[start:end])
                    else:
                        new_values.extend([0.0] * values_per_point)

                new_attr["values"] = new_values

        new_point_attrs[attr_name] = new_attr

    # Extract branch attributes for 3 branches
    # We need to renumber branches to sequential 1, 2, 3
    # Original branchNumbers: [1, 5, 4] -> New: [1, 2, 3]
    orig_branch_numbers = get_values(orig_branch_attrs["branchNumber"])
    old_to_new_branch = {}
    for new_idx, old_num in enumerate(orig_branch_numbers[:3]):
        old_to_new_branch[old_num] = new_idx + 1  # 1-based branchNumber
    print(f"Branch number mapping: {old_to_new_branch}")

    new_branch_attrs = {}
    for attr_name, attr_data in orig_branch_attrs.items():
        new_attr = {
            "type": attr_data["type"],
            "size": attr_data["size"],
            "isArray": attr_data.get("isArray", False),
        }

        orig_values = get_values(attr_data)
        if len(orig_values) == 0:
            new_attr["values"] = []
        elif attr_name == "branchNumber":
            # Renumber to sequential 1, 2, 3
            new_attr["values"] = [1, 2, 3]
        elif attr_name == "branchParentNumber":
            # Map old parent numbers to new, keeping 0 as 0
            new_vals = []
            for i in range(3):
                old_parent = orig_values[i]
                if old_parent == 0:
                    new_vals.append(0)
                else:
                    new_vals.append(old_to_new_branch.get(old_parent, 0))
            new_attr["values"] = new_vals
        elif attr_name == "children":
            # Remap children to new branchNumbers
            new_values = []
            for i in range(3):
                if i < len(orig_values):
                    remapped = [
                        old_to_new_branch[v]
                        for v in orig_values[i]
                        if v in old_to_new_branch
                    ]
                    new_values.append(remapped)
                else:
                    new_values.append([])
            new_attr["values"] = new_values
        elif attr_name == "parents":
            # Remap parents to new branchNumbers
            new_values = []
            for i in range(3):
                if i < len(orig_values):
                    remapped = [
                        old_to_new_branch.get(v, 0)
                        for v in orig_values[i]
                        if v in old_to_new_branch or v == 0
                    ]
                    # Filter out zeros that weren't originally 0
                    new_values.append(remapped)
                else:
                    new_values.append([])
            new_attr["values"] = new_values
        else:
            size = attr_data["size"]
            values_per_branch = size
            new_attr["values"] = orig_values[: 3 * values_per_branch]

        new_branch_attrs[attr_name] = new_attr

    output = {
        "globalAttributes": data["globalAttributes"],
        "points": {
            "attributes": new_point_attrs,
            "positions": new_positions,
        },
        "primitives": {
            "attributes": new_branch_attrs,
            "points": new_branch_points,
        },
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Written to: {output_path}")

    # Verify
    print("\nVerification:")
    print(f"  Positions: {len(output['points']['positions'])}")
    for attr, data in list(output["points"]["attributes"].items())[:5]:
        vals = data.get("values", [])
        print(f"  Point attr {attr}: {len(vals)} values, size={data['size']}")
    print(f"  Branches: {len(output['primitives']['points'])}")
    for attr, data in list(output["primitives"]["attributes"].items())[:5]:
        vals = data.get("values", [])
        print(f"  Branch attr {attr}: {len(vals)} values")


if __name__ == "__main__":
    input_path = Path(
        "data/tmp/ProceduralVegetationEditor/Content/SampleAssets/"
        "Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json"
    )
    output_path = Path("data/output/pve_test/hazel_y_shape.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    reduce_to_y_shape(input_path, output_path)
