# Quick Fix - Corrected Coordinate System (3 Minutes)

## The Real Problem

Your conversion function **swaps axes** when it shouldn't.

- **Grove uses Y-up** (correct for trees)
- **PVE expects Y-up** (also correct for plants)
- **Your code swaps Y↔Z** (creates sideways tree)
- **PVE then swaps Y↔Z again** (double swap = wrong)

---

## Fix #1: Correct the Conversion Function

**File**: `src/growpy/io/pve_foliage_extractor.py`

**Lines 13-26 - Change from:**
```python
def grove_to_pve_position(grove_pos: Tuple[float, float, float]) -> List[float]:
    """
    Convert Grove position to PVE format.

    Grove uses Z-up meters, PVE uses Y-up centimeters.
    """
    x, y, z = grove_pos
    return [x * 100.0, z * 100.0, y * 100.0]  # ❌ Swaps Y and Z
```

**To:**
```python
def grove_to_pve_position(grove_pos: Tuple[float, float, float]) -> List[float]:
    """
    Convert Grove position to PVE format.

    Grove uses Y-up meters.
    PVE expects Y-up centimeters.

    No axis swapping needed - PVE plugin handles Y-up to Z-up conversion internally.
    """
    x, y, z = grove_pos
    return [x * 100.0, y * 100.0, z * 100.0]  # ✓ Scale only, preserve Y-up
```

---

## Fix #2: Correct the Vector Conversion

**File**: `src/growpy/io/pve_foliage_extractor.py`

**Lines 29-40 - Change from:**
```python
def grove_to_pve_vector(grove_vec: Tuple[float, float, float]) -> List[float]:
    """Convert Grove direction vector to PVE format."""
    x, y, z = grove_vec
    return [x, z, y]  # ❌ Swaps Y and Z
```

**To:**
```python
def grove_to_pve_vector(grove_vec: Tuple[float, float, float]) -> List[float]:
    """
    Convert Grove direction vector to PVE format.

    Grove uses Y-up, PVE expects Y-up.
    No axis swapping needed.
    """
    x, y, z = grove_vec
    return [x, y, z]  # ✓ No swap, preserve Y-up
```

---

## Fix #3: Apply Conversion to Skeleton Points

**File**: `src/growpy/io/pve_grove_mapper.py`

**Line 271 - Change from:**
```python
positions = [[p[0], p[1], p[2]] for p in skeleton_points]
```

**To:**
```python
from .pve_foliage_extractor import grove_to_pve_position
positions = [grove_to_pve_position(p) for p in skeleton_points]
```

---

## Optional: Still Need BudDevelopment Fix

If not done yet, also apply:

**File**: `src/growpy/io/pve_schema.py` line 90
```python
# Change from:
"budDevelopment": {"isArray": False, "size": 1, "type": "float"},

# To:
"budDevelopment": {"isArray": True, "size": 6, "type": "int"},
```

And add data extraction in `pve_grove_mapper.py` after line 305 (see earlier documents).

---

## Test

```bash
# Regenerate
python src/growpy/cli/generate_forest.py --species european_beech --output data/output/forest/european_beech/

# Check positions (should have 100x scaling, Y-up preserved)
grep '"positions"' -A 5 data/output/forest/european_beech/european_beech_tree_0000.json | head -10
# Should show: [1400.0, 600.0, 0.0] not [1400.0, 0.0, 600.0]

# In Unreal:
# - Import preset
# - Connect to Generate Mesh
# - Tree should be UPRIGHT
```

---

## Why This Works

```
Grove point: (14.0, 6.0, 0.0)  [Y-up, meters]
   ↓ Correct conversion (scale only)
PVE JSON: [1400.0, 600.0, 0.0]  [Y-up, centimeters]
   ↓ PVE plugin converts internally
Unreal: (1400.0, 0.0, 600.0)  [Z-up, centimeters]
   ↓ Result
Tree grows along Z (UP) ✓
```

vs. What your code was doing:

```
Grove point: (14.0, 6.0, 0.0)  [Y-up, meters]
   ↓ Wrong conversion (scales + swaps)
PVE JSON: [1400.0, 0.0, 600.0]  [Z-up (wrong!), centimeters]
   ↓ PVE plugin converts (swaps again)
Unreal: (1400.0, 600.0, 0.0)  [Y-up in Unreal (wrong!)]
   ↓ Result
Tree grows along Y (SIDEWAYS) ❌
```

---

## Key Insight

You were absolutely right that:
1. Grove uses Y-up
2. The skeleton points weren't being converted
3. There's a mismatch

The issue is the conversion function itself was doing an **unwanted axis swap**.

**Solution**: Just scale, don't swap. PVE plugin handles Y→Z conversion internally.
