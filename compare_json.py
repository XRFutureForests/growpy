#!/usr/bin/env python3
"""Compare two PVE JSON files to find structural and content differences."""

import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

def load_json(path: str) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, 'r') as f:
        return json.load(f)

def get_keys_recursive(obj: Any, prefix: str = "") -> Set[str]:
    """Get all keys in nested structure."""
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            keys.add(full_key)
            keys.update(get_keys_recursive(v, full_key))
    elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
        for item in obj:
            keys.update(get_keys_recursive(item, prefix))
    return keys

def compare_structures(beech: Dict, hazel: Dict) -> Tuple[Set, Set, Set]:
    """Compare top-level structure."""
    beech_keys = set(beech.keys())
    hazel_keys = set(hazel.keys())

    missing_in_beech = hazel_keys - beech_keys
    missing_in_hazel = beech_keys - hazel_keys
    common = beech_keys & hazel_keys

    return missing_in_beech, missing_in_hazel, common

def check_array_lengths(beech: Dict, hazel: Dict, common_keys: Set) -> Dict[str, Tuple[int, int]]:
    """Compare array/list lengths for common keys."""
    differences = {}
    for key in common_keys:
        b_val = beech.get(key)
        h_val = hazel.get(key)
        if isinstance(b_val, list) and isinstance(h_val, list):
            if len(b_val) != len(h_val):
                differences[key] = (len(b_val), len(h_val))
    return differences

def sample_nested_keys(obj: Dict, max_depth: int = 3) -> Dict[str, Any]:
    """Sample nested structure at each level."""
    result = {}
    for k, v in obj.items():
        if isinstance(v, dict):
            result[f"{k} (dict)"] = list(v.keys())[:5]
        elif isinstance(v, list) and v:
            if isinstance(v[0], dict):
                result[f"{k} (list[dict])"] = {
                    "length": len(v),
                    "first_item_keys": list(v[0].keys())[:10]
                }
            else:
                result[f"{k} (list)"] = {
                    "length": len(v),
                    "sample_types": list(set(type(x).__name__ for x in v[:10]))
                }
        else:
            result[f"{k}"] = type(v).__name__
    return result

def main():
    beech_path = "data/output/forest/european_beech/european_beech_tree_0000.json"
    hazel_path = "data/tmp/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json"

    print("Loading JSON files...")
    beech = load_json(beech_path)
    hazel = load_json(hazel_path)

    print(f"\nBeech file size: {len(str(beech))} chars")
    print(f"Hazel file size: {len(str(hazel))} chars")

    # Compare top-level structure
    missing_in_beech, missing_in_hazel, common = compare_structures(beech, hazel)

    print("\n" + "="*60)
    print("TOP-LEVEL STRUCTURE COMPARISON")
    print("="*60)

    print(f"\nTotal keys - Beech: {len(beech)}, Hazel: {len(hazel)}")

    if missing_in_beech:
        print(f"\nMISSING IN BEECH (in Hazel but not Beech):")
        for key in sorted(missing_in_beech):
            val = hazel[key]
            val_type = type(val).__name__
            if isinstance(val, list):
                print(f"  - {key} (list, {len(val)} items)")
            elif isinstance(val, dict):
                print(f"  - {key} (dict, {len(val)} keys)")
            else:
                print(f"  - {key} ({val_type}): {str(val)[:80]}")

    if missing_in_hazel:
        print(f"\nEXTRA IN BEECH (in Beech but not Hazel):")
        for key in sorted(missing_in_hazel):
            val = beech[key]
            val_type = type(val).__name__
            if isinstance(val, list):
                print(f"  - {key} (list, {len(val)} items)")
            elif isinstance(val, dict):
                print(f"  - {key} (dict, {len(val)} keys)")
            else:
                print(f"  - {key} ({val_type}): {str(val)[:80]}")

    # Check array lengths
    array_diffs = check_array_lengths(beech, hazel, common)
    if array_diffs:
        print(f"\nARRAY LENGTH DIFFERENCES (common keys with different lengths):")
        for key, (b_len, h_len) in sorted(array_diffs.items()):
            print(f"  - {key}: Beech={b_len}, Hazel={h_len}")

    # Sample structure
    print("\n" + "="*60)
    print("BEECH FILE STRUCTURE (top-level)")
    print("="*60)
    beech_struct = sample_nested_keys(beech)
    for k, v in sorted(beech_struct.items()):
        print(f"  {k}: {v}")

    print("\n" + "="*60)
    print("HAZEL FILE STRUCTURE (top-level)")
    print("="*60)
    hazel_struct = sample_nested_keys(hazel)
    for k, v in sorted(hazel_struct.items()):
        print(f"  {k}: {v}")

    # Check specific critical fields
    print("\n" + "="*60)
    print("CRITICAL FIELD CHECKS")
    print("="*60)

    critical_fields = ["transform", "materials", "variants", "instances", "properties"]
    for field in critical_fields:
        if field in common:
            b_val = beech.get(field)
            h_val = hazel.get(field)
            if isinstance(b_val, dict) and isinstance(h_val, dict):
                b_keys = set(b_val.keys())
                h_keys = set(h_val.keys())
                if b_keys != h_keys:
                    print(f"\n{field} - subkey differences:")
                    if b_keys - h_keys:
                        print(f"  Extra in Beech: {b_keys - h_keys}")
                    if h_keys - b_keys:
                        print(f"  Missing in Beech: {h_keys - b_keys}")

if __name__ == "__main__":
    main()
