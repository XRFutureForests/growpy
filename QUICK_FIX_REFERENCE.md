# Quick Fix Reference - BudDevelopment Crash

## TL;DR

**Error**: `Assertion failed: BudDevelopment.Num() > 2 [PVMaterialSettings.cpp:71]`

**Cause**: budDevelopment JSON arrays have 1 element, need 6+

**Solution**:
1. Fix schema: `size: 1` → `size: 6`, `isArray: False` → `True`, `type: "float"` → `type: "int"`
2. Extract data: Add budDevelopment mapping in pve_grove_mapper.py

---

## Quick Fix - 3 Minutes

### 1. Fix Schema (30 seconds)

**File**: `src/growpy/io/pve_schema.py`

**Line 90 - Change from:**
```python
"budDevelopment": {"isArray": False, "size": 1, "type": "float"},
```

**To:**
```python
"budDevelopment": {"isArray": True, "size": 6, "type": "int"},
```

### 2. Add Data Extraction (2 minutes)

**File**: `src/growpy/io/pve_grove_mapper.py`

**Function**: `_map_points_from_skeleton()`

**After line 360** (after plantGradient mapping), add:

```python
elif attr_name == "budDevelopment":
    bud_dev_list = []
    for point_idx in range(num_points):
        gen = points_data["attributes"].get("generation", {}).get("values", [0] * num_points)[point_idx]
        age = points_data["attributes"].get("generation", {}).get("values", [0] * num_points)[point_idx]
        bud_dev_list.append([int(gen), int(age), int(age), 50, 50, 16])
    points_data["attributes"][attr_name]["values"] = bud_dev_list
```

### 3. Regenerate & Test (30 seconds)

```bash
python src/growpy/cli/generate_forest.py --species european_beech --output data/output/forest/european_beech/
```

Verify JSON:
```bash
grep '"budDevelopment"' -A 10 data/output/forest/european_beech/european_beech_tree_0000.json
```

Should show `[number, number, number, number, number, number]` arrays ✓

---

## What Gets Fixed

### BEFORE (Crashes):
```json
"budDevelopment": {
  "values": [
    [0],        // ❌ WRONG
    [0],
    ...
  ]
}
```

### AFTER (Works):
```json
"budDevelopment": {
  "values": [
    [0, 0, 0, 50, 50, 16],     // ✓ CORRECT
    [1, 5, 5, 75, 60, 16],
    [2, 10, 10, 90, 70, 16],
    ...
  ]
}
```

---

## Why It Works

The PVE material system accesses:
- `BudDevelopment[0]` - Generation (branch depth)
- `BudDevelopment[2]` - Age (material selection)

Both need to be present. The array must have at least 3 elements (indices 0, 1, 2).

---

## Validation

After making changes:

1. **Schema check**: grep shows 6 in schema ✓
2. **JSON check**: Each budDevelopment has 6 numbers ✓
3. **Import test**: Preset imports without error ✓
4. **Mesh test**: Generate Mesh doesn't crash ✓

---

## Common Issues

| Issue | Solution |
|-------|----------|
| "isArray must be boolean" | Make sure it's `True` not `"True"` |
| Still has 1 element | Make sure elif is in right place in function |
| Assertion still fails | Check generation values exist in points_data |
| Import fails | Validate JSON syntax (use jq or Python json.tool) |

---

## Files to Edit

1. `src/growpy/io/pve_schema.py` (line 90)
2. `src/growpy/io/pve_grove_mapper.py` (after line 360)

That's it! 2 files, ~5 lines of changes total.

---

## Detailed Docs

For complete explanation, see:
- [BUDDEVELOPMENT_FIX_GUIDE.md](BUDDEVELOPMENT_FIX_GUIDE.md) - Full implementation guide
- [PVE_CRASH_ANALYSIS_SUMMARY.md](PVE_CRASH_ANALYSIS_SUMMARY.md) - Complete analysis
- [BUDDEVELOPMENT_ROOT_CAUSE.md](BUDDEVELOPMENT_ROOT_CAUSE.md) - Deep dive analysis
