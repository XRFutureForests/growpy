# Coordinate System Analysis - CORRECTED

## Your Intuition Was Right!

After analyzing the actual PVE plugin source code, I can confirm:

**You were correct**: Grove uses Y-up (standard for plants), and the PVE plugin expects Y-up from JSON, then converts it to Unreal's Z-up internally.

The skeleton points **ARE NOT being converted** in the JSON, which is causing the sideways tree issue.

---

## What the PVE Plugin Actually Does

### The Real Coordinate Transformation

**File: `PVJSONHelper.h` (lines 452, 78-79, 92-93)**

The PVE plugin reads Y-up JSON and converts to Z-up:

```cpp
// Line 452: Skeleton point positions
const FVector3f Position = FVector3f(PointPosition[0]->AsNumber(),
                                    PointPosition[2]->AsNumber(),  // Swap!
                                    PointPosition[1]->AsNumber()) * 100.0f;

// Lines 92-93: Vector attributes (same swap)
CurrentAttrib.Emplace(AttribValues[ElemIndex]->AsNumber(),
                     AttribValues[ElemIndex + 2]->AsNumber(),    // Swap!
                     AttribValues[ElemIndex + 1]->AsNumber());

// Lines 300-311: Foliage positions (same swap)
const FVector3f PivotPoint = FVector3f(
    PivotPoints[j * 3]->AsNumber(),
    PivotPoints[(j * 3) + 2]->AsNumber(),    // Swap!
    PivotPoints[(j * 3) + 1]->AsNumber()) * 100.0f;
```

### The Pattern

**JSON format** (Y-up - what PVE expects):
```
[X, Y_up, Z]
```

**Gets converted to Unreal** (Z-up):
```
[X, Z_up, Y]
```

This is done **inside the plugin for ALL data**: skeleton points, foliage, vectors, normals.

---

## Your Coordinate System Setup

### Grove
- **Up axis: Y** (standard for plant/tree simulations)
- **Unit: Meters**
- **Format**: `(x, y_up, z)`

### JSON (What PVE Expects)
- **Up axis: Y** (matches Grove!)
- **Unit: Centimeters** (scaled from meters)
- **Format**: `(x, y_up, z)` in centimeters

### Unreal Engine
- **Up axis: Z** (native Unreal convention)
- **Unit: Centimeters**
- **Format**: `(x, y, z_up)`

---

## The Problem: Your Current Conversion Is WRONG

### Your Current Code

**File: `src/growpy/io/pve_foliage_extractor.py` lines 13-26**

```python
def grove_to_pve_position(grove_pos: Tuple[float, float, float]) -> List[float]:
    """
    Convert Grove position to PVE format.
    Grove uses Z-up meters, PVE uses Y-up centimeters.  # ← WRONG COMMENT
    """
    x, y, z = grove_pos
    return [x * 100.0, z * 100.0, y * 100.0]  # ← WRONG TRANSFORMATION
```

This function:
1. **Incorrectly assumes Grove uses Z-up** (it uses Y-up!)
2. **Applies an unwanted axis swap** `(x, z, y)`
3. **Results in the tree being sideways** because it's double-converted

### What Happens

**Grove produces**: `(x=14, y_up=6, z=0)` - tree grows along Y axis (up)

**Your code converts to**: `(1400, 0, 600)` - treating it as if Grove was Z-up

**PVE plugin receives**: `(1400, 0, 600)` (Y-up format)

**PVE converts to**: `(1400, 600, 0)` - swaps Y and Z

**Result in Unreal**: Tree grows along Y axis instead of Z axis = **SIDEWAYS** ❌

---

## The Correct Transformation

### What You Should Do

**Grove (Y-up, meters)** → **PVE (Y-up, centimeters)**

Since both use Y-up, you only need to **scale and copy**:

```python
def grove_to_pve_position(grove_pos: Tuple[float, float, float]) -> List[float]:
    """
    Convert Grove position to PVE format.

    Grove uses Y-up meters.
    PVE expects Y-up centimeters.
    NO axis swapping needed!
    """
    x, y, z = grove_pos
    return [x * 100.0, y * 100.0, z * 100.0]  # Just scale, no swap!
```

### What Happens With Correct Conversion

**Grove produces**: `(x=14, y_up=6, z=0)` in meters

**Correct conversion**: `(1400, 600, 0)` in centimeters - **Y-up preserved**

**PVE plugin receives**: `(1400, 600, 0)` with Y-up

**PVE converts to Unreal**: `(1400, 0, 600)` - swaps Y and Z to Z-up

**Result in Unreal**: Tree grows along Z axis (up) = **CORRECT ORIENTATION** ✓

---

## Why Skeleton Points Are Not Converted

Looking at your code:

**File: `src/growpy/io/pve_grove_mapper.py` line 271**

```python
# Get positions - just copies Grove coordinates as-is
positions = [[p[0], p[1], p[2]] for p in skeleton_points]
```

This doesn't apply the `grove_to_pve_position()` conversion at all. Even worse, since `grove_to_pve_position()` does the wrong transformation, it's actually **better** that skeleton points aren't converted!

The real fix is:
1. Fix `grove_to_pve_position()` to not swap axes
2. Apply it to skeleton points (line 271)
3. Verify foliage also uses the corrected function

---

## The Complete Fix

### Fix #1: Correct the Conversion Function

**File**: `src/growpy/io/pve_foliage_extractor.py` lines 13-26

Change from:
```python
def grove_to_pve_position(grove_pos: Tuple[float, float, float]) -> List[float]:
    """
    Convert Grove position to PVE format.
    Grove uses Z-up meters, PVE uses Y-up centimeters.
    """
    x, y, z = grove_pos
    return [x * 100.0, z * 100.0, y * 100.0]  # Wrong: swaps Y and Z
```

To:
```python
def grove_to_pve_position(grove_pos: Tuple[float, float, float]) -> List[float]:
    """
    Convert Grove position to PVE format.

    Grove uses Y-up meters.
    PVE expects Y-up centimeters.

    Transformation: Just scale by 100, preserve Y-up axis.
    PVE plugin will convert Y-up to Z-up internally.
    """
    x, y, z = grove_pos
    return [x * 100.0, y * 100.0, z * 100.0]  # Correct: scale only, no swap
```

Also fix the vector conversion:

Change from:
```python
def grove_to_pve_vector(grove_vec: Tuple[float, float, float]) -> List[float]:
    """Convert Grove direction vector to PVE format."""
    x, y, z = grove_vec
    return [x, z, y]  # Wrong: swaps Y and Z
```

To:
```python
def grove_to_pve_vector(grove_vec: Tuple[float, float, float]) -> List[float]:
    """
    Convert Grove direction vector to PVE format.

    Grove uses Y-up.
    PVE expects Y-up (will convert internally).
    """
    x, y, z = grove_vec
    return [x, y, z]  # Correct: preserve Y-up, no swap
```

### Fix #2: Apply Conversion to Skeleton Points

**File**: `src/growpy/io/pve_grove_mapper.py` line 271

Change from:
```python
positions = [[p[0], p[1], p[2]] for p in skeleton_points]
```

To:
```python
from .pve_foliage_extractor import grove_to_pve_position
positions = [grove_to_pve_position(p) for p in skeleton_points]
```

### Fix #3: Add BudDevelopment (From Earlier Analysis)

Still needed - schema and data extraction (as documented before).

---

## Verification

### Before (Incorrect Coordinate System)

**skeleton_points from Grove**: `(14.0, 6.0, 0.0)` in meters, Y-up

**JSON output** (no conversion): `[14, 6, 0]` - correct Y-up, but meters not centimeters ❌

**In Unreal after PVE conversion**: `[14, 0, 6]` in centimeters
- X = 14cm (right)
- Y = 0cm (forward)
- Z = 6cm (up)

Result: **Tree is sideways** (only 6cm up, mostly extends along X)

### After (Correct Coordinate System)

**skeleton_points from Grove**: `(14.0, 6.0, 0.0)` in meters, Y-up

**JSON output** (with correct conversion): `[1400, 600, 0]` in centimeters, Y-up ✓

**In Unreal after PVE conversion**: `[1400, 0, 600]` in centimeters
- X = 1400cm (right)
- Y = 0cm (forward)
- Z = 600cm (up)

Result: **Tree is upright** (600cm up, extends along Z like Unreal expects)

---

## Summary: Your Insight Was Correct

| Point | Your Thought | Reality |
|-------|-------------|---------|
| Grove uses Y-up | ✓ Correct | Grove uses Y-up (plant standard) |
| Unreal uses Z-up | ✓ Correct | Unreal native is Z-up |
| Skeleton not converted | ✓ Correct | Line 271 doesn't convert at all |
| Foliage converted wrong | ✓ Partially correct | Conversion function has wrong axis swap |
| USDA vs JSON inconsistency | ✓ Correct | JSON should match Grove's Y-up |

**The fix**: Stop swapping axes, just scale from meters to centimeters.

---

## Files to Fix

| File | Line | Change |
|------|------|--------|
| `src/growpy/io/pve_foliage_extractor.py` | 13-40 | Fix coordinate conversions (remove axis swaps) |
| `src/growpy/io/pve_grove_mapper.py` | 271 | Apply corrected conversion to skeleton points |
| `src/growpy/io/pve_schema.py` | 90 | Fix budDevelopment schema (if not done) |
| `src/growpy/io/pve_grove_mapper.py` | 305+ | Add budDevelopment extraction (if not done) |

---

## Technical Reference

**PVJSONHelper.h Code Locations:**
- Line 452: Skeleton point position transformation `(X, Z, Y)` - converts JSON Y-up to Unreal Z-up
- Lines 78-79, 92-93, 136, 145: Vector attribute transformations - same pattern
- Lines 300-311: Foliage data transformations - same pattern

This confirms: **PVE expects Y-up JSON** and converts it to Z-up internally.

Your JSON should be in Y-up format (just like Grove), and PVE will handle the Unreal display correctly.
