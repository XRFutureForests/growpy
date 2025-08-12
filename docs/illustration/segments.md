# Segments and assets overview

## Scene overview

This scene is a 3×3 matrix (rows = species mix, columns = stand density) designed to show above- and below-ground gradients across forest types. Rows progress from Conifer Monoculture → Mixed Forest → Broadleaf Monoculture. Columns progress from Open (low density) → Medium → Dense (high density). Across these sections, soil texture and groundwater depth vary to highlight ecological contrasts and their impact on roots, tree vigor, and competition. The gradients are on opposing diagonals (they do not align): groundwater depth transitions from deep (low water table) in the bottom-left to shallow (high water table) in the top-right, while soil texture transitions from coarse in the top-left to fine in the bottom-right.

### Section gradients matrix (per species × density cell)

_Soil texture (↘): coarse at top-left → fine at bottom-right._  
_Groundwater depth (↗): deep at bottom-left → shallow at top-right._

|                          | **Open Stand (Low Density)**                                                     | **Medium Density**                                                              | **Dense Stand (High Density)**                                                  |
|--------------------------|---------------------------------------------------------------------------------|---------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| **Conifer Monoculture**   | • **Soil Texture & Water Capacity:** Coarse, rocky/sandy soil, low retention • **Groundwater Height:** Intermediate depth • **Root Types & Distribution:** Shallow lateral roots with some vertical extension | • **Soil Texture & Water Capacity:** Coarse, rocky/sandy soil, low retention • **Groundwater Height:** Shallow (high water table) • **Root Types & Distribution:** Shallow lateral; oxygen-limited deeper layers | • **Soil Texture & Water Capacity:** Moderate texture (loam-sandy), medium retention • **Groundwater Height:** Shallow (high water table) • **Root Types & Distribution:** Shallow roots; limited vertical growth |
| **Mixed Forest**          | • **Soil Texture & Water Capacity:** Coarse, rocky/sandy soil, low retention • **Groundwater Height:** Deep (low water table) • **Root Types & Distribution:** Lateral conifer + deep broadleaf taproots | • **Soil Texture & Water Capacity:** Moderate texture (loam-sandy), medium retention • **Groundwater Height:** Intermediate depth • **Root Types & Distribution:** Vertical stratification; balanced competition | • **Soil Texture & Water Capacity:** Fine-textured (loam/clay), high retention • **Groundwater Height:** Shallow (high water table) • **Root Types & Distribution:** Mixed systems; broadleaf taproots constrained |
| **Broadleaf Monoculture** | • **Soil Texture & Water Capacity:** Moderate texture (loam-sandy), medium retention • **Groundwater Height:** Deep (low water table) • **Root Types & Distribution:** Deep taproots with lateral support | • **Soil Texture & Water Capacity:** Fine-textured (loam/clay), high retention • **Groundwater Height:** Deep (low water table) • **Root Types & Distribution:** Deep taproots dominant | • **Soil Texture & Water Capacity:** Fine-textured (loam/clay), high retention • **Groundwater Height:** Intermediate depth • **Root Types & Distribution:** Deep roots with lateral spread |

***

## Detailed segment descriptions (9 cells)

For each segment, provide three tree health states: Healthy, Stressed, Dead/Dying. Use density by instance count and canopy fullness to convey stand density.

### 1) Conifer monoculture (row 1)

- Open stand — intermediate groundwater, coarse soil.  
- Medium density — shallow groundwater, coarse soil.  
- Dense stand — shallow groundwater, moderate soil.  

Estimated tree counts per cell: Open 2–3, Medium 4–5, Dense 5–7.  
Stressed/dead: ~10–15% overall; most common in rocky, dense segment.

### 2) Mixed forest (row 2; paired conifer + broadleaf)

- Open stand — deep groundwater, coarse soil.  
- Medium density — intermediate groundwater, moderate soil.  
- Dense stand — shallow groundwater, fine soil.  

Place tree pairs (conifer + broadleaf) per cell with the same density logic.  
Stressed/dead: ~10%, concentrated in medium and dense segments with challenging soils.

### 3) Broadleaf monoculture (row 3)

- Open stand — deep groundwater, moderate soil.  
- Medium density — deep groundwater, fine soil.  
- Dense stand — intermediate groundwater, fine soil.  

Use the same density counts as conifers (adjust spacing for larger crowns).  
Stressed/dead: ~10–15%, pronounced in the rocky/open segment.

***

## Segment overview table

| Segment (row: species, column: stand density)         | Trees (no. per segment)                  | Tree Health Mix                  | Root System Type(s)                         | Soil Block Type             | Groundwater Depth Indicator |
|------------------------------------------------------|-----------------------------------------|--------------------------------|---------------------------------------------|----------------------------|-----------------------------|
| Conifer / Open                                        | 2-3 conifer trees                       | ~85% healthy, 10% stressed, 5% dead | Shallow lateral with some vertical          | Coarse/rocky soil          | Intermediate water table     |
| Conifer / Medium                                      | 4-5 conifer trees                       | ~80% healthy, 15% stressed, 5% dead | Shallow lateral; oxygen-limited deeper soil | Coarse/rocky soil          | Shallow water table          |
| Conifer / Dense                                      | 5-7 conifer trees                       | ~70% healthy, 20% stressed, 10% dead| Shallow with limited vertical attempts       | Moderate texture           | Shallow water table          |
| Mixed / Open                                         | 1-2 conifer + 1-2 broadleaf trees      | ~90% healthy, 8% stressed, 2% dead   | Lateral conifer + deep broadleaf            | Coarse/rocky soil          | Deep water table             |
| Mixed / Medium                                       | 2-3 conifer + 2-3 broadleaf trees      | ~85% healthy, 12% stressed, 3% dead  | Vertical stratification                     | Moderate texture           | Intermediate water table     |
| Mixed / Dense                                       | 3-4 conifer + 3-4 broadleaf trees      | ~90% healthy, 7% stressed, 3% dead   | Mixed; broadleaf taproots constrained       | Fine-textured soil         | Shallow water table          |
| Broadleaf / Open                                    | 2-3 broadleaf trees                     | ~75% healthy, 20% stressed, 5% dead  | Deep taproots with lateral support          | Moderate texture           | Deep water table             |
| Broadleaf / Medium                                  | 4-5 broadleaf trees                     | ~85% healthy, 10% stressed, 5% dead  | Deep taproots dominant                      | Fine-textured soil         | Deep water table             |
| Broadleaf / Dense                                   | 5-7 broadleaf trees                     | ~80% healthy, 15% stressed, 5% dead  | Deep roots with lateral spread              | Fine-textured soil         | Intermediate water table     |

***

## Assets

### Asset strategy and relation to segments

Use a small set of reusable base assets mapped systematically to the 3×3 matrix:

- Two base tree species (conifer, broadleaf) × three health states (healthy, stressed, dead) → density conveyed by instance count and canopy fullness.
- Three modular root systems (shallow lateral, deep taproot, mixed) chosen per segment based on soil/groundwater.
- Three soil blocks (fine, moderate, coarse/rocky) reused across the grid according to the soil gradient.
- Three groundwater indicators (deep, intermediate, shallow) to visualize the water table per segment.

#### Unique asset count

| Asset Type               | Quantity | Remarks                                |
|-------------------------|----------|----------------------------------------|
| Tree Base Models         | 2        | Conifer, Broadleaf                     |
| Tree Health Variants     | 3 per model (Healthy, Stressed, Dead) | Reused across all density variants  |
| Root Systems             | 3        | Shallow, Deep, Mixed                   |
| Soil Blocks              | 3        | Fine, Moderate, Coarse/Rocky           |
| Groundwater Indicators   | 3        | Deep, Intermediate, Shallow            |

### Individual assets

#### 1) Tree models (core reusable base assets)

- Conifer tree base model  
  - Variants: Healthy, Stressed, Dead  
  - Adjust density via modular branches/leaf clusters and instance count  
  - Reuse across all conifer cells

- Broadleaf tree base model  
  - Variants: Healthy, Stressed, Dead  
  - Modulate canopy density/branching and instance count  
  - Reuse across all broadleaf cells

- Mixed forest trees  
  - Place the conifer and broadleaf bases side-by-side  
  - Vary size/position to represent stand densities

#### 2) Root system models (3 modular assets)

- Shallow lateral root system — conifers, rocky/coarse soils.  
- Deep taproot system — broadleafs with fine soils and deep groundwater.  
- Mixed root system — overlay of shallow + deep for mixed forests.  
Root density/depth should match the segment’s soil and groundwater.

#### 3) Soil blocks (3 variants)

- Fine-textured (loam/clay), dark and smooth — high water retention.  
- Moderate-textured (loam-sandy) — intermediate features.  
- Coarse/rocky (sand + stones) — lower retention.

#### 4) Groundwater indicators (3 depth variants)

- Deep water table — plane low in the soil profile.  
- Intermediate water table — mid-profile plane.  
- Shallow water table — near-surface plane.

### Asset distribution by segment

| Segment                      | Trees (number & type)                                             | Root System                          | Soil Block Type        | Water Table Indicator    |
|------------------------------|------------------------------------------------------------------|---------------------------------------|------------------------|--------------------------|
| Conifer / Open               | 2-3 Conifer (healthy/stressed/dead variants mixed)              | Shallow lateral with some vertical    | Coarse/rocky soil      | Intermediate water table |
| Conifer / Medium             | 4-5 Conifer                                                     | Shallow lateral; oxygen-limited depth | Coarse/rocky soil      | Shallow water table      |
| Conifer / Dense              | 5-7 Conifer                                                     | Shallow with limited vertical attempts| Moderate-textured soil | Shallow water table      |
| Mixed / Open                 | 1-2 Conifer + 1-2 Broadleaf (each health variants as needed)    | Lateral conifer + deep broadleaf      | Coarse/rocky soil      | Deep water table         |
| Mixed / Medium               | 2-3 Conifer + 2-3 Broadleaf                                     | Vertical stratification               | Moderate-textured soil | Intermediate water table |
| Mixed / Dense                | 3-4 Conifer + 3-4 Broadleaf                                     | Mixed; broadleaf taproots constrained | Fine-textured soil     | Shallow water table      |
| Broadleaf / Open             | 2-3 Broadleaf                                                   | Deep taproot + lateral                | Moderate-textured soil | Deep water table         |
| Broadleaf / Medium           | 4-5 Broadleaf                                                   | Deep taproot dominant                 | Fine-textured soil     | Deep water table         |
| Broadleaf / Dense            | 5-7 Broadleaf                                                   | Deep roots + lateral spread           | Fine-textured soil     | Intermediate water table |

