# The Grove 2.2 Preset Settings Reference

This document provides a comprehensive reference for all preset parameters used in The Grove 2.2 tree generation system. These parameters are stored in `.seed.json` files and define the natural growth characteristics of different tree species.

## Overview

Grove presets contain approximately 60 parameters organized into functional groups that control:

- Branch addition and structure
- Growth behavior and dimensions
- Environmental responses (light, shade)
- Physical properties (bending, thickness)
- Automatic pruning
- Twig placement

The same preset files work across The Grove in Blender, Houdini, and the standalone Python API.

---

## Parameter Groups

### 1. Branch Addition (add_*)

These parameters control how new branches are added to the tree structure.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `add_angle` | float | 0.0-1.5 | Angle of new branches from parent (in radians). Higher values create wider branching angles. |
| `add_bud_life` | int | 1+ | Number of years a bud remains viable before dying. |
| `add_chance` | float | 0.0-1.0 | Probability of adding a new branch at each growth point. |
| `add_chance_reduce` | float | 0.0-1.0 | Rate at which branch addition probability decreases over time. |
| `add_fork` | float | 0.0-1.0 | Probability of creating a fork (two equal branches) instead of a single continuation. |
| `add_horizontal` | float | 0.0-1.0 | Tendency for new branches to grow horizontally. |
| `add_only_on_end` | float | 0.0-1.0 | Preference for adding branches only at branch tips (monopodial growth pattern). |
| `add_regenerate` | float | 0.0-1.0 | Ability of the tree to regenerate new branches from dormant buds. |
| `add_side_branches` | int | 1-5 | Number of side branches added per growth flush. |
| `add_twist` | float | 0.0-0.5 | Amount of spiral twist in branch placement (radians). |
| `add_up` | float | -0.5-0.5 | Vertical bias for new branch direction. Negative values point downward. |

#### Species Highlights - Branch Addition

| Species | Notable Value | Effect |
|---------|--------------|--------|
| **Conifers (Pine, Spruce)** | `add_side_branches: 3-5`, `add_only_on_end: 1.0` | Creates whorled branching pattern typical of conifers |
| **European Oak** | `add_fork: 0.5` | High forking creates characteristic massive crown structure |
| **Umbrella Acacia** | `add_fork: 1.0`, `turn_to_horizon: 1.0` | Creates flat-topped umbrella crown |
| **Weeping Willow** | `grow_nodes: 7`, `add_chance: 0.64` | Long flowing branches |
| **Italian Poplar** | `add_regenerate: 1.0`, `add_up: 0.3` | Strong vertical growth, excellent regeneration |
| **Norway Spruce** | `add_horizontal: 0.87`, `add_up: -0.2` | Layered horizontal branches drooping slightly |

---

### 2. Growth Parameters (grow_*)

Control the fundamental growth dimensions and rates.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `grow_length` | float | 0.2-1.0 | Length of each growth segment (meters at scale 1.0). |
| `grow_length_reduce` | float | 0.0-1.0 | Rate at which growth length decreases on sub-branches. |
| `grow_nodes` | int | 3-7 | Number of nodes (growth points) added per growing season. |

#### Species Highlights - Growth

| Species | grow_length | grow_nodes | Effect |
|---------|-------------|------------|--------|
| **Weeping Willow** | 0.8 | 7 | Very long, rapid growth for flowing form |
| **Sycamore Maple** | 0.6 | 4 | Vigorous deciduous growth |
| **European Beech** | 0.3 | 4 | Slower, compact growth |
| **Scots Pine** | 0.35 | 3 | Moderate conifer growth |
| **Japanese Maple** | 0.3 | 3 | Compact ornamental form |

---

### 3. Turning Behavior (turn_*)

Control how branches change direction as they grow.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `turn_to_light` | float | 0.0-1.0 | Strength of phototropism (growing toward light). |
| `turn_up` | float | 0.0-1.0 | Tendency to turn upward (negative geotropism). |
| `turn_up_in_shade` | float | 0.0-1.0 | Increased upward turning when shaded. |
| `turn_to_horizon` | float | 0.0-1.0 | Tendency to grow horizontally. |
| `turn_random` | float | 0.0-0.5 | Random deviation in growth direction (radians). |

#### Species Highlights - Turning

| Species | Notable Value | Effect |
|---------|--------------|--------|
| **Umbrella Acacia** | `turn_to_horizon: 1.0` | Creates flat-topped canopy |
| **Common Ash** | `turn_up: 0.6`, `turn_up_in_shade: 0.6` | Strong vertical orientation |
| **Hornbeam** | `turn_to_light: 1.0`, `turn_up: 0.3` | Responsive to light, upward growth |
| **Japanese Cherry** | `turn_to_light: 0.75` | Graceful light-seeking growth |
| **European Oak** | `turn_random: 0.28` | More irregular, natural appearance |
| **Japanese Maple** | `turn_to_horizon: 0.3` | Creates horizontal layered form |

---

### 4. Favor Parameters (favor_*)

Control growth distribution and resource allocation among branches.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `favor_bright` | float | 0.0-1.0 | Preference for allocating resources to well-lit branches. |
| `favor_end` | float | 0.0-1.0 | Apical dominance strength - preference for terminal growth. |
| `favor_end_reduce` | float | 0.0-1.0 | Rate at which apical dominance decreases with age. |
| `favor_rising` | float | 0.0-1.0 | Preference for upward-growing branches. |

#### Species Highlights - Favor

| Species | favor_bright | favor_end | Effect |
|---------|-------------|-----------|--------|
| **Scots Pine** | 0.87 | 0.0 | Strong light competition, no apical dominance |
| **Ginkgo** | 0.75 | 0.8 | Strong apical dominance, unique growth |
| **European Oak** | 0.65 | 0.0 | Light-seeking, no strong leader |
| **Japanese Cherry** | 0.7 | 0.6 | Moderate apical dominance, graceful |
| **Hornbeam** | 0.55 | 0.4 | Moderate light response, tapering apical |

---

### 5. Shade Parameters (shade_*)

Control how the tree responds to and creates shade.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `shade_area` | float | 2.0-10.0 | Size of the shade cast by each leaf cluster. |
| `shade_area_depth` | float | 0.0-1.0 | How much shade penetrates into the canopy. |
| `shade_area_reduce` | float | 0.0-1.0 | Reduction of shade area over time. |
| `shade_avoidance` | float | 0.0-1.0 | Tendency to grow away from shaded areas. |
| `shade_branches` | bool | true/false | Whether branches (not just leaves) cast shade. |
| `shade_leaf_sides` | bool | true/false | Whether leaves cast shade on both sides. |
| `shade_alongside` | int | 0-5 | Number of neighboring branches considered for shading. |
| `shade_alongside_diameter` | float | 0.0-0.5 | Diameter threshold for alongside shading. |

#### Species Highlights - Shade

| Species | shade_area | Notable Settings | Effect |
|---------|-----------|------------------|--------|
| **European Oak** | 10.0 | Dense crown shading | Large, shade-producing crown |
| **Scots Pine** | 2.0 | `shade_branches: true`, `shade_alongside: 3` | Conifer needle shading pattern |
| **Weeping Willow** | 2.0 | `shade_branches: true`, `shade_leaf_sides: true` | Dense cascading shade |
| **European Beech** | 8.0 | Heavy crown shading | Shade-tolerant understory killer |
| **Silver Birch** | 8.0 | `shade_area_depth: 0.4` | Light, dappled shade |

---

### 6. Branch Dropping (drop_*)

Control when branches are shed or die.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `drop_decay` | float | 0.0-1.0 | Rate at which dead branches decay and fall off. |
| `drop_obsolete` | float | 0.0-1.0 | Rate of dropping branches that no longer contribute. |
| `drop_shaded` | float | 0.0-1.0 | Rate of dropping heavily shaded branches. |
| `drop_weak` | float | 0.0-1.0 | Rate of dropping weak or thin branches. |

#### Species Highlights - Dropping

| Species | drop_weak | drop_decay | Effect |
|---------|-----------|------------|--------|
| **Silver Birch** | 0.5 | 0.6 | Aggressive self-pruning, clean trunk |
| **European Oak** | 0.3 | 1.0 | Retains branches, fast decay |
| **Umbrella Acacia** | 0.6 | 0.6 | Maintains clean umbrella form |
| **Japanese Maple** | 0.61 | 0.8 | Maintains delicate structure |
| **Scots Pine** | 0.3 | 0.3 | Slow decay, retains dead branches |

---

### 7. Bending Physics (bend_*)

Control how branches bend under their own weight and external forces.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `bend_mass` | float | 0.0-2.0 | Mass factor for branch bending calculations. |
| `bend_reaction` | float | 0.0-1.0 | Branch reaction wood formation - straightening response. |
| `bend_twig_mass` | float | 0.0-1.0 | Mass contribution of twigs to bending. |
| `bend_twig_mass_solidify` | float | 0.0-1.0 | How quickly twig mass becomes rigid. |
| `bend_fatigue` | float | 0.0-1.0 | Cumulative weakening from repeated bending. |

#### Species Highlights - Bending

| Species | bend_mass | bend_reaction | Effect |
|---------|-----------|---------------|--------|
| **Silver Birch** | 1.3 | 0.28 | Graceful drooping, moderate correction |
| **Weeping Willow** | 1.0 | 0.0 | Extreme drooping, no correction |
| **Scots Pine** | 1.0 | 0.4 | Strong branch correction |
| **European Oak** | 0.7 | 0.0 | Heavy but stiff branches |
| **Japanese Maple** | 0.5 | 0.075 | Light, elegant drooping |

---

### 8. Thickening Parameters (thicken_*)

Control how branches increase in diameter over time.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `thicken_tips` | float | 0.003-0.01 | Initial diameter of new growth tips (meters). |
| `thicken_tips_reduce` | float | 0.0-1.0 | Rate at which tip thickness reduces on sub-branches. |
| `thicken_join` | float | 0.7-1.0 | Smoothness of diameter transition at branch junctions. |
| `thicken_deadwood` | float | 0.0-0.5 | Continued thickening rate of dead branches. |
| `thicken_base_scale` | float | 1.0-1.5 | Scale factor for trunk base flare. |
| `thicken_base_buttress` | float | 0.0-3.0 | Prominence of buttress roots at base. |
| `thicken_base_shape` | float | 0.0-0.5 | Shape of the base flare curve. |

#### Species Highlights - Thickening

| Species | thicken_tips | thicken_base_buttress | Effect |
|---------|--------------|----------------------|--------|
| **European Oak** | 0.006 | 0.0 | Thick tips, clean base |
| **Ash** | 0.008 | 2.0 | Thick growth, prominent buttress |
| **Beech** | 0.004 | 2.0 | Fine tips, elephant-foot base |
| **Hornbeam** | 0.003 | 1.0 | Very fine, delicate structure |
| **Italian Poplar** | 0.007 | 0.0 | Moderate, clean columnar form |

---

### 9. Auto Pruning (auto_prune_*)

Control automatic branch removal during simulation.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `auto_prune_enabled` | bool | true/false | Enable automatic pruning. |
| `auto_prune_low` | float | 0.0-5.0 | Height below which branches are pruned (meters). |
| `auto_prune_keep_thick` | float | 0.01-0.2 | Minimum diameter to retain branches (meters). |
| `auto_prune_dangling` | float | 0.5-3.0 | Length of thin dangling branches to remove. |

#### Species Highlights - Auto Pruning

| Species | auto_prune_low | auto_prune_keep_thick | Effect |
|---------|----------------|----------------------|--------|
| **Ash** | 5.0 | 0.08 | High crown, clean trunk |
| **European Beech** | 3.0 | 0.02 | Moderate crown height |
| **European Oak** | 2.0 | 0.2 | Low branches retained |
| **Norway Spruce** | 0.5 | 0.01 | Branches nearly to ground |
| **Sycamore Maple** | 3.5 | 0.05 | Clean lower trunk |

---

### 10. Surround Environment (surround_*)

Control interaction with surrounding trees (competition simulation).

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `surround_enabled` | bool | true/false | Enable surrounding tree simulation. |
| `surround_density` | float | 0.0-1.0 | Density of surrounding trees. |
| `surround_distance` | float | 4.0-10.0 | Distance to surrounding trees (meters). |
| `surround_height` | float | 5.0-10.0 | Height of surrounding trees (meters). |
| `surround_grow` | bool | true/false | Whether surrounding trees grow with the main tree. |

#### Species Highlights - Surround

| Species | surround_enabled | surround_distance | Effect |
|---------|-----------------|-------------------|--------|
| **Scots Pine** | true | 10.0 | Forest form with crown lifting |
| **Norway Spruce** | true | 9.5 | Tight forest spacing |
| **European Oak** | false | 4.0 | Open-grown by default |
| **Silver Birch** | false | 10.0 | Pioneer species form |

---

### 11. Twig Placement (twig_*)

Control leaf/needle cluster placement.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `twig_density` | float | 0.0-1.0 | Density of twig placement on branches. |
| `twig_longevity` | int | 2-8 | Years twigs remain on the tree. |

#### Species Highlights - Twigs

| Species | twig_density | twig_longevity | Effect |
|---------|-------------|----------------|--------|
| **Ginkgo** | 1.0 | 8 | Long-lived unique leaves |
| **European Oak** | 0.5 | 3 | Moderate density |
| **Ash** | 1.0 | 2 | Dense but short-lived |
| **Weeping Willow** | 1.0 | 3 | Dense flowing leaves |

---

## Species Comparison Table

### Deciduous Broadleaves

| Parameter | European Oak | European Beech | Silver Birch | Sycamore Maple |
|-----------|-------------|----------------|--------------|----------------|
| `grow_length` | 0.5 | 0.3 | 0.4 | 0.6 |
| `grow_nodes` | 4 | 4 | 4 | 4 |
| `add_fork` | 0.5 | 0.0 | 0.1 | 0.098 |
| `favor_bright` | 0.65 | 0.48 | 0.75 | 0.8 |
| `favor_end` | 0.0 | 0.3 | 0.2 | 0.0 |
| `bend_mass` | 0.7 | 1.0 | 1.3 | 0.5 |
| `turn_random` | 0.28 | 0.14 | 0.087 | 0.087 |
| `add_regenerate` | 0.3 | 0.2 | 0.9 | 0.7 |

### Conifers

| Parameter | Scots Pine | Norway Spruce | Silver Fir |
|-----------|-----------|---------------|------------|
| `add_side_branches` | 3 | 5 | 5 |
| `add_only_on_end` | 1.0 | 1.0 | 1.0 |
| `add_horizontal` | 0.7 | 0.87 | 0.87 |
| `add_up` | 0.0 | -0.2 | -0.2 |
| `shade_branches` | true | false | false |
| `surround_enabled` | true | true | true |
| `favor_bright` | 0.87 | 0.8 | 0.72 |

### Special Forms

| Parameter | Weeping Willow | Umbrella Acacia | Italian Poplar | Japanese Maple |
|-----------|---------------|-----------------|----------------|----------------|
| `grow_length` | 0.8 | 0.4 | 0.6 | 0.3 |
| `grow_nodes` | 7 | 4 | 5 | 3 |
| `add_fork` | 0.1 | 1.0 | 0.17 | 0.5 |
| `turn_to_horizon` | 0.0 | 1.0 | 0.0 | 0.3 |
| `bend_mass` | 1.0 | 1.0 | 0.2 | 0.5 |
| `add_regenerate` | 0.2 | 0.44 | 1.0 | 0.3 |

---

## Key Differentiating Parameters

Understanding which parameters create the most visual impact helps in customizing presets:

### For Crown Shape

- **Columnar**: High `add_up`, low `add_fork`, high `favor_end`
- **Spreading**: High `add_horizontal`, high `add_fork`, low `favor_end`
- **Weeping**: High `bend_mass`, low `bend_reaction`, high `grow_length`
- **Conical**: `add_only_on_end: 1.0`, regular `add_side_branches`

### For Trunk Character

- **Clean**: High `auto_prune_low`, low `add_regenerate`
- **Buttressed**: High `thicken_base_buttress`
- **Forked**: High `add_fork` combined with low `favor_end`

### For Branch Density

- **Dense**: High `add_chance`, high `add_regenerate`, low `drop_weak`
- **Open**: Low `add_chance`, high `drop_weak`, high `drop_shaded`

### For Conifer vs Deciduous

- **Conifers**: `add_only_on_end: 1.0`, `shade_branches: true`, multiple `add_side_branches`
- **Deciduous**: `add_only_on_end: 0.0`, varied `add_fork`, single `add_side_branches`

---

## Common Default Values

Many parameters share common defaults across most species:

| Parameter | Common Default | Notes |
|-----------|---------------|-------|
| `simulation_scale` | 1.0 | Scale multiplier |
| `grow_length_reduce` | 0.78 | Nearly universal |
| `add_bud_life` | 1 | Single year viability |
| `shade_alongside_diameter` | 0.2 | Standard threshold |
| `shade_area_reduce` | 0.0 | No reduction |
| `shade_avoidance` | 0.0 | Disabled by default |
| `favor_rising` | 0.0 | Not commonly used |
| `thicken_base_scale` | 1.2 | Standard flare |
| `surround_height` | 5.0 | Standard competition height |
| `surround_density` | 0.7 | Standard density |
| `bend_twig_mass_solidify` | 1.0 | Full solidification |
| `drop_obsolete` | 0.0 | Not commonly used |

---

## Usage in Python

```python
from growpy.utils.dependencies import gc
import json

# Load a preset
with open('data/assets/presets/european_oak.seed.json', 'r') as f:
    preset = json.load(f)

# Create a grove and apply preset
grove = gc.Grove()
props = grove.get_properties()

for key, value in preset.items():
    try:
        setattr(props, key, value)
    except (TypeError, AttributeError):
        pass

grove.set_properties(props)

# Simulate growth
grove.simulate(flushes=15)
```

---

## Notes on Units

- **Angles**: Specified in radians (1.0 rad ≈ 57 degrees)
- **Lengths**: Specified in meters at `simulation_scale: 1.0`
- **Time**: Growth flushes represent growing seasons (typically 1 year each)

---

## References

- The Grove 2.2 Python API Documentation
- The Grove Blender Add-on Properties System
- The Grove Houdini Digital Asset Documentation
