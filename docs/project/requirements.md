# Requirements Specification: GrowPy

**Document Version:** 1.0
**Date:** 2026-05-11
**Status:** Active
**Standard Compliance:** ISO/IEC/IEEE 29148:2018

<!-- SCOPE: Functional requirements (FR-XXX-NNN format) with MoSCoW prioritization, acceptance criteria, constraints, assumptions, traceability ONLY. -->
<!-- DOC_KIND: explanation -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Read when you need product scope, functional requirements, or acceptance boundaries. -->
<!-- SKIP_WHEN: Skip when you only need implementation details, operations, or low-level schema facts. -->
<!-- PRIMARY_SOURCES: docs/README.md, docs/project/architecture.md, docs/project/tech_stack.md -->

<!-- DO NOT add here: Tech stack → tech_stack.md, Architecture → architecture.md, Pipeline internals → docs/architecture/ -->

## Quick Navigation

- [Docs Hub](../README.md)
- [Architecture](architecture.md)
- [Tech Stack](tech_stack.md)
- [Pipeline Overview](../architecture/pipeline-overview.md)

## Agent Entry

| Signal | Value |
|--------|-------|
| Purpose | Defines functional scope, business expectations, and acceptance boundaries for the GrowPy pipeline. |
| Read When | You need feature scope, priorities, pipeline step contracts, or requirement traceability. |
| Skip When | You only need implementation details, module internals, or CLI reference. |
| Canonical | Yes |
| Next Docs | [Architecture](architecture.md), [Tech Stack](tech_stack.md), [Pipeline Overview](../architecture/pipeline-overview.md) |
| Primary Sources | `docs/README.md`, `docs/project/architecture.md`, `docs/project/tech_stack.md` |

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional requirements for GrowPy — a procedural forest generation pipeline that transforms species/position CSV data into Unreal Engine 5-ready USD forest assemblies via The Grove 2.3 growth simulation engine.

### 1.2 Scope

GrowPy is a single-user, offline batch pipeline operated by researchers at XR Future Forests Lab, University of Freiburg (Eva Mayr-Stihl Stiftung funded).

**IN SCOPE:**
- 4-step pipeline: asset preparation → twig conversion → growth model calibration → forest generation
- Yield-table-calibrated growth simulation for multiple tree species
- USD/Nanite assembly export for Unreal Engine 5.7+
- OBJ/MTL + scene XML export for Helios++ LiDAR simulation
- PVE JSON and wind animation sidecar generation for Unreal Engine
- GBIF-based species name normalisation

**OUT OF SCOPE:**
- Real-time rendering or runtime forest simulation
- Web or networked interfaces
- Automated deployment or containerisation
- Warehouse or inventory management of Grove licences

### 1.3 Intended Audience

- Pipeline developers (XR Future Forests Lab)
- Research scientists running forest simulations
- System architects planning downstream UE/LiDAR integrations

### 1.4 References

- Architecture Document: [architecture.md](architecture.md)
- Pipeline Overview: [docs/architecture/pipeline-overview.md](../architecture/pipeline-overview.md)
- Data Flow Contracts: [docs/architecture/data-flow.md](../architecture/data-flow.md)
- Yield Table Calibration: [docs/reference/yield-table-calibration.md](../reference/yield-table-calibration.md)

---

## 2. Overall Description

### 2.1 Product Perspective

GrowPy is a standalone Python pipeline that bridges field-measurement data (species, position, target dimensions) and real-time 3D environments. It integrates The Grove 2.3 (commercial Blender add-on) as its tree simulation engine via the `bpy` Python API.

Upstream inputs: Forest layout CSVs, Grove 2.3 source assets, German forestry yield tables (via `pylometree`).
Downstream consumers: Unreal Engine 5.7+ (via USD/Nanite + PVE JSON) and Helios++ LiDAR simulator (via OBJ/MTL + scene XML).

### 2.2 User Classes and Characteristics

| User Class | Profile | Primary Tasks |
|------------|---------|---------------|
| Pipeline Operator | Researcher with Python/Conda knowledge | Run full dataset pipeline, inspect outputs |
| Species Modeller | Forestry scientist | Tune yield-table calibration parameters, review growth curves |
| UE Integration Engineer | 3D/VR developer | Import USD assemblies, configure Nanite/PVE/Wind in UE 5.7+ |
| LiDAR Analyst | Remote-sensing researcher | Consume OBJ/MTL + Helios++ scene XML |

### 2.3 Operating Environment

- **OS:** Windows 10/11 or Linux (where Blender/Grove runs)
- **Runtime:** Python 3.12 inside a dedicated `growpy` conda environment
- **Blender dependency:** Steps 2 and 4 require `bpy` (bundled via pip); all steps are invoked as subprocesses by the orchestrator to keep `bpy` isolated
- **Storage:** Local filesystem; inputs at `data/input/`, outputs at `data/output/`, working assets at `data/assets/`
- **Downstream:** Unreal Engine 5.7+ (separate machine/editor), Helios++ (separate binary)

---

## 3. Functional Requirements

### 3.1 Pipeline Orchestration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-ORC-001 | The orchestrator (`growpy-dataset-pipeline`) SHALL run all 4 pipeline steps in dependency order, invoking each as a subprocess. | MUST |
| FR-ORC-002 | The orchestrator SHALL support running a subset of steps via `--steps {1,2,3,4,all}`. | MUST |
| FR-ORC-003 | The orchestrator SHALL support parallel execution of Step 4 across species via `--workers N`. | SHOULD |
| FR-ORC-004 | The orchestrator SHALL support `--dry-run` mode that validates configuration without writing outputs. | SHOULD |
| FR-ORC-005 | The orchestrator SHALL support `--pilot` mode that restricts processing to a representative subset of species. | COULD |
| FR-ORC-006 | The orchestrator SHALL report per-step success/failure and halt on error with a non-zero exit code. | MUST |

### 3.2 Step 1 — Asset Preparation

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-AST-001 | Step 1 SHALL copy Grove 2.3 presets and textures from `src/the_grove_23/` into `data/assets/` with standardised species names. | MUST |
| FR-AST-002 | Step 1 SHALL validate that all species referenced in the forest CSV exist in `config/tree_asset_lookup.csv`. | MUST |
| FR-AST-003 | Step 1 SHALL normalise species names via GBIF lookup and apply configured overrides. | SHOULD |
| FR-AST-004 | Step 1 SHALL resize textures to power-of-2 dimensions for Nanite compatibility. | SHOULD |

### 3.3 Step 2 — Twig Conversion

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-TWG-001 | Step 2 SHALL convert Grove `.blend` twig source files to USD foliage assets (`*_foliage_skeletal.usda`). | MUST |
| FR-TWG-002 | Step 2 SHALL output one `.usda` foliage file per twig–species pair under `data/assets/twigs/<twig>/`. | MUST |
| FR-TWG-003 | Step 2 SHALL apply Nanite-compatible UV and material settings during conversion. | MUST |
| FR-TWG-004 | Step 2 SHALL skip already-converted twigs unless `--force` is specified. | SHOULD |

### 3.4 Step 3 — Growth Model Calibration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-GRW-001 | Step 3 SHALL run uncalibrated Grove growth simulations for each species. | MUST |
| FR-GRW-002 | Step 3 SHALL fit Chapman-Richards curves to German forestry yield table targets (height and DBH at site index). | MUST |
| FR-GRW-003 | Step 3 SHALL write per-species `seed.json` files containing calibrated Grove parameters and a `_yield_table_calibration` metadata block to `data/output/seeds/<species>/`. | MUST |
| FR-GRW-004 | Step 3 SHALL produce calibration diagnostic plots (`.png`) in `data/output/calibration/`. | SHOULD |
| FR-GRW-005 | Step 3 SHALL support yield tables supplied as local CSV or retrieved via the `pylometree` store. | MUST |

### 3.5 Step 4 — Forest Generation

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-FOR-001 | Step 4 SHALL read a forest layout CSV (`x`, `y`, `species`; optional: `z`, `delay`, `fid`, `individual_type`, `target_height_m`, `target_dbh_m`) and simulate all trees with inter-species light competition. | MUST |
| FR-FOR-002 | Step 4 SHALL export per-species USD Nanite assemblies to `data/output/forest/<run>/<species>/`. | MUST |
| FR-FOR-003 | Step 4 SHALL export OBJ/MTL geometry and a Helios++ `scene.xml` for each run. | MUST |
| FR-FOR-004 | Step 4 SHALL export PVE JSON (`pve_*.json`) and a wind animation sidecar (`dynamic_wind.json`) for each run. | MUST |
| FR-FOR-005 | Step 4 SHALL generate Unreal Engine import scripts (`*_unreal_import.py`) for each species. | SHOULD |
| FR-FOR-006 | Step 4 SHALL support `individual_type` column to split trees into independent light-competition groups. | SHOULD |
| FR-FOR-007 | Step 4 SHALL derive per-tree growth cycle counts from `target_height_m`/`target_dbh_m` columns when present. | COULD |

### 3.6 Configuration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-CFG-001 | Pipeline configuration SHALL be expressed in TOML (`config/*.toml`) with per-species and per-preset override support. | MUST |
| FR-CFG-002 | The `growpy-init-config` command SHALL scaffold default `config/*.toml` files from bundled templates. | MUST |
| FR-CFG-003 | All file paths SHALL be resolvable relative to the project root; no hardcoded absolute paths. | MUST |

### 3.7 Tooling and Diagnostics

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-TLS-001 | The pipeline SHALL expose diagnostic tools (`growpy-diagnose-growth`, `growpy-analyze-usda`, `growpy-visualize-tree`) as standalone CLI commands. | SHOULD |
| FR-TLS-002 | The `growpy-ue-exec` tool SHALL support remote Python execution in a running Unreal Engine editor instance. | COULD |
| FR-TLS-003 | The pipeline SHALL emit structured progress logs with `tqdm` progress bars. | SHOULD |

---

## 4. Acceptance Criteria (High-Level)

1. All MUST functional requirements implemented and covered by at least one automated test or manual verification step.
2. Step 4 output USD assemblies load in Unreal Engine 5.7+ with Nanite enabled, without import errors.
3. Calibrated `seed.json` height/DBH values are within ±10% of yield table targets at the specified site index.
4. OBJ/MTL + `scene.xml` pairs are accepted by Helios++ without modification.
5. `--dry-run` exits with code 0 on a valid configuration and non-zero on a misconfigured one.
6. All data-flow contracts in `docs/architecture/data-flow.md` are satisfied between steps.

---

## 5. Constraints

### 5.1 Technical Constraints

| Constraint | Details |
|------------|---------|
| Python 3.12 | Required by `bpy` bundling; earlier versions not supported |
| The Grove 2.3 | Commercial licence required; source tree must be at `src/the_grove_23/` |
| `bpy` isolation | Steps importing `bpy` must run as subprocesses to avoid import conflicts |
| USD format | `usd-core >=23.11`; layer-based instancing used for Nanite assembly |
| Yield tables | German national yield tables only: Fichte Bayern, Buche Braunschweig, Eiche Ungarn |
| License | CC-BY-NC-4.0 — non-commercial use only |

### 5.2 Regulatory / Licence Constraints

- The Grove 2.3 is a commercial tool (thegrove3d.com); distributing its source or presets requires a valid licence.
- All pipeline outputs and source code are released under CC-BY-NC-4.0.
- `pylometree` is sourced from the University of Freiburg GitLab; access requires lab membership.

---

## 6. Assumptions and Dependencies

### 6.1 Assumptions

1. The Grove 2.3 is installed and its source tree is available at `src/the_grove_23/` before Step 1 runs.
2. The `growpy` conda environment is activated; `bpy` is importable within that environment.
3. Forest layout CSVs use the Grove coordinate frame (Z-up, metres).
4. Yield table CSVs or the `pylometree` store are available on the local machine before Step 3 runs.
5. A single researcher or small team runs the pipeline; no concurrent multi-user access is expected.

### 6.2 Dependencies

| Dependency | Version | Role |
|------------|---------|------|
| The Grove 2.3 | 2.3 | Tree growth simulation engine |
| `bpy` | bundled | Blender Python API for `.blend` → USD conversion and Grove simulation |
| `usd-core` | ≥23.11 | USD file I/O and layer composition |
| `pylometree` | git HEAD | Yield table ingestion and allometry helpers |
| `numpy` | ≥1.20 | Numerical array operations |
| `pandas` | ≥1.3 | CSV/tabular data handling |
| `scipy` | ≥1.10 | Chapman-Richards curve fitting |
| `joblib` | ≥1.2 | Parallel step execution |
| `tqdm` | ≥4.60 | Progress reporting |
| Unreal Engine 5.7+ | 5.7+ | Downstream consumer (Nanite/PVE/Wind) |
| Helios++ | — | Downstream LiDAR simulator |

---

## 7. Requirements Traceability

| Requirement ID | Area | Source Module | Status |
|----------------|------|---------------|--------|
| FR-ORC-001 – FR-ORC-006 | Orchestration | `cli/dataset_pipeline.py` | Implemented |
| FR-AST-001 – FR-AST-004 | Asset prep | `cli/prepare_assets.py` | Implemented |
| FR-TWG-001 – FR-TWG-004 | Twig conversion | `cli/convert_twigs.py` | Implemented |
| FR-GRW-001 – FR-GRW-005 | Growth calibration | `cli/create_growth_models.py` | Implemented |
| FR-FOR-001 – FR-FOR-007 | Forest generation | `cli/generate_forest.py` | Implemented |
| FR-CFG-001 – FR-CFG-003 | Configuration | `config/`, `cli/init_config.py` | Implemented |
| FR-TLS-001 – FR-TLS-003 | Tooling | `tools/` | Implemented |

---

## 8. Glossary

| Term | Definition |
|------|------------|
| Forest | Multi-species tree collection with inter-tree light competition, defined by a layout CSV |
| Grove | Species-specific tree group sharing one calibrated growth model; maps to a Grove 2.3 simulation group |
| Tree | Individual tree instance with mesh geometry and skeleton for wind animation |
| Twig | Reusable USD foliage asset (leaves/needles) with Nanite-optimised silhouettes |
| YieldTable | German national forestry yield table providing height/DBH targets at a given site index |
| Seed JSON | Per-species Grove parameter file produced by Step 3; input to Step 4 |
| Nanite | Unreal Engine 5 virtualised geometry system; requires specific USD import settings |
| PVE | Procedural Vegetation Editor — UE 5 system consuming `pve_*.json` sidecar files |
| DBH | Diameter at Breast Height (1.3 m); primary forestry allometric measurement |
| Site Index | Relative productivity index for a forest site, used to select the correct yield table column |
| bpy | Blender's Python API, required for `.blend` → USD twig conversion and Grove simulation |
| Chapman-Richards | Sigmoidal growth function used to fit yield table height/DBH curves |

---

## 9. Appendices

### Appendix A: MoSCoW Prioritization Summary

- **MUST have:** 19 requirements (core pipeline, USD/OBJ/PVE exports, calibration, config)
- **SHOULD have:** 11 requirements (parallelism, dry-run, diagnostics, force-flag)
- **COULD have:** 3 requirements (pilot mode, per-tree cycle derivation, UE remote exec)
- **WON'T have (this release):** Real-time simulation, web interface, Docker packaging

### Appendix B: References

1. ISO/IEC/IEEE 29148:2018 — Systems and software engineering: Life cycle processes — Requirements engineering
2. Chapman-Richards growth function: Richards (1959), Pienaar & Turnbull (1973)
3. The Grove 2.3 documentation: [docs/the_grove/](../the_grove/)
4. Yield table calibration details: [docs/reference/yield-table-calibration.md](../reference/yield-table-calibration.md)
5. Forest CSV schema: [docs/architecture/data-flow.md](../architecture/data-flow.md)

---

## Maintenance

**Last Updated:** 2026-05-11

**Update Triggers:**
- New pipeline steps or CLI commands added
- Forest CSV schema changes (new optional/required columns)
- New downstream consumer integration (beyond UE and Helios++)
- Yield table coverage expanded to new species or national standards
- License or regulatory changes

**Verification:**
- [x] All FR-XXX-NNN requirements have MoSCoW priority
- [x] All requirements traceable to source files in `src/growpy/`
- [x] No unreplaced template markers
- [x] Glossary covers all domain-specific terms used in requirements

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-11 | ln-112-project-core-creator | Initial version |
