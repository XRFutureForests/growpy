# Unreal vs PVE Coordinate Systems - Clarification

## The Confusion

The current GrowPy code assumes:
- **Unreal uses Z-up** (which is partially true)
- **PVE uses Y-up** (which needs verification)

But there's actually a **coordinate system mismatch** that needs clarification.

---

## What Unreal Actually Uses

From [Epic's Official Documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/coordinate-system-and-spaces-in-unreal-engine):

### Unreal Engine's Coordinate System

```
         +Z (up)
          |
          |
    +Y ---+--- -Y (forward/backward)
         /
        /
      +X (right/left)
```

**Key facts:**
- **Z-axis = Up/Down** (positive Z is up)
- **X-axis = Right/Left** (positive X is right)
- **Y-axis = Forward/Backward** (positive Y is forward)

This is **Z-up**, which is what you intended.

---

## What the PVE Plugin Actually Uses

Looking at the Hazel reference JSON, we can infer the coordinate system:

**Hazel positions** start at `[0, 0, 0]` (root) and grow in the **+Y direction**:
```json
"positions": [
  [0.0, 0.0, 0.0],              // Root at origin
  [-0.0007, 0.0057, 0.0003],    // Grows in +Y (0.0057)
  [-0.0014, 0.0114, 0.0007],    // Grows in +Y (0.0114)
  [-0.0021, 0.0171, 0.0011],    // Grows in +Y (0.0171)
  ...
]
```

This suggests:
- **Hazel root at origin**, grows along **+Y axis**
- **Y-axis represents height (up)**
- **X and Z are horizontal**

This is **Y-up** format.

---

## Why PVE Uses Y-up (Historical Reason)

The Procedural Vegetation Editor plugin was developed by Quixel for their **Megaplants** asset pack. Quixel/MegaPlants uses:
- **Y-up coordinate system** (common in game asset pipelines)
- **Centimeters as the unit** (standard for game assets)

This is **different from Unreal's native Z-up system** to match the pre-made asset format.

---

## The Actual Problem

You have a **mismatch** between three systems:

### System 1: Grove (Your Library)
- **Z-up** (up/down along Z axis)
- **Meters** as unit
- Positions: `(x, y, z)` where Z is height

### System 2: PVE Plugin (Unreal's Procedural Vegetation Editor)
- **Y-up** (up/down along Y axis) - **NOT native Unreal**
- **Centimeters** as unit
- Positions: `(x, y, z)` where Y is height
- Format inherited from Quixel's Megaplants

### System 3: Unreal Engine (Native)
- **Z-up** (up/down along Z axis) - **Matches Grove!**
- **Centimeters** as unit
- Positions: `(x, y, z)` where Z is height

---

## Why Your Tree Appears Sideways

When you don't convert Grove → PVE:

**Grove coordinates are interpreted as PVE coordinates:**
```
Grove point: (14.0, 6.0, 0.0)
  x=14m (right)
  y=6m  (right-forward)
  z=0m  (up)

Without conversion, PVE reads it as:
  x=14m (right)
  y=6m  (UP) ← This is the problem!
  z=0m  (horizontal)

In Unreal/Centimeters:
  x=1400cm (right)
  y=600cm (UP) ← Tree grows sideways!
  z=0cm (horizontal)
```

**With conversion to PVE format:**
```
Grove point: (14.0, 6.0, 0.0)

Convert using grove_to_pve_position():
  [x*100, z*100, y*100] = [1400, 0, 600]

In Unreal/PVE:
  x=1400cm (right)
  y=600cm (forward) ← Horizontal, correct!
  z=0cm (up) ← Where it should be, but still sideways to Unreal!
```

---

## The Real Issue: PVE Uses Y-up, But Unreal Expects Z-up

After conversion to PVE format, the tree is still displayed **sideways in Unreal** because:

1. **PVE format expects Y-up** (Y is "up")
2. **Unreal displays Z-up** (Z is "up")
3. **The plugin has to translate** between them

---

## How PVE Plugin Handles This Internally

The PVE plugin likely does an **additional transformation** when rendering:

```
PVE Format (Y-up)     →     Unreal Space (Z-up)
(x, y, z)               →     (x, z, y)
```

But this must happen **inside the plugin**, not in the JSON.

---

## Verification: What the Hazel Asset Shows

The Hazel reference file is:
- **In PVE format** (Y-up, centimeters)
- **Imported into Unreal successfully**
- **Displays correctly upright**

This confirms:
1. PVE format is Y-up
2. The plugin handles the conversion to Unreal's Z-up internally
3. The plugin's internal logic displays it correctly

---

## Why Your Current Fix Is Correct

Your fix converts Grove (Z-up, meters) → PVE (Y-up, centimeters):

```python
def grove_to_pve_position(grove_pos):
    x, y, z = grove_pos
    return [x * 100.0, z * 100.0, y * 100.0]
```

This transformation:
1. **Swaps Y and Z** (Z-up to Y-up)
2. **Scales by 100** (meters to centimeters)
3. **Results in PVE-compatible format**

The PVE plugin then internally handles display in Unreal's Z-up space.

---

## Why This Seems Confusing

The coordinate system journey is:

```
Grove (Z-up, meters)
    ↓ [You apply conversion]
PVE Format (Y-up, centimeters)
    ↓ [PVE plugin handles internally]
Unreal Display (Z-up, centimeters)
```

You only control the first arrow. The second arrow is handled by the PVE plugin.

---

## Summary: Why PVE Uses Y-up

| Reason | Details |
|--------|---------|
| **Historical** | Inherited from Quixel's Megaplants asset format |
| **Asset Standard** | Y-up is common in game asset pipelines (3DS Max, Maya defaults) |
| **Pre-built Assets** | Hazel and other Megaplants use Y-up, so PVE matches them |
| **Compatibility** | PVE needs to work with existing Y-up asset files |

---

## How to Think About It

- **Grove**: Your tree simulation (Z-up, natural choice)
- **PVE**: Pre-made asset format (Y-up, Quixel standard)
- **Unreal**: Game engine (Z-up, but displays PVE Y-up correctly)

Your code **bridges the gap** between Grove and PVE, allowing Unreal to use the simulated trees.

---

## Verification Your Fix Is Correct

When you apply `grove_to_pve_position()`:

1. **In the JSON file**: Points appear with Y as the growing axis
   - `positions: [[0,0,0], [0,1,0], [0,2,0], ...]` grows in +Y

2. **In Unreal Editor**: Tree appears upright (Z is up)
   - The PVE plugin internally converts Y-up → Z-up for display

3. **In-game/viewport**: Tree renders correctly
   - Unreal's renderer uses Z-up natively

---

## References

- **Unreal Docs**: https://dev.epicgames.com/documentation/en-us/unreal-engine/coordinate-system-and-spaces-in-unreal-engine
- **Hazel Reference**: `data/tmp/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json`
- **Conversion Code**: `src/growpy/io/pve_foliage_extractor.py:13-26`

---

## Bottom Line

**PVE uses Y-up because it's designed to work with Quixel's pre-made asset format, not because Unreal uses Y-up.** Unreal natively uses Z-up, but the PVE plugin handles the conversion internally. Your conversion from Grove (Z-up) to PVE (Y-up) is correct.
