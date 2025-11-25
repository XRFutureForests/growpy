# Coordinate Conversion Scope - USDA vs JSON

## The Good News ✓

The coordinate conversion functions **ONLY affect JSON/PVE export**, NOT USDA/USD files.

They are completely separate code paths with independent coordinate systems.

---

## Architecture: Two Independent Export Systems

### System 1: USDA/USD Export (Unreal Assembly)

**Files Involved:**
- `src/growpy/io/tree_export.py` - Skeleton export
- `src/growpy/io/assembly_export.py` - Assembly/twig export
- `src/growpy/io/usd_export.py` - Core USD writing

**Coordinate System:**
- Z-up (Unreal native)
- Meters
- No coordinate conversion

**Key Code (assembly_export.py:91-93):**
```python
# Set stage metadata to match tree USD (Z-up, meters)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
```

**Position Handling (assembly_export.py:364-388):**
```python
for placement in placement_list:
    pos = placement["position"]
    # Direct to USD - NO conversion
    all_positions.append(Gf.Vec3f(pos[0], pos[1], pos[2]))
```

**Comment (assembly_export.py:373-374):**
```python
# CRITICAL: Positions from Grove API are already in the correct coordinate space
# The bindJoints attribute tells Unreal which skeleton joint each instance follows
```

---

### System 2: JSON/PVE Export (Procedural Vegetation Editor)

**Files Involved:**
- `src/growpy/io/pve_grove_mapper.py` - Point/primitive mapping
- `src/growpy/io/pve_foliage_extractor.py` - Conversion functions
- `src/growpy/io/pve_schema.py` - Schema definition

**Coordinate System:**
- Y-up (PVE format, not Unreal native)
- Centimeters
- Uses conversion functions

**Conversion Functions (pve_foliage_extractor.py:13-40):**
```python
def grove_to_pve_position(grove_pos):
    x, y, z = grove_pos
    return [x * 100.0, z * 100.0, y * 100.0]  # Scale & swap

def grove_to_pve_vector(grove_vec):
    x, y, z = grove_vec
    return [x, z, y]  # Swap only
```

---

## Function Usage - Where Conversion Is Applied

### Location 1: pve_foliage_extractor.py (Internal to extraction)

```python
# Lines 69-70: Converting twig vectors
up_pve = grove_to_pve_vector(up_grove)
normal_pve = grove_to_pve_vector(normal_grove)

# Lines 218, 222: Converting twig positions
pve_pos = grove_to_pve_position(position)
pve_normal = grove_to_pve_position(normal)
```

**Scope**: Only affects extracted foliage/twig data for PVE format

---

### Location 2: pve_grove_mapper.py (Pivot point conversion)

```python
# Line 571: Import (only here!)
from .pve_foliage_extractor import grove_to_pve_position

# Line 580: Convert pivot points for PVE
pve_pos = grove_to_pve_position(pos)
pivot_locations.append(list(pve_pos))
```

**Scope**: Only affects PVE primitive pivot points, not USDA

---

## NOT Used In USDA Export

The conversion functions are **NOT imported or used** anywhere in:
- `tree_export.py` - Skeleton export for USDA
- `assembly_export.py` - Assembly/twig export for USDA
- `usd_export.py` - Core USD file writing

---

## Data Flow Diagram

```
Grove Tree Simulation
    ├─ Skeleton points
    ├─ Twig positions
    └─ Growth data
         │
         ├─ USDA Export Path
         │  └─> [Z-up, meters, direct]
         │      └─> assembly_export.py
         │          └─> Gf.Vec3f(x, y, z)  [NO conversion]
         │              └─> Output: USDA file (Z-up)
         │
         └─ JSON/PVE Export Path
            └─> [Apply conversion]
                └─> pve_foliage_extractor.py
                    └─> grove_to_pve_position(x,y,z)
                        └─> [x*100, z*100, y*100]
                            └─> pve_grove_mapper.py
                                └─> JSON output (Y-up, cm)
```

---

## Verification: No Shared Code Between Paths

### USDA Imports (tree_export.py, assembly_export.py):
```python
from pxr import Usd, UsdGeom, ...
# No imports from pve_foliage_extractor
```

### JSON Imports (pve_grove_mapper.py):
```python
from .pve_foliage_extractor import grove_to_pve_position
# Only here, not in USDA code
```

### Skeleton Export (tree_export.py):
```python
# Line 1019-1022: Direct position handling
world_pos = Gf.Vec3d(start_point.x, start_point.y, start_point.z)
local_pos = world_pos - tree_offset  # NO conversion
bone_positions[global_bone_id] = local_pos
```

---

## What This Means For Your Fix

When you change `grove_to_pve_position()` and `grove_to_pve_vector()`:

### ✓ Will Be Affected:
- JSON/PVE preset files
- Procedural Vegetation Editor import
- Foliage positions in PVE
- Material selection in PVE

### ✓ Will NOT Be Affected:
- USDA/USD assembly files
- Tree skeleton export
- Twig/foliage USD export
- Any Unreal direct import of USD files

---

## Safe to Modify

You can safely modify the coordinate conversion functions because:

1. **Isolated module**: `pve_foliage_extractor.py` is only imported by PVE export code
2. **No USDA imports**: USDA export code doesn't use these functions
3. **Clear separation**: USDA uses Unreal's native Z-up directly
4. **No cross-contamination**: Different output formats, different code paths

---

## Summary

| System | Coordinates | Conversion | Files |
|--------|-------------|------------|-------|
| **USDA/USD** | Z-up, meters | NONE (direct) | tree_export.py, assembly_export.py |
| **JSON/PVE** | Y-up, centimeters | grove_to_pve_*() | pve_grove_mapper.py, pve_foliage_extractor.py |

**Your fix is safe**: Changing the conversion functions will only affect JSON/PVE export, not USDA files.

The two systems are completely independent with no shared coordinate conversion logic.
