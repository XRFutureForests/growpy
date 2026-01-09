"""
Validate PVE JSON files against Unreal Engine requirements.

This module validates that JSON files meet the critical requirements
for importing into Unreal's Procedural Vegetation Editor without crashes.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple


def validate_pve_json(json_path: Path) -> Tuple[bool, List[str]]:
    """
    Validate a PVE JSON file for critical requirements.

    Critical checks based on PVE source code analysis:
    1. All pscale values must not be zero (prevents division by zero)
    2. budDirection must have 6+ vectors (18+ floats) per point
    3. Required JSON paths must exist

    Args:
        json_path: Path to JSON file to validate

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        return False, [f"Failed to load JSON: {e}"]

    # Check required top-level structure
    if "globalAttributes" not in data:
        errors.append("CRITICAL: Missing 'globalAttributes' section")
    if "points" not in data:
        errors.append("CRITICAL: Missing 'points' section")
        return False, errors
    if "primitives" not in data:
        errors.append("CRITICAL: Missing 'primitives' section")

    points = data.get("points", {})
    attributes = points.get("attributes", {})

    # CRITICAL CHECK 1: pscale values must not all be zero
    # Location: PVMeshBuilderElement.cpp line 218-219
    # Code: check(MaxPointScale > 0); float MaxPointScaleRatio = 1.0f / (MaxPointScale * UE_TWO_PI);
    if "pscale" in attributes:
        pscale_attr = attributes["pscale"]
        value_key = "values" if "values" in pscale_attr else "value"
        pscale_values = pscale_attr.get(value_key, [])

        if not pscale_values:
            errors.append("CRITICAL: pscale attribute has no values")
        elif all(v == 0 for v in pscale_values):
            errors.append(
                "CRITICAL: All pscale values are 0 - will cause division by zero crash in PVMeshBuilderElement.cpp line 218-219"
            )
        elif max(pscale_values) == 0:
            errors.append(
                "CRITICAL: Maximum pscale is 0 - will cause division by zero crash"
            )
        else:
            zero_count = sum(1 for v in pscale_values if v == 0)
            if zero_count > 0:
                errors.append(
                    f"WARNING: {zero_count}/{len(pscale_values)} pscale values are 0 - may cause issues"
                )
    else:
        errors.append(
            "CRITICAL: Missing 'pscale' attribute - required for mesh building"
        )

    # CRITICAL CHECK 2: budDirection array sizes
    # Location: PVMeshBuilderElement.cpp line 782, 806
    # Code: PointBudDirections[PointIndex][0] and PointBudDirections[PointIndex][5]
    if "budDirection" in attributes:
        bud_dir_attr = attributes["budDirection"]
        value_key = "values" if "values" in bud_dir_attr else "value"
        bud_directions = bud_dir_attr.get(value_key, [])

        if not bud_directions:
            errors.append("CRITICAL: budDirection attribute has no values")
        else:
            for i, bd in enumerate(bud_directions):
                if not isinstance(bd, list):
                    errors.append(
                        f"CRITICAL: budDirection[{i}] is not an array (type: {type(bd)})"
                    )
                    continue

                # Must have at least 18 floats (6 vectors × 3 components)
                if len(bd) < 18:
                    errors.append(
                        f"CRITICAL: budDirection[{i}] has only {len(bd)} values (need 18+ for 6 vectors) - will cause array out of bounds crash at PVMeshBuilderElement.cpp line 782, 806"
                    )

                # Check if vectors are all zero (not critical but suspicious)
                if all(v == 0 for v in bd):
                    errors.append(
                        f"WARNING: budDirection[{i}] has all zero values - may cause rendering issues"
                    )
    else:
        errors.append(
            "CRITICAL: Missing 'budDirection' attribute - required for mesh building"
        )

    # CHECK 3: Required JSON paths from PVJSONHelper.cpp line 127-143
    required_paths = [
        ("points.positions", points.get("positions")),
        (
            "points.attributes.lengthFromRoot",
            attributes.get("lengthFromRoot"),
        ),
        (
            "points.attributes.LOD_totalPscaleGradient",
            attributes.get("LOD_totalPscaleGradient"),
        ),
        ("primitives.points", data.get("primitives", {}).get("points")),
    ]

    for path, value in required_paths:
        if value is None:
            errors.append(f"WARNING: Missing required path '{path}'")
        elif isinstance(value, (list, dict)):
            # Check for attributes with 'values' or 'value' keys
            if isinstance(value, dict):
                value_key = "values" if "values" in value else "value"
                actual_value = value.get(value_key, [])
                if not actual_value:
                    errors.append(f"WARNING: Path '{path}' has empty values")

    # CHECK 4: Validate positions array
    positions = points.get("positions", [])
    if not positions:
        errors.append("CRITICAL: No point positions defined")
    else:
        num_points = len(positions)
        for i, pos in enumerate(positions):
            if not isinstance(pos, list) or len(pos) != 3:
                errors.append(
                    f"CRITICAL: Position[{i}] is not a 3D vector (got {type(pos)} with {len(pos) if isinstance(pos, list) else 0} elements)"
                )
                break

    # CHECK 5: Validate primitives structure
    primitives = data.get("primitives", {})
    prim_points = primitives.get("points", [])
    if not prim_points:
        errors.append(
            "WARNING: No primitives.points defined - tree may have no branches"
        )

    # Summary
    if not errors:
        num_points = len(positions)
        num_branches = len(prim_points)
        return True, [
            f"VALIDATION PASSED: {num_points} points, {num_branches} branches, all critical checks OK"
        ]
    else:
        return False, errors


def validate_pve_json_from_data(data: Dict) -> Tuple[bool, List[str]]:
    """
    Validate PVE JSON data (already loaded) for critical requirements.

    Same checks as validate_pve_json but works on dict instead of file.

    Args:
        data: Loaded JSON data dictionary

    Returns:
        Tuple of (is_valid, error_messages)
    """
    # Use a temporary file approach for now
    # Could refactor to remove file dependency
    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        temp_path = Path(f.name)

    try:
        return validate_pve_json(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def print_validation_report(json_path: Path) -> bool:
    """
    Print a validation report for a PVE JSON file.

    Args:
        json_path: Path to JSON file

    Returns:
        True if validation passed, False otherwise
    """
    print(f"\nValidating PVE JSON: {json_path.name}")
    print("=" * 80)

    is_valid, messages = validate_pve_json(json_path)

    for msg in messages:
        if msg.startswith("CRITICAL"):
            print(f"  ❌ {msg}")
        elif msg.startswith("WARNING"):
            print(f"  ⚠️  {msg}")
        elif msg.startswith("VALIDATION PASSED"):
            print(f"  ✅ {msg}")
        else:
            print(f"  ℹ️  {msg}")

    print("=" * 80)
    if is_valid:
        print("✅ VALIDATION PASSED - Safe to import into Unreal\n")
    else:
        print("❌ VALIDATION FAILED - Fix errors before importing to Unreal\n")

    return is_valid


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python validate_pve_json.py <path_to_json>")
        sys.exit(1)

    json_file = Path(sys.argv[1])
    if not json_file.exists():
        print(f"Error: File not found: {json_file}")
        sys.exit(1)

    success = print_validation_report(json_file)
    sys.exit(0 if success else 1)
