# JSON File Format Issue - Crash Analysis

## Problem Summary
**The beech JSON file uses `"value"` instead of `"values"` for array data in primitives attributes.** This causes a crash when the PVE plugin tries to parse the foliage data.

## Root Cause

The JSON parser in [PVJSONHelper.h](data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/Public/Helpers/PVJSONHelper.h) has a critical assumption:

- **Primitives attributes** (instancer_name, instancer_pivot, instancer_scale, instancer_LFR, etc.) MUST use **`"values"`** key
- **Global attributes** (phyllotaxyLeaf, etc.) use **`"value"`** key

When `FillFoliageData()` (line 237) executes, it directly accesses:
- Line 240: `InstancerNameObject->GetArrayField(TEXT("values"))`
- Line 243: `InstancerPivotObject->GetArrayField(TEXT("values"))`
- Lines 252, 255: Same pattern for scale and LFR

If the key is `"value"` instead of `"values"`, the `GetArrayField()` call **fails** and causes a crash.

## Format Comparison

### Beech JSON (WRONG - Will Crash)
```json
"primitives": {
  "attributes": {
    "instancer_name": {
      "isArray": true,
      "size": 1,
      "type": "string",
      "value": [[], [], ...]  // ❌ WRONG: Uses "value" not "values"
    }
  }
}
```

### Hazel JSON (CORRECT)
```json
"primitives": {
  "attributes": {
    "instancer_name": {
      "isArray": true,
      "size": 1,
      "type": "string",
      "values": [
        ["BrLeaf_020", "BrLeaf_010", ...],
        ["BrLeaf_009", "BrLeaf_010", ...],
        ...
      ]  // ✓ CORRECT: Uses "values"
    }
  }
}
```

## Which Attributes Are Affected

All primitives attributes that should use `"values"`:
- `instancer_name`
- `instancer_pivot`
- `instancer_UP`
- `instancer_N` (normal vectors)
- `instancer_scale`
- `instancer_LFR` (length from root)

These are parsed in `FillFoliageData()` lines 239-255.

## Required Fix

In the beech JSON, **rename all `"value"` keys to `"values"`** for these primitives attributes:
1. `primitives.attributes.instancer_name.value` → `primitives.attributes.instancer_name.values`
2. `primitives.attributes.instancer_pivot.value` → `primitives.attributes.instancer_pivot.values`
3. `primitives.attributes.instancer_UP.value` → `primitives.attributes.instancer_UP.values`
4. `primitives.attributes.instancer_N.value` → `primitives.attributes.instancer_N.values`
5. `primitives.attributes.instancer_scale.value` → `primitives.attributes.instancer_scale.values`
6. `primitives.attributes.instancer_LFR.value` → `primitives.attributes.instancer_LFR.values`

**Global attributes should keep `"value"`** - they are parsed by `FillDetailsAttributes()` which expects `"value"` not `"values"`.
