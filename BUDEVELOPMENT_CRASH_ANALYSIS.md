# BudDevelopment Array Size Crash Analysis

## Crash Details

```
Assertion failed: BudDevelopment.Num() > 2
[File: PVMaterialSettings.cpp]
[Line: 71]
```

The crash occurs when connecting the preset to a generate mesh node, during the material settings application phase.

## Root Cause

[PVMaterialSettings.cpp:71](data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Implementations/PVMaterialSettings.cpp#L71) requires:

```cpp
TArray<int> BudDevelopment = PointFacade.GetBudDevelopment(PointIndex);
check(BudDevelopment.Num() > 2);  // Line 71 - CRASHES HERE
MinGeneration = FMath::Min(MinGeneration, BudDevelopment[0]);
MinAge = FMath::Min(MinAge, BudDevelopment[2]);
```

The code accesses:
- `BudDevelopment[0]` - Generation value
- `BudDevelopment[2]` - Age value

This requires the array to have **at least 3 elements** (indices 0, 1, 2).

## Format Comparison

### Hazel JSON (CORRECT)
```json
"budDevelopment": {
  "isArray": true,
  "size": 1,
  "type": "int",
  "values": [
    [1, 17, 17, 0, 0, 16],    // 6 elements: [gen, ?, age, ?, ?, ?]
    [1, 17, 17, 0, 0, 16],    // 6 elements each
    ...
  ]
}
```

Array structure (inferred from code):
- Index 0: Generation
- Index 1: Unknown (not used in crash line, but used in line 91)
- Index 2: Age
- Index 3-5: Unknown

### Beech JSON (WRONG - Will Crash)
```json
"budDevelopment": {
  "isArray": true,
  "size": 1,
  "type": "int",
  "values": [
    [0],     // Only 1 element! ❌
    [0],     // Only 1 element!
    [0],
    ...
  ]
}
```

**The beech JSON has only 1 element per array, but 3+ elements are required.**

## What BudDevelopment Represents

From [PVMaterialSettings.cpp](data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Implementations/PVMaterialSettings.cpp):

- **BudDevelopment[0]**: Generation number (how many generations deep in the tree)
- **BudDevelopment[2]**: Age (growth stage/cycle)
- BudDevelopment[1], [3-5]: Other bud properties (not accessed in crash path)

The material system uses generation and age to compute which material/UV offset to apply to branches.

## Forest Generation Issue

The beech forest generation is outputting incomplete budDevelopment data. This suggests either:

1. **Forest generation script is not computing budDevelopment correctly**
2. **The JSON export is only taking the first value of budDevelopment**
3. **The growth model is not setting proper bud development values**

## Required Fix

The beech JSON needs to have budDevelopment arrays with **at least 3 elements** per entry:

```json
"budDevelopment": {
  "isArray": true,
  "size": 1,
  "type": "int",
  "values": [
    [<generation>, <unknown1>, <age>, <unknown3>, <unknown4>, <unknown5>],
    [<generation>, <unknown1>, <age>, <unknown3>, <unknown4>, <unknown5>],
    ...
  ]
}
```

## Next Steps

1. Check the forest generation scripts to see where budDevelopment is calculated
2. Verify the growth model is properly setting all 6 values for budDevelopment
3. Ensure the JSON export includes all budDevelopment values, not just the first one
4. Compare with the hazel reference data to understand expected value ranges

## References

- **Crash location**: [PVMaterialSettings.cpp:66-79](data/tmp/ProceduralVegetationEditor/Source/ProceduralVegetation/Private/Implementations/PVMaterialSettings.cpp#L66-L79)
- **Related check**: Line 91 uses `check(BudDevelopment.Num() >= 2)` (less strict, but still requires 3 elements for safety)
- **Point facade**: Returns budDevelopment as `const TArray<int>&`
