#!/usr/bin/env python3
"""
Compare PVE JSON structure between reference and generated files.
Focus on identifying critical differences that might cause crashes or distortion.
"""

import json
from pathlib import Path


def analyze_attribute_data(data, attr_name, path):
    """Analyze a specific attribute's data structure and content."""
    print(f"\nAttribute: {attr_name}")
    print(f"-" * 60)

    if attr_name not in data:
        print(f"  [MISSING] Attribute not found")
        return

    attr = data[attr_name]
    print(f"  Type: {attr.get('type')}")
    print(f"  isArray: {attr.get('isArray')}")
    print(f"  Size: {attr.get('size')}")

    # Determine value key
    value_key = "values" if "values" in attr else "value"
    values = attr.get(value_key, [])

    if isinstance(values, list):
        print(f"  Num entries: {len(values)}")

        if len(values) > 0:
            first = values[0]
            print(f"  First entry type: {type(first)}")
            print(f"  First entry: {first}")

            # Check if all zeros
            if isinstance(first, list):
                all_zeros = all(v == 0 or v == 0.0 for v in first)
                print(f"  First entry all zeros: {all_zeros}")

                # Sample a few more entries
                for i in [1, 2, len(values) - 1]:
                    if i < len(values):
                        entry = values[i]
                        if isinstance(entry, list):
                            is_zero = all(v == 0 or v == 0.0 for v in entry)
                            print(f"  Entry [{i}] all zeros: {is_zero}, sample: {entry[:6] if len(entry) > 6 else entry}")

            # Count non-zero entries
            if isinstance(values[0], list):
                non_zero_count = sum(
                    1
                    for entry in values
                    if not all(v == 0 or v == 0.0 for v in entry)
                )
                print(f"  Non-zero entries: {non_zero_count} / {len(values)}")
    else:
        print(f"  Value: {values}")


def compare_json_files(ref_path, gen_path):
    """Compare reference and generated JSON files."""
    print(f"{'#' * 80}")
    print(f"COMPARING JSON STRUCTURE")
    print(f"{'#' * 80}")

    # Load files
    print(f"\nLoading reference: {ref_path.name}")
    with open(ref_path, "r") as f:
        ref_data = json.load(f)

    print(f"Loading generated: {gen_path.name}")
    with open(gen_path, "r") as f:
        gen_data = json.load(f)

    # Critical attributes to compare
    critical_point_attrs = [
        "budDirection",
        "budNumber",
        "budStatus",
        "budDevelopment",
        "budHormoneLevels",
        "pscale",
        "lengthFromRoot",
        "LOD_totalPscaleGradient",
    ]

    critical_prim_attrs = [
        "parents",
        "children",
        "branchNumber",
        "instancer_name",
        "instancer_pivot",
        "instancer_UP",
        "instancer_N",
        "instancer_scale",
    ]

    # Compare points attributes
    print(f"\n{'=' * 80}")
    print("REFERENCE (HAZEL) - POINTS ATTRIBUTES")
    print(f"{'=' * 80}")

    ref_point_attrs = ref_data["points"]["attributes"]
    for attr_name in critical_point_attrs:
        analyze_attribute_data(ref_point_attrs, attr_name, ref_path)

    print(f"\n{'=' * 80}")
    print("GENERATED (BEECH) - POINTS ATTRIBUTES")
    print(f"{'=' * 80}")

    gen_point_attrs = gen_data["points"]["attributes"]
    for attr_name in critical_point_attrs:
        analyze_attribute_data(gen_point_attrs, attr_name, gen_path)

    # Compare primitives attributes
    print(f"\n{'=' * 80}")
    print("REFERENCE (HAZEL) - PRIMITIVE ATTRIBUTES")
    print(f"{'=' * 80}")

    ref_prim_attrs = ref_data["primitives"]["attributes"]
    for attr_name in critical_prim_attrs:
        analyze_attribute_data(ref_prim_attrs, attr_name, ref_path)

    print(f"\n{'=' * 80}")
    print("GENERATED (BEECH) - PRIMITIVE ATTRIBUTES")
    print(f"{'=' * 80}")

    gen_prim_attrs = gen_data["primitives"]["attributes"]
    for attr_name in critical_prim_attrs:
        analyze_attribute_data(gen_prim_attrs, attr_name, gen_path)

    # Summary statistics
    print(f"\n{'#' * 80}")
    print("SUMMARY COMPARISON")
    print(f"{'#' * 80}")

    ref_num_points = len(ref_data["points"]["positions"])
    gen_num_points = len(gen_data["points"]["positions"])
    ref_num_prims = len(ref_data["primitives"]["points"])
    gen_num_prims = len(gen_data["primitives"]["points"])

    print(f"Points:      Reference={ref_num_points:6d}  Generated={gen_num_points:6d}")
    print(f"Primitives:  Reference={ref_num_prims:6d}  Generated={gen_num_prims:6d}")

    # Check for critical issues
    issues = []

    # Check budDirection
    ref_bud_dir = ref_point_attrs.get("budDirection", {})
    gen_bud_dir = gen_point_attrs.get("budDirection", {})

    value_key = "values" if "values" in gen_bud_dir else "value"
    gen_bud_values = gen_bud_dir.get(value_key, [])

    if len(gen_bud_values) > 0 and isinstance(gen_bud_values[0], list):
        non_zero_buds = sum(
            1 for entry in gen_bud_values if not all(v == 0 or v == 0.0 for v in entry)
        )
        if non_zero_buds == 0:
            issues.append("CRITICAL: All budDirection values are zero - SLOPE NODE WILL FAIL")

    # Check budNumber
    gen_bud_num = gen_point_attrs.get("budNumber", {})
    value_key = "values" if "values" in gen_bud_num else "value"
    gen_bud_num_values = gen_bud_num.get(value_key, [])

    if len(gen_bud_num_values) > 0:
        non_zero_bud_nums = sum(1 for v in gen_bud_num_values if v != 0 and v != 0.0)
        if non_zero_bud_nums == 0:
            issues.append("WARNING: All budNumber values are zero - may cause issues")

    # Check instancer data
    gen_inst_name = gen_prim_attrs.get("instancer_name", {})
    value_key = "values" if "values" in gen_inst_name else "value"
    gen_inst_names = gen_inst_name.get(value_key, [])

    if not gen_inst_names or (isinstance(gen_inst_names, list) and len(gen_inst_names) == 0):
        issues.append("INFO: No foliage instancer names - no leaves will be generated")

    print(f"\n{'=' * 80}")
    print("IDENTIFIED ISSUES")
    print(f"{'=' * 80}")

    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  No critical issues identified")

    print(f"{'#' * 80}\n")


def main():
    """Main comparison function."""
    reference_file = Path(
        r"C:\Users\Maximilian Sperlich\Git\the-grove\data\tmp\ProceduralVegetationEditor"
        r"\Content\SampleAssets\Tree_Common_Hazel_01\Instances\Broadleaf_Hazel_03.json"
    )

    generated_file = Path(
        r"C:\Users\Maximilian Sperlich\Git\the-grove\data\output\test_fix\european_beech"
        r"\tree_0000\european_beech_tree_0000.json"
    )

    compare_json_files(reference_file, generated_file)


if __name__ == "__main__":
    main()
