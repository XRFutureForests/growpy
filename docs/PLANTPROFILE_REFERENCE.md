# PlantProfile Reference Guide

Quick reference for understanding and creating `plantProfile` arrays in PVE preset JSON files.

## What Are PlantProfiles?

PlantProfiles define the **radial crown envelope** of trees when viewed from above. They control the tree's silhouette and are used by Unreal's Procedural Vegetation Editor for:

- Procedural foliage placement and density
- Crown mesh generation and LOD
- Tree variation and natural irregularity
- Collision boundary approximation

## Data Structure

Each PVE preset JSON requires **5 plantProfile arrays** (`plantProfile_1` through `plantProfile_5`):

```json
{
  "plantProfile_1": {
    "isArray": true,
    "size": 1,
    "type": "float",
    "value": [0.8525, 0.8631, 0.8738, ..., 0.8525]  // Exactly 100 values
  },
  "plantProfile_2": { ... },
  "plantProfile_3": { ... },
  "plantProfile_4": { ... },
  "plantProfile_5": { ... }
}
```

### Array Specifications

- **Length**: Exactly 100 float values (no more, no less)
- **Angular Sampling**: Each value represents 3.6° (360° / 100 samples)
- **Value Range**: Typically 0.75 to 1.0 (normalized radii)
- **Cyclic**: First value must equal last value (smooth 360° wrap)

## Biological Interpretation

Think of each profile as a **top-down outline** of the tree crown:

```text
           North (0°)
               |
               v
       0.85 -------- 0.92
       /                \
  0.80                  0.95  (radii at different angles)
       \                /
       0.88 -------- 0.90
```

- **1.0** = Maximum crown extent at that angle (major branches)
- **0.75** = 75% of maximum (gaps between branches, irregular edges)
- **Values in between** = Smooth transition creating natural crown shape

### Why 100 Samples?

100 samples provides sufficient angular resolution for:

- Natural crown irregularity (10-15 major branch lobes)
- Smooth interpolation between samples
- Efficient memory usage
- Real-time procedural generation in Unreal

## Multiple Profiles for Variation

**Why 5 profiles?**

- PVE randomly selects one of the 5 profiles when spawning each tree instance
- Creates natural forest variation without needing separate preset files
- Each profile should have different irregularities
- Mimics biological variation within a species

**Profile Selection:**

- Instance 1 → Uses `plantProfile_1`
- Instance 2 → Uses `plantProfile_3` (random)
- Instance 3 → Uses `plantProfile_5` (random)
- etc.

## Species-Specific Guidelines

### Broadleaf Trees (Oak, Beech, Maple, Hazel)

**Characteristics:**

- Irregular, asymmetric crowns
- 10-15 major branch lobes visible from above
- Value range: 0.80-1.0
- Gradual transitions between lobes

**Example Profile Pattern:**

```text
Major branches at: 30°, 75°, 120°, 165°, 210°, 255°, 300°, 345°
Create local maxima (≈1.0) at these angles
Minima (≈0.80-0.85) between branches
Smooth Gaussian-like transitions
```

### Coniferous Trees (Pine, Spruce, Fir)

**Characteristics:**

- More uniform, conical crowns
- 3-5 major whorls of branches
- Value range: 0.90-1.0 (less variation)
- Smoother, less irregular outlines

**Example Profile Pattern:**

```text
Fewer, broader lobes
More circular overall shape
Slight tapering effect if representing height-dependent profiles
Less angular variation (values stay closer to 1.0)
```

## Creating Custom Profiles

### Quick Method - Copy Reference

Start with a reference profile from Quixel Megaplants:

```bash
# Extract Hazel profile
python src/growpy/utils/extract_pve_config.py
```

Then modify values in `data/assets/pve_configs/common_hazel_pve.json`:

```python
import json

with open("data/assets/pve_configs/common_hazel_pve.json") as f:
    config = json.load(f)

# Get reference profile
reference = config["plantProfile_1"]["value"]

# Modify for your species (e.g., make more irregular)
for i in range(len(reference)):
    if i % 10 == 0:  # Every 36°, create a lobe
        reference[i] = min(1.0, reference[i] * 1.1)  # Emphasize peaks
    else:
        reference[i] *= 0.95  # Reduce valleys

# Ensure cyclic
reference[-1] = reference[0]

# Save to new species config
with open("data/assets/pve_configs/my_species_pve.json", "w") as f:
    json.dump({"plantProfile_1": {"isArray": True, "size": 1, "type": "float", "value": reference}}, f)
```

### Algorithmic Method - Generate from Scratch

```python
import numpy as np
import json

def generate_broadleaf_profile(num_major_branches=12, irregularity=0.15, seed=None):
    """
    Generate naturalistic broadleaf crown profile
    
    Args:
        num_major_branches: Number of major branch lobes (10-15 typical)
        irregularity: Amount of variation (0.1-0.2 realistic)
        seed: Random seed for reproducibility
    
    Returns:
        List of 100 float values representing crown profile
    """
    if seed is not None:
        np.random.seed(seed)
    
    angles = np.linspace(0, 2*np.pi, 100)
    
    # Start with circular base
    profile = np.ones(100)
    
    # Add major branch lobes at random angles
    branch_angles = np.sort(np.random.uniform(0, 2*np.pi, num_major_branches))
    for branch_angle in branch_angles:
        # Gaussian lobe around each branch
        distance = np.minimum(np.abs(angles - branch_angle), 
                             2*np.pi - np.abs(angles - branch_angle))
        lobe = irregularity * np.exp(-(distance**2) / 0.5)
        profile += lobe
    
    # Add small-scale noise (minor branches, foliage clumps)
    noise = irregularity * 0.3 * np.random.randn(100)
    profile += noise
    
    # Normalize to 0.75-1.0 range
    profile = 0.75 + 0.25 * (profile - profile.min()) / (profile.max() - profile.min())
    
    # Smooth slightly (avoid sharp transitions)
    from scipy.ndimage import gaussian_filter1d
    profile = gaussian_filter1d(profile, sigma=1.5, mode='wrap')
    
    # Ensure cyclic boundary
    profile[-1] = profile[0]
    
    return profile.tolist()

def generate_coniferous_profile(num_whorls=4, irregularity=0.08, seed=None):
    """
    Generate coniferous crown profile (more uniform)
    
    Args:
        num_whorls: Number of branch whorls (3-5 typical)
        irregularity: Amount of variation (0.05-0.10 realistic)
        seed: Random seed for reproducibility
    """
    if seed is not None:
        np.random.seed(seed)
    
    angles = np.linspace(0, 2*np.pi, 100)
    
    # More circular base
    profile = np.ones(100) * 0.95
    
    # Fewer, broader lobes
    whorl_angles = np.linspace(0, 2*np.pi, num_whorls, endpoint=False)
    for whorl_angle in whorl_angles:
        distance = np.minimum(np.abs(angles - whorl_angle),
                             2*np.pi - np.abs(angles - whorl_angle))
        lobe = irregularity * np.exp(-(distance**2) / 1.0)  # Broader lobes
        profile += lobe
    
    # Minimal noise
    noise = irregularity * 0.2 * np.random.randn(100)
    profile += noise
    
    # Normalize to 0.90-1.0 range (less variation)
    profile = 0.90 + 0.10 * (profile - profile.min()) / (profile.max() - profile.min())
    
    # Heavy smoothing
    from scipy.ndimage import gaussian_filter1d
    profile = gaussian_filter1d(profile, sigma=2.5, mode='wrap')
    
    profile[-1] = profile[0]
    
    return profile.tolist()

# Generate 5 variations for a species
def generate_species_profiles(species_type='broadleaf', output_path=None):
    """
    Generate 5 profile variations for a species
    
    Args:
        species_type: 'broadleaf' or 'coniferous'
        output_path: Path to save JSON config (optional)
    
    Returns:
        Dictionary with plantProfile_1 through plantProfile_5
    """
    generator = generate_broadleaf_profile if species_type == 'broadleaf' else generate_coniferous_profile
    
    profiles = {}
    for i in range(5):
        profiles[f"plantProfile_{i+1}"] = {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generator(seed=42+i)  # Different seed for each variation
        }
    
    if output_path:
        with open(output_path, "w") as f:
            json.dump(profiles, f, indent=2)
    
    return profiles

# Example usage
profiles = generate_species_profiles('broadleaf', 'data/assets/pve_configs/my_oak_pve.json')
```

## Visualizing Profiles

Debug and validate profiles with polar plots:

```python
import matplotlib.pyplot as plt
import numpy as np
import json

def visualize_profile(json_path, profile_name="plantProfile_1"):
    """Create polar plot of crown profile"""
    with open(json_path) as f:
        config = json.load(f)
    
    profile = config[profile_name]["value"]
    angles = np.linspace(0, 2*np.pi, len(profile))
    
    fig, ax = plt.subplots(subplot_kw=dict(projection='polar'), figsize=(8, 8))
    ax.plot(angles, profile, linewidth=2)
    ax.fill(angles, profile, alpha=0.3)
    
    ax.set_ylim(0.7, 1.05)
    ax.set_title(f"Crown Profile: {profile_name}\nTop-Down View", pad=20)
    ax.set_theta_zero_location('N')  # North at top
    ax.grid(True)
    
    plt.savefig(f"{profile_name}_visualization.png", dpi=150, bbox_inches='tight')
    plt.show()

def visualize_all_profiles(json_path):
    """Create comparison plot of all 5 profiles"""
    with open(json_path) as f:
        config = json.load(f)
    
    fig, axes = plt.subplots(2, 3, subplot_kw=dict(projection='polar'), figsize=(15, 10))
    axes = axes.flatten()
    
    for i in range(5):
        profile = config[f"plantProfile_{i+1}"]["value"]
        angles = np.linspace(0, 2*np.pi, len(profile))
        
        axes[i].plot(angles, profile, linewidth=2)
        axes[i].fill(angles, profile, alpha=0.3)
        axes[i].set_ylim(0.7, 1.05)
        axes[i].set_title(f"Profile {i+1}")
        axes[i].set_theta_zero_location('N')
    
    axes[5].axis('off')  # Hide 6th subplot
    
    plt.tight_layout()
    plt.savefig("all_profiles_comparison.png", dpi=150, bbox_inches='tight')
    plt.show()

# Usage
visualize_profile("data/assets/pve_configs/european_beech_pve.json", "plantProfile_1")
visualize_all_profiles("data/assets/pve_configs/european_beech_pve.json")
```

## Validation Checklist

Before using profiles in Unreal, verify:

- [ ] Exactly 100 values in each profile array
- [ ] First value equals last value (cyclic boundary)
- [ ] Values in range 0.5-1.2 (typically 0.75-1.0)
- [ ] All 5 profiles present (`plantProfile_1` through `plantProfile_5`)
- [ ] No NaN or infinite values
- [ ] Smooth transitions (no sharp spikes)
- [ ] Profiles differ from each other (provide variation)
- [ ] Biologically plausible for species (realistic crown shape)

**Quick validation script:**

```python
import json
import numpy as np

def validate_profiles(json_path):
    """Validate plantProfile arrays"""
    with open(json_path) as f:
        config = json.load(f)
    
    issues = []
    
    for i in range(1, 6):
        profile_name = f"plantProfile_{i}"
        
        if profile_name not in config:
            issues.append(f"Missing {profile_name}")
            continue
        
        values = config[profile_name]["value"]
        
        # Check length
        if len(values) != 100:
            issues.append(f"{profile_name}: Wrong length ({len(values)}, expected 100)")
        
        # Check cyclic
        if abs(values[0] - values[-1]) > 1e-6:
            issues.append(f"{profile_name}: Not cyclic (first={values[0]:.4f}, last={values[-1]:.4f})")
        
        # Check range
        min_val, max_val = min(values), max(values)
        if min_val < 0.5 or max_val > 1.2:
            issues.append(f"{profile_name}: Values out of range ({min_val:.2f} - {max_val:.2f})")
        
        # Check for NaN/inf
        if any(not np.isfinite(v) for v in values):
            issues.append(f"{profile_name}: Contains NaN or infinite values")
    
    if issues:
        print("Validation FAILED:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("Validation PASSED: All profiles are valid")
        return True

# Usage
validate_profiles("data/assets/pve_configs/european_beech_pve.json")
```

## Common Issues and Solutions

### Profile Too Uniform (Looks Artificial)

**Problem**: All values close to 1.0, crown looks like perfect circle

**Solution**: Increase irregularity

```python
# Add more variation
profile = [max(0.75, v * np.random.uniform(0.85, 1.0)) for v in profile]
```

### Profile Too Irregular (Looks Unnatural)

**Problem**: Sharp spikes, unrealistic jagged outline

**Solution**: Apply smoothing

```python
from scipy.ndimage import gaussian_filter1d
profile = gaussian_filter1d(profile, sigma=2.0, mode='wrap')
```

### Profiles Too Similar (No Variation)

**Problem**: All 5 profiles look the same

**Solution**: Use different seeds or parameters

```python
for i in range(5):
    profiles[f"plantProfile_{i+1}"] = generate_profile(
        num_major_branches=np.random.randint(10, 16),
        irregularity=np.random.uniform(0.12, 0.18),
        seed=42 + i
    )
```

### Import Fails in Unreal

**Problem**: JSON imports but profiles don't apply

**Solution**: Enable PVE Debug Mode

```text
# In Unreal Editor console
PV.DebugMode.Enabled 1
```

## Example Profiles

### Realistic Oak Profile

```python
# Oak: Broad, spreading crown with irregular outline
oak_profile = generate_broadleaf_profile(
    num_major_branches=14,  # Many major branches
    irregularity=0.18,      # High variation
    seed=123
)
```

### Realistic Pine Profile

```python
# Pine: Conical, more uniform crown
pine_profile = generate_coniferous_profile(
    num_whorls=5,           # Typical for mature pine
    irregularity=0.08,      # Low variation
    seed=456
)
```

### Realistic Beech Profile

```python
# Beech: Dense, dome-shaped crown
beech_profile = generate_broadleaf_profile(
    num_major_branches=12,
    irregularity=0.14,      # Moderate variation
    seed=789
)
```

## Integration with GrowPy

GrowPy's PVE export system uses species-specific config files in `data/assets/pve_configs/`:

```bash
# 1. Create or generate profiles
python -c "
from generate_profiles import generate_species_profiles
generate_species_profiles('broadleaf', 'data/assets/pve_configs/european_oak_pve.json')
"

# 2. Generate forest with PVE presets
python src/growpy/cli/generate_forest.py --generate-pve-json --quality high

# 3. Profiles automatically applied to exported JSON files
```

Config file structure:

```json
{
  "plantProfile_1": {"isArray": true, "size": 1, "type": "float", "value": [...]},
  "plantProfile_2": {"isArray": true, "size": 1, "type": "float", "value": [...]},
  "plantProfile_3": {"isArray": true, "size": 1, "type": "float", "value": [...]},
  "plantProfile_4": {"isArray": true, "size": 1, "type": "float", "value": [...]},
  "plantProfile_5": {"isArray": true, "size": 1, "type": "float", "value": [...]},
  "maxBranchNumber": {"isArray": false, "size": 1, "type": "int", "value": 120},
  "maxBudNumber": {"isArray": false, "size": 1, "type": "int", "value": 800},
  ...
}
```

## Further Reading

- [PVE Preset Workflow](PVE_PRESET_WORKFLOW.md) - Complete import guide
- [PVE Implementation Summary](PVE_IMPLEMENTATION_SUMMARY.md) - Technical details
- Grove 2.2 Documentation - Botanical simulation parameters
- Quixel Megaplants - Reference PVE presets

## Quick Reference Card

```text
PlantProfile Quick Facts:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Number Required:    5 (plantProfile_1 to plantProfile_5)
Array Length:       100 values (exactly)
Angular Resolution: 3.6° per sample (360° / 100)
Value Range:        0.75 - 1.0 (normalized radii)
Cyclic:            first value = last value
Purpose:           Radial crown envelope (top-down view)

Broadleaf Trees:
  • Major branches: 10-15
  • Value range: 0.80-1.0
  • Irregularity: High (0.15-0.20)
  
Coniferous Trees:
  • Branch whorls: 3-5
  • Value range: 0.90-1.0
  • Irregularity: Low (0.05-0.10)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
