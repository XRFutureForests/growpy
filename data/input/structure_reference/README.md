# Structure reference store

Real-tree percentiles that generated catalog trees are gated against (XRFF-573). Plan
and gate: hub `04-LOGIC-TIER/tree-structure-realism-plan-2026-10`.

| File | Content |
|---|---|
| `reference_percentiles.csv` | one row per species x height bin x descriptor: `tiers`, `sources`, `unit`, `n`, `p5`, `p25`, `p50`, `p75`, `p95` |
| `coverage.csv` | real trees per species x source x tier x 5 m height bin |
| `descriptor_definitions.csv` | unit, frame, scan robustness and meaning of every descriptor |
| `manifest.json` | build date, growpy commit, input tables, tier rule, bin width, minimum n |
| `core_set.csv` | the core descriptors per species (`species_key`, `descriptor`); added once XRFF-576 fixes them. Until then the gate uses the scan-robust descriptors |

## Rows

- `height_bin = all`: every real tree of the species, height-normalised. Lengths (unit
  `m`) are divided by tree height, per-metre densities (`1/m`) multiplied by it; ratios
  and angles are unchanged. Tree height itself has no pooled row.
- `height_bin = h20-25` and so on: raw values of the trees in that 5 m bin, only where
  the bin holds at least `min_n` (10) trees.
- A row uses tiers A and B when it has at least `min_n` of them, otherwise every tier;
  `tiers` says which. Tiers are never pooled silently.
- Only the catalog's species are kept. Silver fir and Douglas fir have no QSM of their
  own: the gate scores them against Norway spruce (Kew, tier C) as a declared proxy.

## Sources

Built from `growpy-qsm-descriptors` tables of standardised QSMs (`growpy-qsm-standardize`):
BioDiv-3DTrees (tier A and C), the Belgium destructive set (tier B) and Kew Wakehurst
(tier C). Descriptors use the shared resolution of `growpy-qsm-descriptors` (laterals
shorter than 0.3 m and axes above order 2 removed). Point-cloud (L2) metrics and the
Ecosense TLS beech reference are added by XRFF-577 and XRFF-574.

## Rebuild

```shell
growpy-qsm-standardize biodiv data/input/reference_qsm/biodiv3dtrees_qsm/QSM/corrected --labels data/input/reference_qsm/biodiv3dtrees_graphs/labels.csv --out-dir data/output/structure/std/biodiv
growpy-qsm-standardize belgium data/input/reference_qsm/belgium_beech_pine_ash_larch --out-dir data/output/structure/std/belgium
growpy-qsm-standardize kew data/input/reference_qsm/kew_wakehurst --out-dir data/output/structure/std/kew
growpy-qsm-descriptors data/output/structure/std/biodiv --tier A --out-dir data/output/structure/desc_biodivA
growpy-qsm-descriptors data/output/structure/std/biodiv --tier C --out-dir data/output/structure/desc_biodivC
growpy-qsm-descriptors data/output/structure/std/belgium data/output/structure/std/kew --out-dir data/output/structure/desc_belgium_kew
growpy-qsm-reference data/output/structure/desc_*/descriptors.csv
```

`growpy-qsm-reference` rewrites everything here except this README and `core_set.csv`.
Scoring: `growpy-qsm-gate <generated descriptors.csv> --out-dir data/output/structure/<run>`,
always on unthinned growth JSONs.
