# GrowPy Dataset Update -- April 2026

**Procedurally generated tree meshes for Unreal Engine 5 Nanite**

---

## What we built

GrowPy takes species-calibrated growth parameters from The Grove 2.3 and generates
height-graded tree meshes ready for Nanite import. Growth models are calibrated
against **forestry yield tables**, linking simulated grove iterations to real-world
height and DBH development over time. Each tree is grown under two light regimes --
**competition** (forest stand) and **open grown** (solitary) -- producing distinct
crown architectures at every height step.

The pipeline outputs per tree variant:

- USD assembly (stems + twigs + foliage)
- PVE wind/physics configuration for Unreal
- Skeletal mesh for runtime animation
- Preview icon for the dataset catalog

## Pilot run: 2 species, 3 height steps

The first production run covers **European Beech** and **Norway Spruce** at 4m
height intervals. Each cell below is a generated preview icon showing the bare
branch architecture.

| Species | Context | 4 m | 8 m | 12 m |
|---|---|---|---|---|
| European Beech | Competition | ![h04m](../data/output/forest/european_beech/competition/European_Beech_comp_h04m_d04cm_full_icon.png) | ![h08m](../data/output/forest/european_beech/competition/European_Beech_comp_h08m_d12cm_full_icon.png) | ![h12m](../data/output/forest/european_beech/competition/European_Beech_comp_h12m_d19cm_full_icon.png) |
| European Beech | Open Grown | ![h04m](../data/output/forest/european_beech/open_grown/European_Beech_open_h04m_d04cm_full_icon.png) | ![h08m](../data/output/forest/european_beech/open_grown/European_Beech_open_h08m_d12cm_full_icon.png) | ![h12m](../data/output/forest/european_beech/open_grown/European_Beech_open_h12m_d18cm_full_icon.png) |
| Norway Spruce | Competition | ![h04m](../data/output/forest/norway_spruce/competition/Norway_Spruce_comp_h04m_d05cm_full_icon.png) | ![h08m](../data/output/forest/norway_spruce/competition/Norway_Spruce_comp_h08m_d12cm_full_icon.png) | ![h12m](../data/output/forest/norway_spruce/competition/Norway_Spruce_comp_h12m_d16cm_full_icon.png) |
| Norway Spruce | Open Grown | ![h04m](../data/output/forest/norway_spruce/open_grown/Norway_Spruce_open_h04m_d05cm_full_icon.png) | ![h08m](../data/output/forest/norway_spruce/open_grown/Norway_Spruce_open_h08m_d12cm_full_icon.png) | ![h12m](../data/output/forest/norway_spruce/open_grown/Norway_Spruce_open_h12m_d20cm_full_icon.png) |

Combined icon grid from the pilot run:

![Dataset icon grid](../data/output/forest/dataset_overview_icons.png)

The branching patterns clearly differ between species and contexts -- beech develops
a broad, spreading crown while spruce maintains its conical habit. Competition
trees are narrower with higher crown bases than their open-grown counterparts.

## Target dataset: 10 species, 5 m to 25 m

The next milestone scales the pipeline to **10 species x 2 contexts x 5 height
steps = 100 tree variants**. Heights will use 5 m increments from 5 m to 25 m,
covering the range from young stand establishment to mid-rotation canopy.

### Species selection

| # | Species | Scientific Name | Type | Max Height |
|---|---|---|---|---|
| 1 | European Beech | *Fagus sylvatica* | Broadleaf | 30 m |
| 2 | Norway Spruce | *Picea abies* | Conifer | 35 m |
| 3 | Scots Pine | *Pinus sylvestris* | Conifer | 30 m |
| 4 | European Oak | *Quercus robur* | Broadleaf | 30 m |
| 5 | Silver Birch | *Betula pendula* | Broadleaf | 25 m |
| 6 | Common Ash | *Fraxinus excelsior* | Broadleaf | 30 m |
| 7 | Silver Fir | *Abies alba* | Conifer | 35 m |
| 8 | Small-leaved Linden | *Tilia cordata* | Broadleaf | 25 m |
| 9 | Sycamore Maple | *Acer pseudoplatanus* | Broadleaf | 25 m |
| 10 | Wild Cherry | *Prunus avium* | Broadleaf | 20 m |

### Planned dataset matrix

Each cell represents one generated tree variant (competition + open grown).

| Species | 5 m | 10 m | 15 m | 20 m | 25 m |
|---|:---:|:---:|:---:|:---:|:---:|
| European Beech | x | x | x | x | x |
| Norway Spruce | x | x | x | x | x |
| Scots Pine | -- | -- | -- | -- | -- |
| European Oak | -- | -- | -- | -- | -- |
| Silver Birch | -- | -- | -- | -- | -- |
| Common Ash | -- | -- | -- | -- | -- |
| Silver Fir | -- | -- | -- | -- | -- |
| Small-leaved Linden | -- | -- | -- | -- | -- |
| Sycamore Maple | -- | -- | -- | -- | -- |
| Wild Cherry | -- | -- | -- | -- | -- |

**x** = pilot data available (close height match) | **--** = planned

### Output per variant

Each of the 100 tree variants produces:

| Output | Format | Purpose |
|---|---|---|
| Stem mesh | USD (.usda) | Nanite static mesh import |
| Skeletal mesh | USD (.usda) | Runtime wind animation |
| Twig assembly | USD (.usda) | Foliage attachment points |
| PVE config | JSON | Unreal PVE wind physics |
| Wind config | JSON | Procedural wind response |
| Preview icon | PNG | Dataset catalog & QA |
| Export control | PNG | Visual QA reference |

**Total estimated output: ~700 files across 100 variants.**

## What is next

1. **Calibrate 8 remaining species** -- fit yield-table growth models for each
   species using the existing calibration pipeline
2. **Configure presets** -- tune Grove 2.3 branching parameters per species
   (grow_length, grow_nodes, shade_area, etc.)
3. **Run full generation** -- batch produce all 100 variants through the
   dataset pipeline
4. **Validate in Unreal** -- import a representative subset into UE5 and
   verify Nanite LOD, wind animation, and foliage density

---

*Generated by the GrowPy dataset pipeline. See the full pilot dataset at
`data/output/forest/dataset_overview.md`.*
