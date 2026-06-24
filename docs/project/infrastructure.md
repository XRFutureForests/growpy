# Infrastructure: GrowPy

<!-- SCOPE: Developer workstation inventory, host requirements, environment setup, Python package sources, CLI entry points, and pipeline integration points. No Docker, no network services. -->
<!-- DO NOT add here: Operational procedures → (no runbook; no containerised deployment), Architecture patterns → ../architecture/pipeline-overview.md, Tech stack versions → tech_stack.md -->
<!-- DOC_KIND: explanation -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Read when you need host setup constraints, environment variables, package sources, or CLI command inventory. -->
<!-- SKIP_WHEN: Skip when you only need pipeline logic, data-flow design, or Unreal Engine import steps. -->
<!-- PRIMARY_SOURCES: environment.yml, pyproject.toml, docs/quickstart.md -->

> **Status:** Active
> **Last Updated:** 2026-05-11

## Quick Navigation

- [Docs Hub](../README.md)
- [Architecture](../architecture/pipeline-overview.md)
- [Quickstart](../quickstart.md)
- [CLI Reference](../reference/cli-reference.md)

## Agent Entry

| Signal | Value |
|--------|-------|
| Purpose | Documents the single-workstation deployment: host requirements, conda environment, env vars, package sources, and CLI entry points. |
| Read When | You need to set up or reproduce the GrowPy environment, or understand what host constraints apply. |
| Skip When | You only need pipeline logic, species calibration details, or Unreal Engine import procedures. |
| Canonical | Yes |
| Next Docs | [Quickstart](../quickstart.md), [Pipeline Overview](../architecture/pipeline-overview.md), [CLI Reference](../reference/cli-reference.md) |
| Primary Sources | `environment.yml`, `pyproject.toml`, `docs/quickstart.md` |

## 1. Server Inventory

GrowPy runs entirely on a single developer workstation — no remote servers, no containerised services.

| Property | Developer Workstation |
|----------|-----------------------|
| **Role** | Local development and pipeline execution |
| **OS** | Windows, Linux, or macOS |
| **Python** | 3.12 (managed via Miniconda / conda) |
| **GPU** | Optional — required only for UE5 Nanite preview in Unreal Engine 5.7+ |
| **Java** | Optional — required only for `tabula-py` PDF yield-table extraction |
| **Conda** | Required (`conda env create -f environment.yml`) |
| **The Grove 2.3** | Commercial license required (thegrove3d.com) |
| **Network** | Outbound access to conda-forge, PyPI, and GitHub/GitLab for initial install |

## 2. Port Allocation

GrowPy exposes no network services and binds no ports. All processing is local CLI / Python API.

## 3. Environment Variables

| Variable | Set In | Value | Purpose |
|----------|--------|-------|---------|
| `PYTHONPATH` | `environment.yml` (`variables:`) | `./src:./src/the_grove_23/modules` | Makes `growpy` package and The Grove 2.3 core modules importable without editable install conflicts |

> `conda activate growpy` applies the `PYTHONPATH` entry automatically via the `variables:` block in `environment.yml`.
> For editable installs outside conda, set it manually: `export PYTHONPATH=./src:./src/the_grove_23/modules`

## 4. Package Sources

| Package | Source | Notes |
|---------|--------|-------|
| `bpy` | PyPI (`pip`) | Blender Python API with bundled USD, MaterialX, OpenImageIO |
| `usd-core >=23.11` | PyPI (`pip`) — optional extra `[export]` | Standalone OpenUSD runtime; install via `pip install -e ".[export]"` |
| `pylometree` | Git — `git+https://github.com/geosense-ufr/pylometree.git` | Volume calculation library from XR Future Forests Lab |
| `tabula-py` | PyPI (`pip`) | PDF yield-table extraction; requires a Java 8+ runtime on `PATH` |
| `openpyxl` | conda-forge | XLSX yield-table parsing (Kohlenstoff-Ertragstafeln) |
| `openyieldtables` | PyPI (`pip`) | Real-world German yield-table calibration data |
| All other deps | conda-forge / defaults | See `environment.yml` for pinned versions |

> The Grove 2.3 core modules (`src/the_grove_23/modules/`) must be obtained separately under commercial license.
> See [The Grove setup guide](../reference/vendor/the-grove/core-api/overview.md).

## 5. CI/CD Pipeline

No CI/CD pipeline is configured. Tests are executed locally:

```shell
conda activate growpy
pytest
```

See `pyproject.toml` `[tool.pytest.ini_options]` for test path configuration (`src/growpy/tests/`).

## 6. CLI Entry Points

Installed by `pip install -e .` (defined in `pyproject.toml` `[project.scripts]`):

| Command | Module | Purpose |
|---------|--------|---------|
| `growpy-init-config` | `growpy.cli.init_config` | Initialise project config |
| `growpy-prepare-assets` | `growpy.cli.prepare_assets` | Prepare twig/mesh assets |
| `growpy-convert-twigs` | `growpy.cli.convert_twigs` | Convert twig geometry |
| `growpy-create-models` | `growpy.cli.create_growth_models` | Build yield-table growth models |
| `growpy-generate-forest` | `growpy.cli.generate_forest` | Run full forest generation pipeline |
| `growpy-dataset-pipeline` | `growpy.cli.dataset_pipeline` | Execute dataset processing pipeline |
| `growpy-ue-exec` | `growpy.tools.ue_exec` | Unreal Engine execution helper |
| `growpy-analyze-usda` | `growpy.tools.analyze_usda` | Inspect generated USDA files |
| `growpy-diagnose-growth` | `growpy.tools.diagnose_growth` | Diagnose growth simulation issues |
| `growpy-visualize-tree` | `growpy.tools.visualize_tree` | Visualise single-tree output |
| `growpy-sensitivity-analysis` | `growpy.cli.sensitivity_analysis` | Run parameter sensitivity analysis |

## 7. Host Requirements

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| **Python** | 3.12 | Managed via conda; see `environment.yml` |
| **Conda** | Any current Miniconda/Anaconda | Required for env + PYTHONPATH injection |
| **Disk** | ~2 GB for env | `bpy` wheel is large (~500 MB); USD outputs vary by forest size |
| **RAM** | 8 GB | 16 GB recommended for large multi-species forests |
| **GPU** | Optional | Only needed for UE5 Nanite preview rendering |
| **Java** | Optional (8+) | Required only if using `tabula-py` for PDF yield-table extraction |
| **The Grove 2.3** | Commercial license | Obtain from thegrove3d.com; place modules in `src/the_grove_23/modules/` |

## 8. Downstream Integration Points

| System | Interface | Reference |
|--------|-----------|-----------|
| Unreal Engine 5.7+ | USD Nanite assemblies (`.usda` / `.usdz`) | [Unreal Import Guide](../guides/unreal-import.md) |
| Helios++ | OBJ meshes + XML scene files | [Helios Export Guide](../guides/helios-export.md) |
| `pylometree` | Python API (volume calculations) | [Package API](../reference/package-api.md) |
| `digital-twin-db` | CSV species/position input data | [Dataset Overview](../dataset/dataset-overview.md) |

## Maintenance

**Update Triggers:**
- `environment.yml` or `pyproject.toml` dependency changes
- The Grove 2.3 version upgrade
- New CLI entry points added to `pyproject.toml`
- PYTHONPATH or conda variable changes
- New downstream integration targets

**Verification:**

```shell
# Confirm environment activates and packages resolve
conda activate growpy
python -c "import growpy; print('OK')"

# Confirm CLI entry points are installed
growpy-generate-forest --help

# Confirm USD export optional extra
python -c "from pxr import Usd; print(Usd.GetVersion())"

# Confirm pylometree git source resolves
python -c "import pylometree; print('OK')"
```

---
**Owner:** ln-115-devops-docs-creator
**Contact:** XR Future Forests Lab, Uni Freiburg — maximilian.sperlich@gmail.com
