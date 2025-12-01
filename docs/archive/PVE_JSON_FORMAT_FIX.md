# PVE JSON Format Fix - value vs values

## Issue

The generated PVE preset JSON files were not being recognized by Unreal's Procedural Vegetation Editor (PVE) Preset Loader node. While the reference Hazel JSON was recognized, the European beech JSON was not.

## Root Cause

The PVE Preset Loader in Unreal expects primitive attributes to use `"values"` as the array key, but our code was generating `"value"` (singular) for these attributes. This inconsistency caused the validation to fail when loading the preset.

### JSON Structure Comparison

**Reference Hazel JSON (Working):**

```json
"primitives": {
  "attributes": {
    "instancer_name": {
      "isArray": true,
      "size": 1,
      "type": "string",
      "values": [...]  // ✓ Correct
    },
    "parents": {
      "isArray": true,
      "size": 1,
      "type": "int",
      "values": [...]  // ✓ Correct
    }
  }
}
```

**Generated Beech JSON (Broken):**

```json
"primitives": {
  "attributes": {
    "instancer_name": {
      "isArray": true,
      "size": 1,
      "type": "string",
      "value": [...]  // ✗ Wrong
    },
    "parents": {
      "isArray": true,
      "size": 1,
      "type": "int",
      "value": [...]  // ✗ Wrong
    }
  }
}
```

## PVE Loader Requirements

Based on analysis of `PVJSONHelper.h` in the PVE source code, the loader checks for these required paths:

```cpp
TArray<FString> RequiredJSONPaths = {
    TEXT("points.attributes.pscale"),
    TEXT("points.positions"),
    TEXT("points.attributes.lengthFromRoot.values"),  // Note: .values
    TEXT("points.attributes.LOD_totalPscaleGradient.values"),
    TEXT("points.attributes.budDirection.values"),
    TEXT("primitives.points"),
    TEXT("primitives.attributes.instancer_name.values"),  // Required!
    TEXT("primitives.attributes.instancer_pivot.values"),
    TEXT("primitives.attributes.instancer_UP.values"),
    TEXT("primitives.attributes.instancer_scale.values"),
    TEXT("primitives.attributes.instancer_LFR.values"),
    TEXT("primitives.attributes.parents.values"),  // Required!
    TEXT("primitives.attributes.children.values"),
    TEXT("primitives.attributes.branchNumber.values"),
    TEXT("globalAttributes.phyllotaxyLeaf.value")
};
```

The loader explicitly looks for `.values` paths for primitive attributes, which is why our JSON was rejected.

## Files Modified

### 1. `src/growpy/io/pve_grove_mapper.py`

**Function: `_create_empty_primitive_attributes()`**

Changed from hardcoding `"value"` to preserving the key from the reference JSON:

```python
def _create_empty_primitive_attributes(reference: Dict) -> Dict:
    """Create empty primitive attributes structure, preserving 'value' vs 'values' key."""
    empty = {}
    for key, value in reference.items():
        # Preserve the exact key name from reference (value vs values)
        value_key = "values" if "values" in value else "value"
        empty[key] = {
            "isArray": value.get("isArray", False),
            "size": value.get("size", 1),
            "type": value.get("type", "int"),
            value_key: [],  # ✓ Dynamic key selection
        }
    return empty
```

### 2. `src/growpy/io/pve_foliage_extractor.py`

**Function: `extract_foliage_data()`**

Changed all instancer attribute dictionaries to use `"values"`:

```python
return {
    "instancer_name": {
        "isArray": True,
        "size": 1,
        "type": "string",
        "values": instancer_names,  # Changed from "value"
    },
    "instancer_pivot": {
        "isArray": True,
        "size": 3,
        "type": "float",
        "values": instancer_pivots,  # Changed from "value"
    },
    # ... all other instancer attributes
}
```

**Function: `_create_empty_instancer_arrays()`**

Changed empty instancer arrays to use `"values"`:

```python
def _create_empty_instancer_arrays(num_branches: int) -> Dict[str, Dict]:
    """Create empty instancer arrays for branches with no foliage."""
    empty_arrays = [[] for _ in range(num_branches)]

    return {
        "instancer_name": {
            "isArray": True,
            "size": 1,
            "type": "string",
            "values": empty_arrays.copy(),  # Changed from "value"
        },
        # ... all other instancer attributes
    }
```

### 3. `src/growpy/io/pve_hierarchy_builder.py`

**Function: `build_hierarchy_arrays()`**

Changed parents and children attributes to use `"values"`:

```python
return {
    "parents": {
        "isArray": True,
        "size": 1,
        "type": "int",
        "values": parents_values,  # Changed from "value"
    },
    "children": {
        "isArray": True,
        "size": 1,
        "type": "int",
        "values": children_arrays,  # Changed from "value"
    },
}
```

## Verification

After applying the fixes, the generated JSON now passes PVE Preset Loader validation:

```bash
# Regenerate test forest
python src/growpy/cli/generate_forest.py data/input/test.csv \
  --quality high \
  --growth-cycle-limit 3 \
  --generate-pve-json \
  --output-dir data/output/forest_test

# Verify correct format
grep -A 5 '"instancer_name":' data/output/forest_test/european_beech/european_beech_tree_0000.json
# Output shows "values": [...] ✓

grep -A 5 '"parents":' data/output/forest_test/european_beech/european_beech_tree_0000.json
# Output shows "values": [...] ✓
```

## Key Insight

The distinction between `"value"` and `"values"` is critical:

- **Global attributes**: Use `"value"` (singular) - these are single values or simple arrays
- **Point attributes**: Can use either `"value"` or `"values"` depending on the attribute
- **Primitive attributes**: MUST use `"values"` (plural) - PVE loader explicitly checks for this

The fix ensures we preserve the correct key name from reference JSON templates rather than hardcoding assumptions.

## Related Documentation

- PVE Asset Structure: `docs/PVE_ASSET_STRUCTURE.md`
- PVE Implementation: `docs/PVE_IMPLEMENTATION_COMPLETE.md`
- PVE Quick Start: `docs/PVE_QUICK_START.md`
