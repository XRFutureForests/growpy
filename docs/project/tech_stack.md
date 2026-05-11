# Technology Stack: GrowPy

**Document Version:** 1.0
**Date:** 2026-05-11
**Status:** Active

<!-- SCOPE: Technology stack (specific versions, libraries, tools, naming conventions) ONLY. -->
<!-- DOC_KIND: reference -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Read when you need exact technologies, versions, tooling, or tool installation details. -->
<!-- SKIP_WHEN: Skip when you only need business scope or runtime procedures. -->
<!-- PRIMARY_SOURCES: pyproject.toml, environment.yml, docs/reference/adrs/ -->

<!-- DO NOT add here: API endpoints → docs/reference/package-api.md, Architecture patterns → architecture.md, Requirements → requirements.md, Pipeline procedures → docs/architecture/pipeline-overview.md -->

## Quick Navigation

- [Docs Hub](../README.md)
- [Requirements](requirements.md)
- [Architecture](architecture.md)
- [Quickstart](../quickstart.md)

## Agent Entry

| Signal | Value |
|--------|-------|
| Purpose | Lists the actual stack, versions, tooling, and rationale for selected technologies in GrowPy. |
| Read When | You need exact framework, library, runtime, or tool choices. |
| Skip When | You only need workflow instructions or feature scope. |
| Canonical | Yes |
| Next Docs | [Architecture](architecture.md), [Quickstart](../quickstart.md) |
| Primary Sources | `pyproject.toml`, `environment.yml`, `docs/reference/adrs/` |

---

## 1. Introduction

### 1.1 Purpose

This document specifies the technology stack, libraries, and development tools used in GrowPy. It is the single source of truth for version constraints, rationale, and tooling setup.

### 1.2 Scope

GrowPy is a Python-only offline batch pipeline. There is no frontend, no web server, and no database.

**IN SCOPE:** Python runtime, tree simulation engine, 3D/USD libraries, data-science dependencies, build tooling, code quality tools.
**OUT OF SCOPE:** Infrastructure provisioning, deployment procedures (no Docker/k8s), API contracts, database schema.

---

## 2. Technology Stack

### 2.1 Stack Overview

| Layer | Technology | Version | Rationale |
|-------|------------|---------|-----------|
| **Runtime** | Python (conda env `growpy`) | 3.12 | Required by `bpy` bundling and `usd-core` compatibility |
| **Tree simulation** | The Grove 2.3 | 2.3 (commercial) | Only tool producing botanically realistic procedural trees with skeleton/wind support |
| **Blender API** | `bpy` (bundled via pip) | bundled with Grove env | Required for driving The Grove 2.3 and converting `.blend` twig files to USD |
| **USD I/O** | `usd-core` | ≥23.11 | Native UE 5 Nanite pipeline; layer-based instancing for assembly |
| **Allometry** | `pylometree` | git HEAD | University of Freiburg yield table store and Chapman-Richards fitting helpers |
| **Numerics** | `numpy` | ≥1.20 | Array operations across forest positions and growth curves |
| **Tabular data** | `pandas` | ≥1.3 | Forest CSV ingestion and yield table manipulation |
| **Curve fitting** | `scipy` | ≥1.10 | Chapman-Richards `scipy.optimize` fitting for calibration |
| **Parallelism** | `joblib` | ≥1.2 | Parallel Step 4 execution across species |
| **Progress** | `tqdm` | ≥4.60 | Per-step and per-species progress bars |
| **Packaging** | `setuptools` + `pyproject.toml` | setuptools ≥45 | Standard Python packaging; console-script entry points |
| **Testing** | `pytest` | ≥7.0 | Unit and integration tests in `src/growpy/tests/` |
| **Formatting** | `black` | ≥22.0 (88-char line length) | Deterministic code formatting |
| **Linting** | `ruff` | ≥0.0.250 | Fast Python linting (replaces flake8/isort) |
| **Downstream (UE)** | Unreal Engine 5.7+ | 5.7+ | Nanite, PVE, Wind animation consumers |
| **Downstream (LiDAR)** | Helios++ | — | OBJ/MTL + scene XML LiDAR simulation |

### 2.2 Key Libraries and Dependencies

**Core simulation dependencies (from `pyproject.toml` `[project.dependencies]`):**

| Library | Version Constraint | Purpose |
|---------|-------------------|---------|
| `numpy` | ≥1.20.0 | Forest position arrays, growth curve data |
| `pandas` | ≥1.3.0 | CSV ingestion, yield table tabular data |
| `tqdm` | ≥4.60.0 | CLI progress reporting |
| `joblib` | ≥1.2.0 | Parallel species processing |
| `pylometree` | git (Uni Freiburg GitLab) | Yield table store, allometry helpers |

**Optional dependencies (from `pyproject.toml` `[project.optional-dependencies]`):**

| Group | Library | Version | Purpose |
|-------|---------|---------|---------|
| `dev` | `pytest` | ≥7.0.0 | Test runner |
| `dev` | `black` | ≥22.0.0 | Code formatter |
| `dev` | `ruff` | ≥0.0.250 | Linter |
| `export` | `usd-core` | ≥23.11 | USD file I/O (required for Steps 2 and 4) |

**Not in `pyproject.toml` (provided by conda env):**

| Library | Source | Purpose |
|---------|--------|---------|
| `bpy` | bundled via pip in conda env | Blender Python API for Grove simulation and `.blend` → USD |
| `scipy` | conda / pip | Chapman-Richards curve fitting (install: `pip install scipy>=1.10`) |

### 2.3 Console Scripts

Defined in `pyproject.toml [project.scripts]` — all entry points in `src/growpy/cli/` or `src/growpy/tools/`:

| Command | Module | Purpose |
|---------|--------|---------|
| `growpy-init-config` | `cli.init_config:main` | Scaffold `growpy.toml` from bundled templates |
| `growpy-prepare-assets` | `cli.prepare_assets:main` | Step 1: mirror Grove assets |
| `growpy-convert-twigs` | `cli.convert_twigs:main` | Step 2: `.blend` → USD foliage |
| `growpy-create-models` | `cli.create_growth_models:main` | Step 3: yield-table calibration |
| `growpy-generate-forest` | `cli.generate_forest:main` | Step 4: Grove simulation + export |
| `growpy-dataset-pipeline` | `cli.dataset_pipeline:main` | Full 4-step orchestrator |
| `growpy-ue-exec` | `tools.ue_exec:main` | UE remote Python execution |
| `growpy-analyze-usda` | `tools.analyze_usda:main` | USD assembly inspection |
| `growpy-diagnose-growth` | `tools.diagnose_growth:main` | Growth calibration diagnostics |
| `growpy-visualize-tree` | `tools.visualize_tree:main` | Per-tree mesh visualisation |
| `growpy-sensitivity-analysis` | `cli.sensitivity_analysis:main` | Grove parameter sensitivity |

---

## 3. Environment Setup

No Docker image is provided. The pipeline requires a local conda environment.

### 3.1 Required Tools

| Tool | Version | Purpose | Installation |
|------|---------|---------|--------------|
| Miniconda / Anaconda | Latest | Conda environment manager | https://docs.conda.io/en/latest/miniconda.html |
| Python | 3.12 (via conda) | Runtime | Managed by `environment.yml` |
| The Grove 2.3 | 2.3 | Tree simulation engine (commercial) | https://www.thegrove3d.com/ |
| Git | 2.40+ | Version control | https://git-scm.com/ |

### 3.2 Environment Creation and Installation

```shell
# Create conda environment
conda env create -f environment.yml

# Activate
conda activate growpy

# Install growpy package (editable)
pip install -e .

# Install USD support
pip install -e ".[export]"
```

### 3.3 Recommended IDE

VS Code with the Python extension. No project-level `.vscode/` settings are committed. Use the `growpy` conda interpreter.

---

## 4. Development Tools

### 4.1 Linters and Code Quality

| Tool | Version | Purpose | Command | Config |
|------|---------|---------|---------|--------|
| `black` | ≥22.0 | Code formatting (88-char) | `black .` | `pyproject.toml` (implicit) |
| `ruff` | ≥0.0.250 | Linting (replaces flake8/isort) | `ruff check .` | `pyproject.toml [tool.ruff]` |
| `pytest` | ≥7.0 | Test runner | `pytest` | `pyproject.toml [tool.pytest.ini_options]` |

**Run all quality checks:**

```shell
black . && ruff check . && pytest
```

**CI/CD:** No CI pipeline is configured at time of writing. Quality checks are run manually before merging.

### 4.2 Test Configuration

From `pyproject.toml [tool.pytest.ini_options]`:

```toml
pythonpath = ["src", "src/the_grove_23/modules"]
testpaths = ["src/growpy/tests"]
```

Tests live alongside the source in `src/growpy/tests/`. See `docs/reference/testing.md` for coverage and test strategy.

---

## 5. Naming Conventions

### 5.1 File and Module Naming

| Artefact | Convention | Example |
|----------|-----------|---------|
| Python modules | `snake_case` | `forest_stages.py`, `yield_tables.py` |
| CLI scripts | `snake_case` verbs | `prepare_assets.py`, `generate_forest.py` |
| Config files | `snake_case` or `kebab-case` | `growpy.toml`, `tree_asset_lookup.csv` |
| Doc files | `kebab-case` | `pipeline-overview.md`, `yield-table-calibration.md` |
| USD output files | `<species>_<role>.usda` | `norway_spruce_foliage_skeletal.usda` |
| Species directories | `kebab-case` | `norway-spruce/`, `european-beech/` |

### 5.2 Variable and Function Naming

| Context | Convention |
|---------|-----------|
| Variables and functions | `snake_case` |
| Classes | `PascalCase` |
| Constants | `UPPER_SNAKE_CASE` |
| Private helpers | `_leading_underscore` (omitted from public API docs) |

### 5.3 Species Naming

Species identifiers are normalised via GBIF lookup and stored in `config/tree_asset_lookup.csv`. The canonical form is the full Latin binomial in Title Case (e.g., `Norway Spruce`). Directory and file names use `kebab-case` equivalents (e.g., `norway-spruce`). See `docs/reference/naming-conventions.md` for the full standard.

---

## Maintenance

**Last Updated:** 2026-05-11

**Update Triggers:**
- Major/minor version upgrade to any core dependency
- New library added to `pyproject.toml` or `environment.yml`
- New console script registered
- Python runtime version change
- New downstream consumer tool added

**Verification:**
- [x] All versions match `pyproject.toml` and `environment.yml`
- [x] Console script table matches `pyproject.toml [project.scripts]`
- [x] No unreplaced template markers
- [x] Naming conventions consistent with `docs/reference/naming-conventions.md`

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-11 | ln-112-project-core-creator | Initial version |
