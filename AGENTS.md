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
| `src/growpy/structure/` | Real-tree QSM standardisation: canonical cylinder/tree schema, single axis rule, per-format readers, per-dataset adapters, store (no Grove or bpy import) |
| `src/growpy/blender/` | grove_extract, twig_converter |

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
| `growpy-pve-leaf-area` | Report scale-corrected leaf area for the calibrated PVE trees |
| `growpy-pve-export` | Trigger the Export of PVE graphs in the running editor (posted Ctrl+E + UI Automation; works with the workstation locked) |
| `growpy-pve-gallery` | Lay the exported PVE trees out in gallery levels (one per species: stand radius x stage) to judge the catalog by eye; skips meshes over the 32,767-bone cap; `--shots` photographs each stand row |
| `growpy-twig-audit` | Offline audit of where the PVE plan places foliage, per catalog cell, against `config/twig_audit.toml` (upturned shoots, leader foliage, top-band density); needs no editor |
| `growpy-structure-descriptors` | Branching-structure descriptors of growth JSONs in the hub's schema frames (whorls per node, tier spacing, chord angle to half length, straightness, crown profile, regularity indices); `--compare A B` for side-by-side cells |
| `growpy-qsm-to-growth` | Convert a TreeQSM point graph (GraphML, e.g. BioDiv-3DTrees) to the growth-JSON layout so a real tree goes through the same descriptor code as a generated one |
| `growpy-qsm-standardize` | Convert a published QSM dataset (Kew, Belgium, Ghent, TreeML, BioDiv graphs) to the canonical cylinder + tree tables of `growpy.structure`: one frame, one axis rule, DBH/height/volume measured the same way, source metadata and quality numbers side by side |
| `growpy-qsm-export-growth` | Write growth JSONs from a standardised QSM dataset so real trees go through the same tools as Grove trees (descriptors, PVE exporter) |
| `growpy-qsm-descriptors` | Structure descriptors on standardised trees after a common-resolution prune: geometry (L), size-free growth-rule fingerprint (G), topology (T), sequences (S) and branch/crown form (F: dangling, wave, irregularity, asymmetry, crown per DBH against the reported DBH), with definitions (unit, frame, scan robustness) and a summary by source kind × species × height class |
| `growpy-qsm-prototypes` | Prototype silhouettes of real trees per species x height class x crown-width tertile, drawn in the catalog icon style (front view, 512 px, pipe-model radii from DBH): occupancy map, template skeleton from median unrolled branch curves, medoid tree; `branch_curves.csv`, Grove overlays and per-decile curve scores (`--grove-lane`), `prototype_overview.md` laid out like `dataset_overview.md` |
| `growpy-qsm-to-mtg` | Write the quality-checked standardised QSM trees as OpenAlea MTG files (tree and cylinder scales, `<`/`+` edges, geometry and axis properties) at the common resolution, plus `index.csv`; needs the `growpy-openalea` conda env (openalea.mtg, `-c openalea3`) |
| `growpy-branching-model` | Fit a stochastic branching model per species x height class from the MTG files (Bayesian-smoothed position-dependent Markov chain of lateral events along axes, real-data pools of laterals and stems), generate trees with its L-Py rule set (`structure/branching.lpy`), and validate them against real trees and the Grove catalog through the descriptors; `growpy-openalea` env |
| `growpy-preflight-assembly` | Validate a USD assembly before import (bindJoints, paths) |
| `growpy-ue-exec` | Execute Unreal Engine import scripts (with watchdog) |
| `growpy-ue-import-probe` / `growpy-ue-viewport-probe` | Gate 2 import cost and Gate 4 frame-time measurement |
| `growpy-analyze-usda` | Analyse USD assembly output (triangle budget) |
| `growpy-diagnose-growth` | Diagnose growth simulation results |
| `growpy-visualize-tree` | Visualise individual tree output |
| `growpy-sensitivity-analysis` | Run parameter sensitivity analysis |

## Critical Rules

| Category | Rule | When to Apply |
|----------|------|---------------|
| Confirmation | Never commit or push without explicit user confirmation | Always |
| Scope | Modify only what the request requires — no adjacent cleanup | Always |
| Clarity | State assumptions explicitly; ask when uncertain rather than guessing | Before coding |
| Simplicity | Minimum code that solves the problem — no speculative features | Always |
| Verification | Define success criteria before starting; verify each step | Per task |
| Task tracking | Use Linear MCP for all issue operations — check before creating new issues | Always |
| Language | Keep project code and documentation in English | For all written artifacts |
| Research | Prefer official Python and USD documentation sources | Before stack-specific decisions |

## MCP Tool Preferences

| Need | Preferred flow |
|------|----------------|
| Discover files | `inspect_path` with narrow path |
| Search text | `grep_search(output_mode="summary")`, narrow before content mode |
| Read code | `outline` or targeted `read_file` |
| Edit code | `read_file(edit_ready=true)` → `edit_file(base_revision)` → verify |
| Semantic risk | `index_project` → symbol/architecture analysis |

Use `hex-line` first for repository text reads, search, and edits. Use `hex-graph` first for semantic questions: symbol identity, references, architecture, edit blast radius. Fall back to built-in Read/Edit/Write/Grep/Glob only when MCP is unavailable or task is shell-native.

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

**Last Updated:** 2026-09-25
