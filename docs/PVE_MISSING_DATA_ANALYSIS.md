# PVE Preset Missing Data Analysis & Implementation Guide

## Overview

Analysis of missing data in PVE preset JSON generation and how to extract or generate it from The Grove API.

## Critical Missing Data

### 1. **Foliage Instancer Data** (HIGHEST PRIORITY)

**Status:** Completely missing - trees have no leaves!

**Required Structure:**

```json
"primitives": {
  "attributes": {
    "instancer_name": {
      "isArray": true,
      "size": 1,
      "type": "string",
      "value": [  // Per branch, array of twig/leaf names
        ["SM_Leaf_01", "SM_Leaf_01", "SM_Leaf_02"],  // Branch 0
        ["SM_Leaf_01"],  // Branch 1
        []  // Branch 2 (no leaves)
      ]
    },
    "instancer_pivot": {
      "isArray": true,
      "size": 3,
      "type": "float",
      "value": [  // Per branch, flattened xyz positions
        [x1, z1, y1, x2, z2, y2, x3, z3, y3],  // Branch 0 (3 leaves)
        [x1, z1, y1],  // Branch 1 (1 leaf)
        []  // Branch 2 (no leaves)
      ]
    },
    "instancer_UP": {
      "isArray": true,
      "size": 3,
      "type": "float",
      "value": [  // Per branch, flattened up vectors
        [ux1, uz1, uy1, ux2, uz2, uy2, ux3, uz3, uy3],
        [ux1, uz1, uy1],
        []
      ]
    },
    "instancer_N": {
      "isArray": true,
      "size": 3,
      "type": "float",
      "value": [  // Per branch, flattened normal vectors
        [nx1, nz1, ny1, nx2, nz2, ny2, nx3, nz3, ny3],
        [nx1, nz1, ny1],
        []
      ]
    },
    "instancer_scale": {
      "isArray": true,
      "size": 1,
      "type": "float",
      "value": [  // Per branch, scale values
        [scale1, scale2, scale3],  // Branch 0
        [scale1],  // Branch 1
        []
      ]
    },
    "instancer_LFR": {
      "isArray": true,
      "size": 1,
      "type": "float",
      "value": [  // Per branch, length from root values
        [lfr1, lfr2, lfr3],  // Branch 0
        [lfr1],  // Branch 1
        []
      ]
    }
  }
}
```

**How to Extract from Grove:**

```python
# Grove provides twigs via build_models with build_twigs=True
models = grove.build_models({
    "resolution": 24,
    "build_twigs": True,  # CRITICAL for foliage
    "twig_density": 1.0,  # Adjust density
})

# For each tree model
for tree_idx, model in enumerate(models):
    # Twigs are in model.twigs - list of twig instances
    twigs = model.twigs  # List of (position, rotation, scale, type_id)
    
    # Each twig has:
    # - twig.position: (x, y, z) world position
    # - twig.rotation: (x, y, z, w) quaternion
    # - twig.scale: float
    # - twig.type_id: int (index into twig_types)
    # - twig.branch_id: int (which branch it's on)
    
    # Group twigs by branch_id
    twigs_by_branch = {}
    for twig in twigs:
        if twig.branch_id not in twigs_by_branch:
            twigs_by_branch[twig.branch_id] = []
        twigs_by_branch[twig.branch_id].append(twig)
```

**Coordinate Conversion (Z-up to Y-up + cm scale):**

```python
# Grove uses Z-up meters, PVE uses Y-up centimeters
def grove_to_pve_position(grove_pos):
    """Convert Grove position to PVE format."""
    x, y, z = grove_pos
    return [x * 100.0, z * 100.0, y * 100.0]  # X, Z, Y in cm

def grove_to_pve_vector(grove_vec):
    """Convert Grove direction vector to PVE format."""
    x, y, z = grove_vec
    return [x, z, y]  # No scaling for unit vectors

def quaternion_to_up_normal(quat):
    """Convert quaternion to up and normal vectors."""
    # Extract rotation matrix from quaternion
    # Up vector = transformed (0, 0, 1)
    # Normal vector = transformed (0, 1, 0)
    import numpy as np
    from scipy.spatial.transform import Rotation
    
    rot = Rotation.from_quat(quat)  # [x, y, z, w]
    up = rot.apply([0, 0, 1])  # Local Z
    normal = rot.apply([0, 1, 0])  # Local Y
    
    return grove_to_pve_vector(up), grove_to_pve_vector(normal)
```

**Twig Name Mapping:**

```python
# Grove twig types correspond to FBX files
# Need to map Grove twig_type_id to Unreal asset names

# From tree_asset_lookup.csv:
# european_oak -> Twig_01.fbx, Twig_02.fbx, etc.

def get_twig_name(species_name, twig_type_id):
    """Get Unreal twig asset name."""
    # Simple version - use species-specific naming
    return f"SM_{species_name}_Twig_{twig_type_id:02d}"
    # Or load from config:
    # config = get_config()
    # twig_info = config.get_species_info(species_name)
    # return twig_info['twig_names'][twig_type_id]
```

---

### 2. **Branch Hierarchy (parents/children arrays)**

**Status:** Empty arrays - breaks hierarchy traversal

**Required Structure:**

```json
"primitives": {
  "attributes": {
    "parents": {
      "isArray": true,
      "size": 1,
      "type": "int",
      "value": [  // Per branch, array of parent branch indices
        [-1],     // Branch 0: root, no parent
        [0],      // Branch 1: parent is branch 0
        [0],      // Branch 2: parent is branch 0
        [1],      // Branch 3: parent is branch 1
        [1, 0]    // Branch 4: parents are 1 and 0 (grafted?)
      ]
    },
    "children": {
      "isArray": true,
      "size": 1,
      "type": "int",
      "value": [  // Per branch, array of child branch indices
        [1, 2, 7, 12],  // Branch 0: children are 1, 2, 7, 12
        [3, 4, 5, 6],   // Branch 1: children are 3-6
        [],             // Branch 2: no children (terminal)
        []              // Branch 3: no children
      ]
    }
  }
}
```

**How to Extract from Grove:**

```python
# Grove skeleton has branch hierarchy
skeleton = skeletons[tree_index]

# skeleton.poly_lines - list of branch polylines
# Each poly_line has .parent_index

# Build hierarchy
num_branches = len(skeleton.poly_lines)
parents_array = []
children_array = [[] for _ in range(num_branches)]

for branch_idx, poly_line in enumerate(skeleton.poly_lines):
    # Get parent
    parent_idx = poly_line.parent_index
    if parent_idx == -1:
        parents_array.append([-1])  # Root branch
    else:
        parents_array.append([parent_idx])
        # Add this branch as child of parent
        children_array[parent_idx].append(branch_idx)

# Result:
# parents_array: [ [-1], [0], [0], [1], [1] ]
# children_array: [ [1,2], [3,4], [], [], [] ]
```

---

### 3. **Growth Parameter Curves (globalAttributes)**

**Status:** All empty arrays - missing growth model data

**Required Values (from Hazel reference):**

```json
"globalAttributes": {
  "phyllotaxyLeaf": {  // REQUIRED by C++ validation!
    "isArray": true,
    "size": 1,
    "type": "float",
    "value": [
      0.0,      // Leaf arrangement type
      198.39,   // Divergence angle (degrees)
      51.63,    // Vertical distance
      1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 2.0, 0.0547
    ]
  },
  "phototropism": {  // Light attraction curve
    "value": [0.2465, 0.6691, 0.4671, 0.4977]
  },
  "phyllotaxy": {  // Branch arrangement curve
    "value": [0.0, 202.7, 50.21, 1.0, 1.0, 0.0, 60.0, 0.0, ...]
  },
  "axialElongation": {  // Growth curve
    "value": [0.25, 0.0, 0.4819, 0.0, 0.0, 1.0]
  }
  // ... many more curves
}
```

**Extraction Strategy:**

1. **From .seed.json files (BEST source):**

```python
import json
from pathlib import Path

def load_growth_params_from_seed(species_name):
    """Load growth parameters from Grove .seed.json file."""
    config = get_config()
    species_info = config.get_species_info(species_name)
    seed_path = species_info['preset_path']  # Path to .seed.json
    
    with open(seed_path, 'r') as f:
        seed_data = json.load(f)
    
    # Extract relevant curves from seed data
    # Seed files have parameters like:
    # - phototropism_curve
    # - elongation_curve
    # - phyllotaxy settings
    # Map these to PVE format
    
    return {
        "phyllotaxyLeaf": extract_phyllotaxy_leaf(seed_data),
        "phototropism": extract_curve(seed_data, "phototropism"),
        # ... etc
    }
```

2. **Default values (FALLBACK):**

```python
# Use Hazel values as sensible defaults for broadleaf trees
HAZEL_DEFAULTS = {
    "phyllotaxyLeaf": [0.0, 198.39, 51.63, 1.0, 1.0, 0.0, 0.0, 0.0, 
                       0.0, 0.0, 0.0, 2.0, 2.0, 0.0547],
    "phototropism": [0.2465, 0.6691, 0.4671, 0.4977],
    "phototropismChild": [0.1863, 0.3753, 0.1659, 0.1687],
    "phyllotaxy": [0.0, 202.7, 50.21, 1.0, 1.0, 0.0, 60.0, 0.0, 
                   0.0, 0.0, 0.0, 2.0, 2.0, 0.2196],
    # ... etc from Hazel JSON
}

def get_growth_params(species_name, use_defaults=False):
    """Get growth parameters, with fallback to defaults."""
    if use_defaults:
        return HAZEL_DEFAULTS.copy()
    
    try:
        return load_growth_params_from_seed(species_name)
    except Exception as e:
        print(f"Warning: Could not load growth params, using defaults: {e}")
        return HAZEL_DEFAULTS.copy()
```

---

### 4. **Plant Profiles (Optional but Useful)**

**Status:** Empty arrays

**Required Structure:**

```json
"globalAttributes": {
  "plantProfile_1": {
    "isArray": true,
    "size": 1,
    "type": "float",
    "value": [0.8525, 0.8706, 0.8546, ...]  // ~100 values
  },
  "plantProfile_2": { "value": [...] },
  // ... up to plantProfile_5
}
```

**What They Represent:**

- Age-based attribute curves (e.g., vigor over tree lifetime)
- Used for procedural variation in PVE
- Can be generated or use defaults

**Extraction:**

```python
def generate_plant_profiles(num_profiles=5, num_points=100):
    """Generate smooth profile curves."""
    import numpy as np
    
    profiles = {}
    for i in range(1, num_profiles + 1):
        # Generate smooth random curve
        # Start high (~0.85), peak mid-life (~0.98), end high (~0.96)
        t = np.linspace(0, 1, num_points)
        
        # Use sin-based curve with variation
        base = 0.85 + 0.13 * np.sin(np.pi * t)  # 0.85 to 0.98 range
        noise = np.random.normal(0, 0.02, num_points)  # Small variation
        profile = np.clip(base + noise, 0.8, 1.0)
        
        profiles[f"plantProfile_{i}"] = {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": profile.tolist()
        }
    
    return profiles
```

---

## Implementation Priority

### Phase 1: Foliage Data (CRITICAL)

1. Extract twig instances from `grove.build_models(build_twigs=True)`
2. Group by branch_id
3. Convert positions/rotations to PVE format
4. Generate instancer_* arrays
5. Map twig_type_id to Unreal asset names

### Phase 2: Branch Hierarchy (IMPORTANT)

1. Extract parent_index from skeleton.poly_lines
2. Build parents array (trivial)
3. Build children array (inverse of parents)

### Phase 3: Growth Parameters (NICE TO HAVE)

1. Load from .seed.json if available
2. Use Hazel defaults as fallback
3. Add configuration option to override

### Phase 4: Plant Profiles (OPTIONAL)

1. Generate synthetic profiles OR
2. Use Hazel profiles as defaults

---

## Configuration Options

Add to PVE generation function:

```python
def generate_pve_from_grove(
    grove: Any,
    output_path: Path,
    species_name: str,
    tree_index: int = 0,
    verbose: bool = True,
    # NEW PARAMETERS:
    use_default_growth_params: bool = True,  # Use Hazel defaults
    twig_density: float = 1.0,  # Foliage density multiplier
    include_plant_profiles: bool = True,  # Generate profiles
    custom_growth_params: Optional[Dict] = None,  # Manual override
) -> Dict:
    """
    Generate PVE preset JSON with full foliage and growth data.
    """
    # ... implementation
```

---

## Testing Approach

1. **Minimal test:** Export Oak with foliage only
2. **Full test:** Export with foliage + hierarchy + defaults
3. **Compare:** Load in Unreal and compare to Hazel preset
4. **Iterate:** Adjust parameters to match expected behavior

---

## Code Structure

```
src/growpy/io/
├── pve_grove_mapper.py          # Main mapper (UPDATE)
├── pve_schema.py                # Schema definition (OK)
├── pve_foliage_extractor.py    # NEW: Extract foliage from Grove
├── pve_hierarchy_builder.py    # NEW: Build parent/child arrays
├── pve_growth_defaults.py      # NEW: Default growth parameters
└── pve_preset_json.py           # High-level API (MINOR UPDATE)
```

---

## Next Steps

1. Create `pve_foliage_extractor.py` with twig extraction
2. Create `pve_hierarchy_builder.py` for parent/child arrays
3. Create `pve_growth_defaults.py` with Hazel reference values
4. Update `pve_grove_mapper.py` to use new extractors
5. Test with European Oak
6. Compare in Unreal Engine
7. Document any differences from Hazel
