# ADR-003: Python Environment Management — conda

**Date:** 2026-05-11 | **Status:** Accepted | **Category:** package_manager | **Decision Makers:** XR Future Forests Lab, Uni Freiburg

<!-- SCOPE: Architecture Decision Record for Python environment management tool selection ONLY. -->
<!-- DO NOT add here: Environment setup steps → docs/quickstart.md, Infrastructure inventory → docs/project/infrastructure.md -->
<!-- DOC_KIND: record -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Read when you need the rationale for using conda instead of venv, poetry, or uv for this project. -->
<!-- SKIP_WHEN: Skip when you already know the setup steps — see docs/quickstart.md. -->
<!-- PRIMARY_SOURCES: docs/project/infrastructure.md, environment.yml, docs/quickstart.md -->

## Quick Navigation

- [Reference Hub](../README.md)
- [Infrastructure](../../project/infrastructure.md)
- [Quickstart](../../quickstart.md)

## Agent Entry

| Signal | Value |
|--------|-------|
| Purpose | Records the decision to use conda as the sole Python environment manager and the constraints that drove this choice. |
| Read When | You need the rationale for conda over venv/poetry/uv. |
| Skip When | You only need setup instructions — see docs/quickstart.md. |
| Canonical | Yes |
| Next Docs | [Infrastructure](../../project/infrastructure.md), [Quickstart](../../quickstart.md) |
| Primary Sources | `environment.yml`, `docs/project/infrastructure.md` |

---

## Context

The pipeline depends on `bpy` (Blender Python API), which bundles USD, MaterialX, OpenImageIO, and a full Blender runtime inside a pip-installable wheel. `bpy` requires CPython at a specific minor version and links against native libraries that conflict with standard `pip` venv toolchains on Windows and Linux. Additionally, `tabula-py` (PDF yield table extraction) requires a Java runtime discoverable via `$PATH`, which conda environments can pin more reliably than pure pip.

---

## Decision

We use conda (via Miniconda or Mamba) with a named `growpy` environment defined in `environment.yml`. pip venv, virtualenv, poetry, and uv are explicitly prohibited for this project. The `pip` subsection of `environment.yml` installs packages unavailable on conda-forge (`bpy`, `pylometree`, `openyieldtables`, `tabula-py`).

---

## Rationale

1. **bpy native library isolation** — `bpy` bundles OpenEXR, USD, and Blender's own Python extensions that conflict with system libraries. conda's isolated prefix prevents DLL/SO collisions that occur in pip venvs on Windows.
2. **Cross-platform reproducibility** — `environment.yml` pins Python to `3.12` and conda-forge packages to compatible versions across Windows, Linux, and macOS; this is the environment used in CI and on developer workstations.
3. **PYTHONPATH injection** — conda environments support `variables:` in `environment.yml`, allowing `PYTHONPATH=./src:./src/the_grove_23/modules` to be set automatically on activation without shell profile edits.

---

## Consequences

**Positive:**
- Single `conda env create -f environment.yml` reproduces the full working environment including bpy, scipy, and all native deps
- Conda handles binary package conflicts that would require manual DLL management in pip venvs
- `conda run -n growpy python ...` enables subprocess invocation of pipeline steps without explicit activation

**Negative:**
- Conda environment is ~2–4 GB (bpy alone is ~1 GB); initial setup is slow
- `mamba` is recommended for faster resolution but requires separate install; `conda` is slower on large environments
- Team members unfamiliar with conda may attempt pip venv — documentation must be explicit about prohibition

---

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| pip + venv | Lightweight, universal, fast | bpy native libraries cause DLL conflicts on Windows; no `variables:` support for PYTHONPATH injection; no binary package index for scipy/numpy pinning | bpy installation fails or produces runtime errors in pure venv on Windows |
| Poetry | Dependency resolution, lock file, pyproject.toml native | Does not solve bpy DLL isolation; no equivalent to conda `variables:`; community reports bpy installation failures under poetry | Does not resolve the core bpy isolation requirement |

---

## Related Decisions

- ADR-001: Tree Engine (bpy dependency originates from The Grove/bpy requirement)
- See `environment.yml` for the canonical dependency list

---

## Maintenance

**Last Updated:** 2026-05-11

**Update Triggers:**
- Python version upgrade
- bpy packaging model changes (e.g., bpy ships its own Python interpreter)
- Team evaluates uv or pixi as conda alternatives

**Verification:**
- [ ] Decision still reflects accepted choice
- [ ] `environment.yml` variables section still works on target platforms
- [ ] Related links resolve
