# Tree Asset Dataset Specification

## Overview

This document defines the target tree asset dataset for a VR forest simulation in Unreal Engine 5. Assets are produced using GrowPy with The Grove 2.3, exported as USD with Nanite-ready meshes and skeletal animation support.

**Purpose**: Systematically cover the most common tree species of southern Germany (Bavaria, Baden-Wuerttemberg) with multiple growth stages, competition variants, and foliage density levels per species.

**Target engine**: Unreal Engine 5.5+ with Nanite and Procedural Vegetation Editor (PVE).

**Estimated total models**: ~576 (16 species x 2 individuals x ~6 stages x 3 densities).

## Species Selection

### Methodology

Species are selected based on the German National Forest Inventory (Bundeswaldinventur, BWI) frequency data for southern Germany. The selection prioritizes:

1. **Area share**: Species covering the largest forest area in Bavaria and Baden-Wuerttemberg
2. **Ecological importance**: Species significant for forest ecology even if area share is small
3. **Preset availability**: Species must have a Grove 2.3 preset (or be marked for custom preset creation)

### Species Table

#### Conifers (6 species)

| # | Common Name | Scientific Name | BWI Share | Standardized Name | Preset | Twig | Yield Table | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Norway spruce | Picea abies | ~34% | `norway_spruce` | Pinaceae - Fir | PacificSilverFirTwig | Fichte | Dominant conifer in southern Germany |
| 2 | Scots pine | Pinus sylvestris | ~15% | `scots_pine` | Pinaceae - Scots pine | ScotsPineTwig | Kiefer | Second most common conifer |
| 3 | Silver fir | Abies alba | ~3% | `silver_fir` | Pinaceae - Fir | PacificSilverFirTwig | Tanne | Key species in Black Forest, Allgaeu |
| 4 | Austrian pine | Pinus nigra | <1% | `austrian_pine` | Pinaceae - Austrian pine | ScotsPineTwig | Schwarzkiefer | Planted, dry limestone sites |
| 5 | Grand fir | Abies grandis | <1% | `grand_fir` | Pinaceae - Grand fir | PacificSilverFirTwig | -- | Serves as Douglas fir stand-in |
| 6 | Western redcedar | Thuja plicata | <1% | `western_redcedar` | Cupressaceae - Western redcedar | WesternRedCedarTwig | -- | Distinct silhouette, evergreen alternative |

#### Broadleaf (10 species)

| # | Common Name | Scientific Name | BWI Share | Standardized Name | Preset | Twig | Yield Table | Notes |
|---|---|---|---|---|---|---|---|---|
| 7 | European beech | Fagus sylvatica | ~14% | `european_beech` | Fagaceae - Beech | EuropeanBeechTwig | Buche | Dominant broadleaf |
| 8 | European oak | Quercus robur | ~7% | `european_oak` | Fagaceae - European oak | EuropeanOakTwig | Eiche | Major component of mixed forests |
| 9 | Common ash | Fraxinus excelsior | ~3% | `common_ash` | Oleaceae - Ash | OneLeavedAshTwig | Esche | Declining due to ash dieback |
| 10 | Sycamore maple | Acer pseudoplatanus | ~2% | `sycamore_maple` | Sapindaceae - Maple | SycamoreMapleFallTwig | -- | Common in montane forests |
| 11 | Silver birch | Betula pendula | ~2% | `silver_birch` | Betulaceae - Silver birch | PaperBirchTwig | Birke | Pioneer species, distinctive bark |
| 12 | Black alder | Alnus glutinosa | ~2% | `black_alder` | Betulaceae - Alder | BlackAlderTwig | Erle | Riparian habitat indicator |
| 13 | Hornbeam | Carpinus betulus | ~1% | `hornbeam` | Betulaceae - Hornbeam | HazelTwig | Hainbuche | Common understory tree |
| 14 | Small-leaved linden | Tilia cordata | ~1% | `small_leaved_linden` | Malvaceae - Linden | SmallLeavedLindenTwig | Winterlinde | Cultural significance |
| 15 | Wild cherry | Prunus avium | <1% | `wild_cherry` | Rosaceae - Wild cherry | JapaneseCherryTwig | -- | Valuable timber species |
| 16 | Field maple | Acer campestre | <1% | `field_maple` | Sapindaceae - Field maple | FieldMapleTwig | -- | Hedgerows, forest edges |

### Gap Analysis

The following species are common in southern German forests but lack Grove presets. They are planned for future custom preset and twig development:

| Common Name | Scientific Name | BWI Share | Status |
|---|---|---|---|
| European larch | Larix decidua | ~2% | Needs custom preset and twig |
| Douglas fir | Pseudotsuga menziesii | ~2% | Needs custom preset and twig; Grand fir used as stand-in for now |
| Robinia | Robinia pseudoacacia | <1% | preset exists but low priority for southern Germany |

## Asset Hierarchy

Each tree asset is defined by four orthogonal dimensions:

```
Species (16)
  |
  +-- Individual (2+)
        |
        +-- Growth Stage (~6)
              |
              +-- Density Variant (3)
```

### Level 1: Species

The 16 species listed above. Each species has its own Grove preset, twig set, bark textures, and growth model (calibrated against yield tables where available).

### Level 2: Individual

Each species has at minimum two individuals representing different growing conditions:

| Individual | Description | CSV Setup | Export |
|---|---|---|---|
| `open_grown` | Single tree, no neighbors. Wide crown, heavy branching, short trunk. | 1 tree at origin | Export all |
| `competition` | Center tree surrounded by 6 same-species neighbors in hexagonal pattern. Narrow crown, tall clear trunk, suppressed lower branches. | 7 trees, center + 6 neighbors | Export center only (`export_trees = [1]`) |

**Competition spacing** varies by species shade tolerance:

| Shade Tolerance | Spacing (m) | Species |
|---|---|---|
| Tolerant | 5 | European beech, hornbeam, silver fir, small-leaved linden, western redcedar |
| Intermediate | 6 | European oak, sycamore maple, common ash, wild cherry, field maple, Norway spruce, grand fir |
| Intolerant | 8 | Scots pine, Austrian pine, silver birch, black alder |

**Hexagonal neighbor positions** at spacing `s`:

| FID | x | y | Role |
|---|---|---|---|
| 1 | 0 | 0 | Center (exported) |
| 101 | s | 0 | Neighbor |
| 102 | -s | 0 | Neighbor |
| 103 | s/2 | s * 0.866 | Neighbor |
| 104 | -s/2 | s * 0.866 | Neighbor |
| 105 | s/2 | -s * 0.866 | Neighbor |
| 106 | -s/2 | -s * 0.866 | Neighbor |

### Level 3: Growth Stage

Each individual is exported at multiple heights using multi-stage export (`cycle_interval` in growpy.toml).

**Height-based increments** (preferred over age-based):

| Species Group | Height Range | Increment | Stages |
|---|---|---|---|
| Tall conifers (spruce, fir, pine) | 5 m -- 35 m | 5 m | 7 |
| Medium conifers (Austrian pine, redcedar) | 5 m -- 25 m | 5 m | 5 |
| Tall broadleaf (beech, oak, ash) | 5 m -- 30 m | 5 m | 6 |
| Medium broadleaf (maple, birch, linden) | 5 m -- 25 m | 5 m | 5 |
| Small broadleaf (hornbeam, cherry, field maple) | 5 m -- 20 m | 5 m | 4 |

The target height in the input CSV is set to the species maximum. Multi-stage export produces snapshots at the cycle intervals corresponding to each height milestone.

### Level 4: Density Variant

Each growth stage is exported with three foliage density levels, controlled by the `twig_density` CSV column:

| Variant | `twig_density` | Description | Use Case |
|---|---|---|---|
| `full` | 1.0 | All twigs and foliage attached | Healthy tree in full leaf |
| `reduced` | 0.5 | 50% of twigs removed | Stressed tree, partial defoliation |
| `bare` | 0.0 | No twigs, branch structure only | Dead tree, winter deciduous, or LOD |

Seasonal leaf color (spring green, summer, autumn, winter) is handled at runtime in Unreal Engine via material parameter changes, not via separate asset variants.

## Asset Count Estimate

| Species Group | Species | Individuals | Stages | Densities | Subtotal |
|---|---|---|---|---|---|
| Tall conifers | 3 | 2 | 7 | 3 | 126 |
| Medium conifers | 3 | 2 | 5 | 3 | 90 |
| Tall broadleaf | 3 | 2 | 6 | 3 | 108 |
| Medium broadleaf | 4 | 2 | 5 | 3 | 120 |
| Small broadleaf | 3 | 2 | 4 | 3 | 72 |
| **Total** | **16** | | | | **516** |

## Naming Convention

### Directory Structure

```
data/output/dataset/
+-- {species_standardized}/
    +-- {individual_type}/
        +-- {species_clean}_{individual}_{height}_{dbh}_{density}_assembly.usda
        +-- {species_clean}_{individual}_{height}_{dbh}_{density}_stems_skeletal.usda
        +-- {species_clean}_{individual}_{height}_{dbh}_{density}_preview.png
        +-- textures/
```

Example:

```
data/output/dataset/
+-- european_beech/
|   +-- open_grown/
|   |   +-- European_beech_open_h05m_d03cm_full_assembly.usda
|   |   +-- European_beech_open_h05m_d03cm_full_preview.png
|   |   +-- European_beech_open_h10m_d08cm_full_assembly.usda
|   |   +-- European_beech_open_h10m_d08cm_reduced_assembly.usda
|   |   +-- European_beech_open_h10m_d08cm_bare_assembly.usda
|   |   +-- ...
|   +-- competition/
|       +-- European_beech_comp_h05m_d03cm_full_assembly.usda
|       +-- European_beech_comp_h10m_d06cm_full_assembly.usda
|       +-- ...
+-- norway_spruce/
    +-- open_grown/
    +-- competition/
```

### Filename Components

| Component | Format | Example |
|---|---|---|
| Species clean | Title_case_underscored | `European_beech` |
| Individual | `open` or `comp` | `open`, `comp` |
| Height | `h{NN}m` | `h15m` |
| DBH | `d{NN}cm` | `d10cm` |
| Density | `full`, `reduced`, `bare` | `full` |
| Asset type | `assembly`, `stems_skeletal`, `preview` | `assembly` |

## Production Pipeline

### Prerequisites

1. Run steps 1--3 of the GrowPy pipeline for all 16 species:

   ```
   python src/growpy/cli/prepare_assets.py --csv data/input/dataset/all_species.csv
   python src/growpy/cli/convert_twigs.py
   python src/growpy/cli/create_growth_models.py --csv data/input/dataset/all_species.csv
   ```

2. Verify growth models and yield table calibration exist for each species.

### Production Workflow Per Species

For each species, two export runs are needed (open_grown + competition):

**Step 1: Open-grown individual**

```
python src/growpy/cli/generate_forest.py \
    --csv data/input/dataset/{species}_open.csv \
    --output data/output/dataset/{species}/open_grown \
    --cycle-interval 25 \
    --quality high
```

**Step 2: Competition individual**

```
python src/growpy/cli/generate_forest.py \
    --csv data/input/dataset/{species}_competition.csv \
    --output data/output/dataset/{species}/competition \
    --cycle-interval 25 \
    --quality high \
    --export-trees 1
```

**Step 3: Density variants**

Re-run steps 1--2 with `twig_density` set to 0.5 and 0.0 in the CSV, or implement a post-processing step that re-exports twig placements at different densities from the same growth simulation.

### CSV Input Templates

Templates are stored in `data/input/dataset/`. Each species has two CSVs:

**`{species}_open.csv`** -- single tree, open-grown:

```csv
fid,species,x,y,z,height,twig_density
1,{Common Name},0,0,0,{max_height},1.0
```

**`{species}_competition.csv`** -- center tree + 6 neighbors:

```csv
fid,species,x,y,z,height,twig_density
1,{Common Name},0,0,0,{max_height},1.0
101,{Common Name},{s},0,0,{max_height},1.0
102,{Common Name},{-s},0,0,{max_height},1.0
103,{Common Name},{s/2},{s*0.866},0,{max_height},1.0
104,{Common Name},{-s/2},{s*0.866},0,{max_height},1.0
105,{Common Name},{s/2},{-s*0.866},0,{max_height},1.0
106,{Common Name},{-s/2},{-s*0.866},0,{max_height},1.0
```

## Species Catalog

Each species section below contains a properties summary and a preview image grid. During production, preview images are inserted into the grid as they are exported. The production status checkboxes track completion.

---

### 1. Norway Spruce (Picea abies)

| Property | Value |
|---|---|
| Standardized name | `norway_spruce` |
| BWI share | ~34% |
| Max height | 35 m |
| Growth stages | 5, 10, 15, 20, 25, 30, 35 m |
| Preset | Pinaceae - Fir |
| Twig | PacificSilverFirTwig |
| Yield table | Fichte |
| Competition spacing | 6 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |
| 30 m | <!-- open_h30m --> | <!-- comp_h30m --> |
| 35 m | <!-- open_h35m --> | <!-- comp_h35m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 2. Scots Pine (Pinus sylvestris)

| Property | Value |
|---|---|
| Standardized name | `scots_pine` |
| BWI share | ~15% |
| Max height | 30 m |
| Growth stages | 5, 10, 15, 20, 25, 30 m |
| Preset | Pinaceae - Scots pine |
| Twig | ScotsPineTwig |
| Yield table | Kiefer |
| Competition spacing | 8 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |
| 30 m | <!-- open_h30m --> | <!-- comp_h30m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 3. Silver Fir (Abies alba)

| Property | Value |
|---|---|
| Standardized name | `silver_fir` |
| BWI share | ~3% |
| Max height | 35 m |
| Growth stages | 5, 10, 15, 20, 25, 30, 35 m |
| Preset | Pinaceae - Fir |
| Twig | PacificSilverFirTwig |
| Yield table | Tanne |
| Competition spacing | 5 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |
| 30 m | <!-- open_h30m --> | <!-- comp_h30m --> |
| 35 m | <!-- open_h35m --> | <!-- comp_h35m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 4. Austrian Pine (Pinus nigra)

| Property | Value |
|---|---|
| Standardized name | `austrian_pine` |
| BWI share | <1% |
| Max height | 25 m |
| Growth stages | 5, 10, 15, 20, 25 m |
| Preset | Pinaceae - Austrian pine |
| Twig | ScotsPineTwig |
| Yield table | Schwarzkiefer |
| Competition spacing | 8 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 5. Grand Fir (Abies grandis)

| Property | Value |
|---|---|
| Standardized name | `grand_fir` |
| BWI share | <1% |
| Max height | 35 m |
| Growth stages | 5, 10, 15, 20, 25, 30, 35 m |
| Preset | Pinaceae - Grand fir |
| Twig | PacificSilverFirTwig |
| Yield table | -- |
| Competition spacing | 6 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |
| 30 m | <!-- open_h30m --> | <!-- comp_h30m --> |
| 35 m | <!-- open_h35m --> | <!-- comp_h35m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 6. Western Redcedar (Thuja plicata)

| Property | Value |
|---|---|
| Standardized name | `western_redcedar` |
| BWI share | <1% |
| Max height | 25 m |
| Growth stages | 5, 10, 15, 20, 25 m |
| Preset | Cupressaceae - Western redcedar |
| Twig | WesternRedCedarTwig |
| Yield table | -- |
| Competition spacing | 5 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 7. European Beech (Fagus sylvatica)

| Property | Value |
|---|---|
| Standardized name | `european_beech` |
| BWI share | ~14% |
| Max height | 30 m |
| Growth stages | 5, 10, 15, 20, 25, 30 m |
| Preset | Fagaceae - Beech |
| Twig | EuropeanBeechTwig |
| Yield table | Buche |
| Competition spacing | 5 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |
| 30 m | <!-- open_h30m --> | <!-- comp_h30m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 8. European Oak (Quercus robur)

| Property | Value |
|---|---|
| Standardized name | `european_oak` |
| BWI share | ~7% |
| Max height | 30 m |
| Growth stages | 5, 10, 15, 20, 25, 30 m |
| Preset | Fagaceae - European oak |
| Twig | EuropeanOakTwig |
| Yield table | Eiche |
| Competition spacing | 6 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |
| 30 m | <!-- open_h30m --> | <!-- comp_h30m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 9. Common Ash (Fraxinus excelsior)

| Property | Value |
|---|---|
| Standardized name | `common_ash` |
| BWI share | ~3% |
| Max height | 30 m |
| Growth stages | 5, 10, 15, 20, 25, 30 m |
| Preset | Oleaceae - Ash |
| Twig | OneLeavedAshTwig |
| Yield table | Esche |
| Competition spacing | 6 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |
| 30 m | <!-- open_h30m --> | <!-- comp_h30m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 10. Sycamore Maple (Acer pseudoplatanus)

| Property | Value |
|---|---|
| Standardized name | `sycamore_maple` |
| BWI share | ~2% |
| Max height | 25 m |
| Growth stages | 5, 10, 15, 20, 25 m |
| Preset | Sapindaceae - Maple |
| Twig | SycamoreMapleFallTwig |
| Yield table | -- |
| Competition spacing | 6 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 11. Silver Birch (Betula pendula)

| Property | Value |
|---|---|
| Standardized name | `silver_birch` |
| BWI share | ~2% |
| Max height | 25 m |
| Growth stages | 5, 10, 15, 20, 25 m |
| Preset | Betulaceae - Silver birch |
| Twig | PaperBirchTwig |
| Yield table | Birke |
| Competition spacing | 8 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 12. Black Alder (Alnus glutinosa)

| Property | Value |
|---|---|
| Standardized name | `black_alder` |
| BWI share | ~2% |
| Max height | 25 m |
| Growth stages | 5, 10, 15, 20, 25 m |
| Preset | Betulaceae - Alder |
| Twig | BlackAlderTwig |
| Yield table | Erle |
| Competition spacing | 8 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 13. Hornbeam (Carpinus betulus)

| Property | Value |
|---|---|
| Standardized name | `hornbeam` |
| BWI share | ~1% |
| Max height | 20 m |
| Growth stages | 5, 10, 15, 20 m |
| Preset | Betulaceae - Hornbeam |
| Twig | HazelTwig |
| Yield table | Hainbuche |
| Competition spacing | 5 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 14. Small-leaved Linden (Tilia cordata)

| Property | Value |
|---|---|
| Standardized name | `small_leaved_linden` |
| BWI share | ~1% |
| Max height | 25 m |
| Growth stages | 5, 10, 15, 20, 25 m |
| Preset | Malvaceae - Linden |
| Twig | SmallLeavedLindenTwig |
| Yield table | Winterlinde |
| Competition spacing | 5 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |
| 25 m | <!-- open_h25m --> | <!-- comp_h25m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 15. Wild Cherry (Prunus avium)

| Property | Value |
|---|---|
| Standardized name | `wild_cherry` |
| BWI share | <1% |
| Max height | 20 m |
| Growth stages | 5, 10, 15, 20 m |
| Preset | Rosaceae - Wild cherry |
| Twig | JapaneseCherryTwig |
| Yield table | -- |
| Competition spacing | 6 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

---

### 16. Field Maple (Acer campestre)

| Property | Value |
|---|---|
| Standardized name | `field_maple` |
| BWI share | <1% |
| Max height | 20 m |
| Growth stages | 5, 10, 15, 20 m |
| Preset | Sapindaceae - Field maple |
| Twig | FieldMapleTwig |
| Yield table | -- |
| Competition spacing | 6 m |

**Preview Grid**

| Height | Open Grown | Competition |
|---|---|---|
| 5 m | <!-- open_h05m --> | <!-- comp_h05m --> |
| 10 m | <!-- open_h10m --> | <!-- comp_h10m --> |
| 15 m | <!-- open_h15m --> | <!-- comp_h15m --> |
| 20 m | <!-- open_h20m --> | <!-- comp_h20m --> |

**Production Status**

- [ ] Growth model calibrated
- [ ] Open-grown: full / reduced / bare
- [ ] Competition: full / reduced / bare

## Production Tracker

| # | Species | Growth Model | Open Full | Open Reduced | Open Bare | Comp Full | Comp Reduced | Comp Bare |
|---|---|---|---|---|---|---|---|---|
| 1 | Norway spruce | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 2 | Scots pine | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3 | Silver fir | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4 | Austrian pine | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5 | Grand fir | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 6 | Western redcedar | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 7 | European beech | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 8 | European oak | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 9 | Common ash | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 10 | Sycamore maple | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 11 | Silver birch | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 12 | Black alder | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 13 | Hornbeam | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 14 | Small-leaved linden | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 15 | Wild cherry | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 16 | Field maple | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |

## Open Questions and Future Work

1. **Stems reuse across density variants**: Currently each density variant requires a full re-simulation. An optimization would export stems geometry once and only vary twig PointInstancer density. This would cut production time by ~60% but requires pipeline changes.

2. **European larch and Douglas fir**: Together ~4% of southern German forests, increasing through active planting. Both require custom Grove presets and custom twigs. Priority for phase 2.

3. **Random seed variation**: Each individual type could benefit from 2--3 random seed variants to increase visual diversity. Currently not included to keep the initial dataset manageable.

4. **Dead/damaged trees**: Beyond the `bare` density variant, specific damage patterns (broken crown, hollow trunk, lightning strike) could be valuable for ecological realism. Out of scope for initial production.

5. **Understory vegetation**: Shrubs, ground cover, and young regeneration are not covered by this specification. They would need separate asset categories using different source tools.
