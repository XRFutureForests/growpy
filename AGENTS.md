# GrowPy

Procedural tree/forest generation pipeline: CSV species data → The Grove 2.3 growth simulation → USD Nanite assemblies for Unreal Engine 5.7+. Trees grow to height milestones; stem diameter is realised at export from yield-table height-DBH allometry. Competition variants come from Grove's Surround shell. Outputs USD assemblies, PVE JSON, OBJ for Helios++ LiDAR.

## Documentation Map

| Need | Read |
|------|------|
| What growpy is, the dataset, why it is built this way | [README.md](README.md) |
| Install, the four steps, dataset production, Unreal import, troubleshooting | [RUNBOOK.md](RUNBOOK.md) |
| Guides, reference, internals | [docs/](docs/README.md) |
| Why The Grove, why USD, the calibration records, Grove API analysis | XR Future Forests Lab knowledge hub (`04-LOGIC-TIER/growpy*`, `99-RESOURCES/vendor/the-grove/`) — **not** in this repo |
| Tasks | Linear |

Deep-dive documentation is deliberately not duplicated here. If you need to explain *why* an
approach was chosen, write it in the knowledge hub and link to it. The Grove's own product
documentation is not redistributed — point at thegrove3d.com.

## Source Layout

| Path | Contents |
|------|----------|
| `src/growpy/cli/` | argparse entry points for all CLI scripts |
| `src/growpy/core/` | forest.py, tree.py, twig.py, skeleton.py, grove.py |
| `src/growpy/pipelines/` | step_runner.py, forest_stages.py, forest_exports.py, dataset_csv_planner.py |
| `src/growpy/io/usd/` | USD/Nanite exporters |
| `src/growpy/io/unreal/` | PVE JSON, import scripts, wind |
| `src/growpy/io/helios/` | OBJ export, Helios scene XML |
| `src/growpy/config/` | TOML config, species overrides |
| `src/growpy/utils/` | yield tables, allometry, analysis, logging, GBIF |
| `src/growpy/tools/` | console tools: UE exec + import/viewport probes, crown metrics, surround-density sweep + summariser, PVE assets + leaf area + export click, preflight, twig ladder, texture packing, diagnostics |
| `src/growpy/blender/` | grove_extract, twig_converter |
| `tools/ue_plugins/XRFFEditorScripting/` | Unreal Editor C++ plugin (canonical source): blueprint scripting helpers and the PVE skeleton dump to growth JSON; build recipe in its README |

Structure evaluation (QSM readers, descriptors, reference store, gate, point-cloud metrics, synthetic scans) moved to the internal repo **tree-structure**, and the tree look survey to **tree-survey**, on 2026-10-28 (owner decision; history kept). growpy grows and exports trees; tree-structure judges them from growpy's output files.

## CLI Scripts

| Script | Purpose |
|--------|---------|
| `growpy-init-config` | Initialise project TOML config |
| `growpy-prepare-assets` | Prepare input assets |
| `growpy-convert-twigs` | Convert twig meshes via Blender/Grove |
| `growpy-create-models` | Create tree models (growth simulation + yield-table pacing calibration) |
| `growpy-build-allometry` | Fit height-DBH allometry from yield tables (no Grove simulation) |
| `growpy-generate-forest` | Run full forest generation pipeline |
| `growpy-dataset-pipeline` | Dataset CSV planning and execution |
| `growpy-sweep-surround-density` / `growpy-summarise-surround-density` | Run and read the per-species surround-shell density sweep |
| `growpy-crown-metrics` | Forestry crown dimensions from exported assemblies |
| `growpy-calibrate-crown-density` / `growpy-icon-metrics` | Crown-density and icon-based crown-fill measurement |
| `growpy-derive-twig-ladder` | Derive a twig size ladder from a Grove twig |
| `growpy-pack-pve-textures` | Pack twig textures into the two maps PVE's tree material expects |
| `growpy-pve-assets` | Generate the UE script that imports PVE twig palettes and bark materials |
| `growpy-material-intake` | Bark material intake (XRFF-679): `fab` / `grove` / `set` (any folder of texture maps) write an intake folder under `data/input/materials/<id>/`; `build` checks it, packs the `_NAH` map, writes the UE script for `MI_<id>` and regenerates `data/input/materials/catalog.toml` |
| `growpy-pve-leaf-area` | Report scale-corrected leaf area for the calibrated PVE trees |
| `growpy-pve-export` | Trigger the Export of PVE graphs in the running editor (posted Ctrl+E + UI Automation; works with the workstation locked) |
| `growpy-pve-gallery` | Lay the exported PVE trees out in gallery levels (one per species: stand radius x stage) to judge the catalog by eye; skips meshes over the 32,767-bone cap; `--shots` photographs each stand row |
| `growpy-twig-audit` | Offline audit of where the PVE plan places foliage, per catalog cell, against `config/twig_audit.toml` (upturned shoots, leader foliage, top-band density); needs no editor |
| `growpy-structure-regrow` | Regrow one species for scoring: N seeds, unthinned `growth_json_only`, optional preset knobs (`--set key=value`) in a sandbox project root, into `data/output/regrow/<species>/<arm>/`; score the arm with `tree-structure-score-arm` (tree-structure repo) |
| `growpy-export-budget` | Export budget report (XRFF-592): bones, branches with bones, planned parts and triangles per catalog mesh; skinned transform buffer share per site x scenario step from the twin's tree caches, gated against the draft PCVR budget |
| `growpy-twig-catalog` | Twig catalog (XRFF-684): `seed <species>` writes one entry per twig part a species wears today under `data/input/twigs/<id>/twig.toml` (part kind, cut-diameter bin, source, licence, leaf area); `build` checks every entry and regenerates `data/input/twigs/catalog.toml`; `check` lists unsized or broken entries |
| `growpy-tree-catalog` | Tree catalog manifest (XRFF-678): `build` writes `data/input/tree_catalog.toml` from the PVE plan manifests, an editor bones dump and target-sheet score CSVs (structure, twig set, bark material, variant, meshes, twigs, bones, target result per tree asset); `check` lists missing entries and out-of-target traits |
| `growpy-catalog-print` | Print catalog PDF (structure side views, twig renders, bark renders); `--publish` writes it beside the UE catalog and copies it plus an overview note to the knowledge hub. `growpy-pve-export` runs it after each export |
| `growpy-catalog-backup` | Incremental backup of the tree catalog to the lab share `40_SideProjects\tree_catalog\` (UE `Content/Generated/Trees`, the `r??` skeleton ladders and plan folders, the bark intake; sha256 manifest); run after each finished species and at each release |
| `growpy-skeleton-budget` | Bone budget of catalog growth JSONs (points, polylines, Douglas-Peucker keep shares) and, with `--spacing`, what `min_point_spacing` would save |
| `growpy-preflight-assembly` | Validate a USD assembly before import (bindJoints, paths) |
| `growpy-ue-exec` | Execute Unreal Engine import scripts (with watchdog) |
| `growpy-ue-import-probe` / `growpy-ue-viewport-probe` | Gate 2 import cost and Gate 4 frame-time measurement |
| `growpy-analyze-usda` | Analyse USD assembly output (triangle budget) |
| `growpy-diagnose-growth` | Diagnose growth simulation results |
| `growpy-visualize-tree` | Visualise individual tree output |
| `growpy-sensitivity-analysis` | Run parameter sensitivity analysis |

## Critical Rules

Workspace rules (decision rights, commits, Linear, tool preferences) are in the workspace `AGENTS.md` one level above the repos and apply here too. The basics: change only what the task needs, verify each step, commit your own work with an explicit pathspec, never commit secrets.

| Category | Rule | When to Apply |
|----------|------|---------------|
| Language | Keep project code and documentation in English | For all written artifacts |
| Research | Prefer official Python and USD documentation sources | Before stack-specific decisions |

## Development Commands

| Task | Command |
|------|---------|
| Create conda env | `conda env create -f environment.yml` |
| Activate env | `conda activate growpy` |
| Install (editable) | `pip install -e .` |
| Run tests | `pytest` |
| Format | `ruff format .` |
| Lint | `ruff check .` |

## Maintenance

**Update Triggers:**
- When root navigation or canonical document links change
- When CLI scripts are added or removed
- When core commands change
- When critical project rules change

**Verification:**
- [ ] Links resolve
- [ ] Commands match current project setup
- [ ] CLI script table matches `pyproject.toml` entry points
- [ ] Canonical docs listed here still exist

**Last Updated:** 2026-11-17
