# Wind JSON Implementation Summary

## Problem Analysis

The initial wind JSON generation had issues with joint classification:

1. **Mass-based grouping was unreliable**: Branch mass correlates with thickness, not flexibility
2. **Missing hierarchy information**: Branch position in tree structure wasn't being used
3. **Overcomplicated thresholds**: Percentile-based mass thresholds were fragile and confusing

## Solution: Age-Based Classification

The Grove API provides an `age` attribute on skeleton points that directly represents growth order:

- **Higher age = older growth = trunk/main structure** (Group 0 - rigid)
- **Medium age = primary branches** (Group 1 - medium flexibility)  
- **Lower age = newer growth = tips and secondary branches** (Group 2 - most flexible)

This is simpler, more predictable, and aligns with how trees actually grow.

## Classification Logic

```python
# Group 0 (Trunk/Rigid): Maximum age - main trunk structure
if age == max_age:
    return 0

# Group 1 (Primary/Medium): Medium age OR branch roots at shallow depth
elif age >= max_age * 0.5 or (is_branch_root and branch_depth <= 1):
    return 1

# Group 2 (Tips/Flexible): Everything else - young growth
else:
    return 2
```

## Key Attributes Used

From Grove skeleton data:

- `skeleton.point_attribute_age`: Growth order (0 = newest, max = oldest)
- `bones_info`: List of bone tuples with hierarchy information
  - `is_branch_root`: Whether this bone starts a new branch
  - `branch_id`: Unique identifier for each branch polyline
  - `parent_bone_id`: Parent bone in hierarchy

Derived attributes:

- `branch_depth`: Number of branch forks from trunk (0 = trunk, 1 = primary, 2+ = secondary)

## Test Results

Using `grove_geometry_dump/tree_0` data (25 skeleton points, 2 growth flushes):

```
Age distribution: [2, 2, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
Branch depth: max_depth=1, branch_roots=6

Classification:
  Group 0 (trunk/rigid):       2 points  (oldest trunk segments)
  Group 1 (primary/medium):    9 points  (primary branches + medium-age trunk)
  Group 2 (tips/flexible):    14 points  (branch tips + youngest growth)
```

## JSON Output Format

Matches Unreal Engine DynamicWind schema from megaplant example:

```json
{
    "Joints": [
        {
            "JointName": "tree_point_0",
            "SimulationGroupIndex": 0
        },
        ...
    ],
    "SimulationGroups": [],
    "bIsGroundCover": false,
    "GustAttenuation": 0.0
}
```

## Integration Points

### During Forest Generation

Wind JSON is generated automatically for skeletal trees in `generate_forest.py`:

```python
from growpy.io.wind_json import generate_wind_json

generate_wind_json(
    tree_usd_path=skeletal_usd_path,
    skeleton=skeleton,           # From grove.build_skeletons()
    bones_info=bones_for_tree,   # From grove.tag_bone_id()
    output_path=wind_json_path,
)
```

### Standalone Generation

Use `generate_wind_json.py` CLI tool for existing USD files:

```bash
# Single tree
python src/growpy/cli/generate_wind_json.py tree_skeletal.usda

# All trees in species directory
python src/growpy/cli/generate_wind_json.py data/output/forest/european_beech/
```

## Benefits of Age-Based Approach

1. **Predictable**: Age directly represents growth order - no complex thresholds
2. **Biologically accurate**: Matches how real trees grow (old trunk, new tips)
3. **Consistent**: Same age value = same classification across different trees
4. **Simple**: One primary attribute instead of combining age + mass + percentiles
5. **Robust**: Works with minimal growth cycles (even 2-3 flushes give good results)

## Known Limitations

- **Minimum growth cycles**: Requires at least 2-3 growth flushes for good age distribution
- **Fallback mode**: If no Grove skeleton data available, falls back to hierarchy depth counting from joint names (less accurate)
- **Branch depth mapping**: Requires bones_info structure; won't work with raw USD files without Grove context

## Future Improvements

Possible enhancements:

- Add secondary attributes (radius, mass) as tiebreakers within same age group
- Support custom classification rules per species
- Add validation that checks distribution (warn if >80% in one group)
- Export SimulationGroups array with physics parameters per group
