# Illustration Assets (USD)

This folder contains modular, stylized USD assets derived from `prompts.md` and `segments.md` to assemble the 3×3 ecosystem illustration.

- Units: metersPerUnit = 1, upAxis = Y
- Colors: primvars:displayColor used for simple preview shading; primvars:displayOpacity for basic transparency
- Ground reference: soil top is at Y = 0; soil extends downward (−Y). Trees stand on Y = 0.
- Reuse: Place, scale, and rotate instances to achieve densities and variations per segment.

## Structure

- `trees/` — Conifer and broadleaf trees, each with Healthy, Stressed, Dead variants
- `roots/` — Shallow lateral, Deep taproot, Mixed
- `soil/` — Fine, Moderate, Coarse/Rocky soil blocks
- `water/` — Deep, Intermediate, Shallow groundwater planes

## Quick import (USD)

- Import any `.usda` into Blender, Omniverse, or USDView. Parent tree prims above the soil block at Y=0.
- For mixed forest segments, pair one conifer and one broadleaf and add the `roots/mixed.usda`.

## Notes

- These are simple geometric proxies for layout and education. You can swap materials with richer shaders later.
- Colors roughly indicate state:
  - Healthy: greener, fuller canopy
  - Stressed: yellower/browner canopy, reduced size
  - Dead: brown/grey canopy minimal or absent
