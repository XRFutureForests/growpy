# Yield Table Calibration

How GrowPy calibrates Grove 2.3 growth simulations against real-world yield tables
from local ingested data (via [pylometree](https://github.com/maxsperlich/pylometree)).

## Problem Statement

Grove's growth engine produces realistic tree geometry, but its internal growth rates
do not match forestry yield tables out of the box. The key challenges:

1. **Height mismatch**: Grove's default `grow_length` produces heights that differ
   (often lower) from yield table predictions at the same age.
2. **DBH-height coupling**: Grove uses a pipe model where radial thickening is
   fundamentally coupled to height growth. Increasing `grow_length` to match height
   targets inflates DBH far beyond yield table values.
3. **Limited levers**: Many Grove parameters that sound relevant to DBH
   (e.g. `thicken_base_scale`, `thicken_base_buttress`, `thicken_base_shape`) have
   zero effect at breast height (1.3m) because they only modify the trunk base.

## Calibrated Species

| Species | Yield Table | ID | YC | Base grow_length | Base thicken_tips |
|---------|-------------|----|----|------------------|-------------------|
| Norway spruce | Fichte Bayern | 2 | 12 | 0.30 | 0.007 |
| European beech | Buche Braunschweig | 10 | 8 | 0.40 | 0.0035 |
| European oak | Eiche Ungarn | 11 | 6 | 0.50 | 0.006 |

Silver fir was removed from the pipeline because it shares the same Grove preset as
Norway spruce, producing identical growth curves.

## Growth Curve Model: Chapman-Richards

GrowPy uses the Chapman-Richards function as its primary growth curve model for
interpolating yield tables and fitting Grove simulation output:

```
h(t) = A * (1 - exp(-k * t))^p
```

With optional baseline: `h(t) = y0 + (A - y0) * (1 - exp(-k * t))^p`

### Why Chapman-Richards

The Chapman-Richards equation is the standard growth model in forest mensuration,
chosen for several properties that make it well-suited to tree growth:

- **Biological basis**: Derived from the von Bertalanffy differential growth
  equation (anabolism vs catabolism), giving it a mechanistic interpretation
  rather than being a purely empirical curve fit.
- **Asymptotic behavior**: The parameter `A` provides a natural height ceiling,
  reflecting the biological reality that trees reach a maximum height.
- **Flexible shape**: The exponent `p` controls the inflection point, allowing
  the same equation to represent both fast-early growth (shade-intolerant pioneer
  species) and slow-early growth (shade-tolerant species).
- **Parsimonious**: Only 3-4 parameters (`A`, `k`, `p`, optional `y0`), which is
  few enough to fit reliably from the limited data points in typical yield tables.

Alternative sigmoidal models exist (Weibull, Gompertz, logistic, Korf, Hossfeld),
but Chapman-Richards consistently ranks among the best across species and site
conditions in comparative forestry studies.

### How GrowPy Uses It

| Context | Location | Purpose |
|---------|----------|---------|
| Yield table interpolation | `utils/yield_tables.py` | Smooth age-to-height mapping from sparse yield table data |
| Growth model fitting | `utils/analysis.py` | Mapping Grove simulation cycles to height/DBH curves |
| Extrapolation | `utils/analysis.py` | Predicting growth beyond the simulated cycle range |

The fit is not blindly trusted. `analysis.py` checks R² after fitting and falls
back to piecewise linear interpolation when the parametric fit is poor. This
handles species or datasets where the sigmoidal assumption does not hold (e.g.
irregular yield table data or very short simulation runs).

### Parameters

| Parameter | Meaning | Typical Range |
|-----------|---------|---------------|
| `A` | Asymptotic maximum (height ceiling) | 20-50 m for height |
| `k` | Growth rate coefficient | 0.01-0.15 |
| `p` | Shape/inflection exponent | 0.5-5.0 |
| `y0` | Baseline offset (optional) | 0-2 m |

## Calibration Pipeline

```
create_growth_models.py   (Step 3)   Simulate uncalibrated Grove growth
         |                           Compare vs yield tables, write overrides
         |                           Regenerate models with calibration applied
         |
generate_forest.py        (Step 4)   Forest generation with per-cycle overrides
                                     + post-hoc radial scaling at export
```

### Step 1: Uncalibrated Growth Models

`create_growth_models.py` runs Grove simulations with default preset parameters and
records height/DBH curves per cycle. These curves represent Grove's "native" growth
behavior for each species.

### Step 2: Yield Table Comparison & Calibration

`create_growth_models.py` loads pre-ingested yield table data via pylometree
(use `--ingest-yield-tables` flag to populate the local store first), interpolates it to
per-year resolution using PCHIP (preserving monotonicity), and computes per-cycle parameter overrides:

#### Height Calibration: `grow_length_per_cycle`

For each cycle, the ratio of yield-table height increment to Grove height increment
determines a scale factor applied to the base `grow_length`:

```
scale_factor[i] = target_increment[i] / grove_increment[i]
grow_length[i]  = base_grow_length * clip(smooth(scale_factor), 0.5, 1.8)
```

Scale factors are smoothed with a 3-point uniform filter and clamped to
`[base * 0.5, min(base * 2.0, 0.65)]` to prevent structural instability.

A safety check rejects the calibration if >30% of cycles hit the upper cap,
indicating the yield table demands growth rates Grove cannot structurally support.

#### DBH Calibration: Multi-Lever Approach

DBH calibration uses three complementary strategies:

**1. Per-cycle `thicken_tips` adjustment**

Same ratio-based approach as height, but with wider clamp range (0.05-20x) and
5-point smoothing. Values are floored at 0.0005 (effectively near-zero radial
growth at branch tips) and capped at 0.05.

**2. Static parameter overrides**

Evaluated once based on final-cycle DBH ratio:

| Parameter | Effect | When Applied |
|-----------|--------|-------------|
| `grow_nodes` | Fewer nodes = less cumulative radial thickening | When `target/grove < 0.9` |
| `thicken_deadwood` | Set to 0 to eliminate dead branch thickening | When base value > 0 |
| `thicken_tips_reduce` | Capped at 0.5 | When base value > 0.5 |

**3. Height-aware radial scaling at export (runtime)**

Even with parameter tuning, Grove's pipe model makes it physically impossible to
independently control DBH. The remaining gap is closed at USD export time by scaling
stem mesh vertices **perpendicular to each bone's axis**.

When skeleton data is available (`bones_info` + `point_attribute_bone_id`), each
vertex is scaled in the plane perpendicular to its parent bone rather than in the
global XZ plane. This correctly thickens branches without stretching them along
their length -- critical for angled and horizontal branches where XZ-plane scaling
would distort the mesh.

The scaling magnitude is **distributed across the full tree** to avoid unnatural
base bulging while preserving crown proportions:

- Below breast height (1.3m): full `radial_scale` applied
- From breast height to 85% of tree height: smoothstep blend toward `crown_scale`
- Above 85% of tree height: `crown_scale` (30% of full correction retained)

```text
radial_scale = clamp(target_dbh[cycle] / grove_dbh, 0.1, 2.0)
crown_scale  = 1.0 + (radial_scale - 1.0) * 0.3

per-vertex scale at height h:
  h <= 1.3m            -> radial_scale          (full correction)
  1.3m < h < blend_end -> smoothstep blend      (gradual transition)
  h >= blend_end       -> crown_scale           (30% correction retained)

per-vertex displacement (when bone data available):
  D = normalize(bone_end - bone_start)           (bone axis)
  V = vertex - bone_start                        (vertex offset)
  perp = V - dot(V, D) * D                       (perpendicular component)
  vertex_new = vertex + (s - 1) * perp           (scale only perpendicular)
```

The smoothstep function ($3t^2 - 2t^3$) provides C1 continuity, avoiding visible
seams in the mesh. For the trunk (near-vertical bones), perpendicular scaling is
equivalent to XZ-plane scaling. For angled branches, it prevents length distortion.

When no bone data is available (static mesh export), the scaling falls back to
XZ-plane scaling from the tree center.

Applied in `tree_export.py:build_tree_mesh()` and threaded through both the
single-export and snapshot-export paths in `generate_forest.py`.

## Parameter Sweep Findings

A systematic sweep of 7 Grove parameters (`sweep_dbh_params.py`) tested each
parameter's effect on DBH at breast height across all 3 species at 25 cycles.
Key findings:

### Parameters That Affect DBH at 1.3m

| Parameter | DBH Range (beech) | DBH Range (oak) | Height Impact | Usability |
|-----------|-------------------|------------------|---------------|-----------|
| `thicken_tips` | 48 cm | 33 cm | Minimal | Primary lever |
| `grow_nodes` | 17 cm | 13 cm | Zero to minimal | Secondary lever |
| `thicken_deadwood` | 5-12 cm | 12 cm | None | Free reduction |
| `thicken_join` | Massive | 58 cm | Destroys height | Unusable |

### Parameters With Zero DBH Effect at 1.3m

| Parameter | Reason |
|-----------|--------|
| `thicken_base_scale` | Only affects trunk below ~0.5m |
| `thicken_base_buttress` | Only affects trunk flare at ground level |
| `thicken_base_shape` | Only affects trunk taper below breast height |

These were removed from the calibration algorithm after the sweep confirmed zero
effect across all species.

## Calibration Data Format

Calibration is stored in each species' `seed.json` under `_yield_table_calibration`:

```json
{
    "_yield_table_calibration": {
        "table_id": 2,
        "yield_class": 12,
        "table_title": "Fichte Bayern",
        "grow_length_per_cycle": [0.3602, 0.3602, ...],
        "thicken_tips_per_cycle": [0.0005, 0.0005, ...],
        "static_overrides": {
            "thicken_tips_reduce": 0.5
        },
        "target_dbh_per_cycle": [0.461971, 0.425264, ...],
        "description": "Per-cycle values calibrated against yield table."
    }
}
```

- `grow_length_per_cycle`: Applied as `CycleArrayOverride` via `PresetOverrides`
- `thicken_tips_per_cycle`: Applied as `CycleArrayOverride` via `PresetOverrides`
- `static_overrides`: Applied as `StaticOverride` via `PresetOverrides`
- `target_dbh_per_cycle`: Used at export time for radial scale computation (not applied during simulation)

## Results at 25 Cycles

Growth model outputs after calibration (single seed):

| Species | Final Height (m) | Final DBH (cm) | Growth Rate (m/cycle) |
|---------|-------------------|-----------------|----------------------|
| Norway spruce | 8.84 | 10.8 | 0.35 |
| European beech | 10.38 | 18.5 | 0.42 |
| European oak | 8.26 | 27.5 | 0.33 |

Height calibration typically achieves 2-15% error relative to yield table targets.
DBH accuracy at simulation time remains limited by the pipe model coupling, but
post-hoc radial scaling at export corrects the geometry to match yield table DBH
values.

## Configuration

Species yield table mappings are in `growpy.toml`:

```toml
[calibration.species."Norway spruce"]
table_id = 2
yield_class = 12
flushes_per_year = 1.0
```

- `table_id`: Identifier for the yield table in the ingested pylometree store
- `yield_class`: Site quality class (index used for lookup)
- `flushes_per_year`: Cycle-to-age mapping (see below)

### Cycle-to-Age Mapping: `flushes_per_year`

Grove cycles represent growth flushes, not calendar years. The `flushes_per_year`
parameter controls how cycle indices map to yield table ages during calibration:

```text
calendar_age = cycle_index / flushes_per_year
```

| Value | Meaning | Example |
|-------|---------|---------|
| 1.0 (default) | 1 cycle = 1 year | 25 cycles = age 25 |
| 0.5 | 1 cycle = 2 years | 25 cycles = age 50 |
| 2.0 | 2 cycles = 1 year | 50 cycles = age 25 |

This is particularly useful when:

- A species needs more cycles than years to achieve realistic branching density
  (use `flushes_per_year > 1.0`)
- Simulating slow-growing species where fewer flushes produce sufficient structure
  (use `flushes_per_year < 1.0`)

The parameter can also be set via CLI: `--flushes-per-year 0.5` (overrides toml).
When not 1.0, the value is stored in the seed.json calibration block for reference.

## Key Files

| File | Role |
|------|------|
| `cli/create_growth_models.py` | Growth model generation + calibration (step 3) |
| `cli/generate_forest.py` | Forest pipeline with radial scaling |
| `tools/sweep_dbh_params.py` | Parameter sweep tool (diagnostic) |
| `config/preset_overrides.py` | PresetOverrides system + `load_target_dbh_from_preset()` |
| `io/tree_export.py` | Radial scaling in `build_tree_mesh()` |
| `data/assets/presets/*.seed.json` | Per-species calibration data |

## Limitations

1. **Pipe model coupling**: Grove's physics-based pipe model makes DBH a consequence
   of branching structure, not an independent variable. No combination of Grove
   parameters can fully decouple height and DBH growth.

2. **Single-seed variability**: Current calibration uses 1 seed for speed. Production
   runs should use 3+ seeds (`--seeds 3`) for robust curves.

3. **Radial scaling preserves topology**: Perpendicular-to-bone scaling corrects
   trunk DBH without distorting branch length or direction. The height-aware
   smoothstep blend transitions from full correction at breast height to no
   correction in the crown. Extreme scale factors (>1.5x) may still produce
   visible discontinuities at the blend boundary. When bone data is unavailable
   (static mesh export), scaling falls back to the XZ plane.

4. **Flush-year mapping is per-species**: The `flushes_per_year` parameter is constant
   across the life of a tree. In reality, juvenile trees may flush more frequently
   than mature ones. A per-cycle mapping function could improve accuracy but adds
   complexity.
