# GrowPy Assessment & Remediation Plan

## Context

GrowPy is a ~43k-LOC Python package that drives a 5-stage forest-simulation pipeline (prepare assets → convert twigs → calibrate growth → generate forest → export OBJ). It has evolved rapidly: Grove 2.2 → 2.3 migration (March 2026), `pylometree` extraction (March 2026), removal of `calibrate_growth.py` and `yield_providers.py`. The codebase is generally well-organized but shows accumulated rough edges from this evolution: silent fallbacks in calibration, an asymmetric DBH scaling rule that produces misleading filenames, an absolute Windows path in `pyproject.toml`, a `build_tree_mesh` function with 20 positional arguments, and broad duplication across the CLI layer.

This plan inventories the findings from a functional/algorithmic/structural/quality assessment and organizes remediation into four tranches — ordered by correctness impact first, user-visible improvement second, structural hygiene third, and new features last.

---

## Findings Summary

### HIGH — correctness / reproducibility
1. **DBH radial-scale clamping asymmetry + silent filename mismatch**  
   [`src/growpy/io/forest_export.py:281-292`](src/growpy/io/forest_export.py#L281-L292) — CSV-provided DBH clamped to [0.1, 5.0]×, yield-table DBH clamped to [0.5, 2.0]×. No justification in code; filename uses *post-clamp* DBH so a tree requested at D=1.0 m but clamped to D=0.20 m silently writes `…_D20`. Users lose the target-vs-achieved signal.
2. **Growth-cycle limit is per-grove, not per-tree**  
   `pipelines/forest_stages.py:~50` — `growth_cycle_limit` caps all trees in a grove. In mixed-species groves, short-lived species continue cycling past their target while tall-target trees are clipped too early.
3. **Unclassified twig topology silently defaults to leaf**  
   [`src/growpy/io/helios/obj_export.py:~156`](src/growpy/io/helios/obj_export.py#L156) — a twig USDA with no GeomSubset/material bindings produces **zero stem geometry** in the Helios OBJ export. No warning; the LiDAR sim runs against leaf-only meshes.
4. **Calibration failure is silent**  
   [`src/growpy/utils/yield_tables.py:106-161`](src/growpy/utils/yield_tables.py#L106-L161) — if FPY RMSE exceeds 0.25, falls back to `fpy=1.0` without logging which yield tables were considered or why. Missing / malformed `_yield_table_calibration` block in `seed.json` also silently falls through to uncalibrated Grove.
5. **Non-portable absolute Windows path in `pyproject.toml`**  
   [`pyproject.toml:17`](pyproject.toml#L17) — `pylometree @ file:///D:/Git/pylometree` breaks install on any other machine/OS. Also: `matplotlib`, `scikit-learn`, `pillow`, `openyieldtables`, `bpy`, `tabula-py` are imported but not declared.

### MEDIUM — structural / maintainability
6. **`build_tree_mesh` accepts 20 positional args** ([`src/growpy/io/usd/tree_export.py:71-92`](src/growpy/io/usd/tree_export.py#L71-L92)) — violates project style (<6), callers are fragile.
7. **CLI argparse duplicated across 6–8 scripts** — no shared parser builder; every script re-implements config resolution, logging init, path defaults.
8. **Config loaded as untyped dicts** ([`src/growpy/config/core.py:66-108`](src/growpy/config/core.py#L66-L108)) — `_deep_merge` returns bare `dict`, typos in TOML fail silently, no startup validation.
9. **Height-calibration smoothing skipped for <6 cycles** ([`src/growpy/utils/yield_tables.py:325-326`](src/growpy/utils/yield_tables.py#L325-L326)) — short-lived species get raw oscillating per-cycle scale factors.
10. **Radial scaling assumes uniform radial growth** ([`src/growpy/io/usd/tree_export.py:~340-351`](src/growpy/io/usd/tree_export.py#L340-L351)) — if DBH gap is taper-driven, allometry is violated; crown-taper fudge is geometric, not biological.
11. **`the_grove_23_core` imported directly from ~10 modules** — no abstraction seam; a Grove 2.4 migration will touch every consumer again.
12. **`bpy` imported at module top level in non-Blender CLI scripts** ([`src/growpy/cli/convert_twigs.py:7`](src/growpy/cli/convert_twigs.py#L7), [`src/growpy/cli/generate_forest.py:10`](src/growpy/cli/generate_forest.py#L10)) — defeats the lazy-import pattern already in `__init__.py`.
13. **`environment.yml` ↔ `pyproject.toml` dependency mismatch** — runtime deps only in env.yml; install via `pip install -e .` misses them.
14. **No integration tests for the CLI pipeline** — unit coverage is strong (45 files), but there is no end-to-end test that prepare → convert → calibrate → generate → export runs on a minimal fixture CSV.

### LOW — polish / deferred work
15. **Leaf-area plan** (`memory/leaf_area_plan.md`) is drafted but unimplemented; classification machinery already exists in `obj_export.py` and can be reused on numpy arrays.
16. **Unused Helios leaf-area reuse** — tube/plane classifier exists but is not invoked to emit `leaf_area_summary.csv`.
17. **`paths.py:get_twig_files_by_type`** appends `_twig` to a name that already ends in `_twig`; correct by fallback, wasteful.
18. **`nanite_voxelize_script.py` uses `print()` instead of logging** (12 calls).
19. **`target_edge_factor` deprecated parameter still accepted in `twig_geometry.py`**.
20. **Main `README.md`** is truncated mid-configuration section; no troubleshooting or architecture overview; no ADR directory.

---

## Remediation Tranches

### Tranche 1 — Correctness fixes (low-risk, high-value)

**Goal:** kill the silent-failure modes that produce misleading output.

- **1A. Surface DBH clamp events.** In [`forest_export.py:281-292`](src/growpy/io/forest_export.py#L281-L292), when `tree_radial_scale` hits either clamp boundary, log a WARNING with `(species, tree_id, target_dbh, grove_dbh, raw_scale, clamped_scale)` and keep the *target* DBH in the filename while tagging it with a `_clamped` suffix (or record the miss in a `calibration_report.csv` next to the USD output). Document the asymmetric `[0.1, 5.0]` vs `[0.5, 2.0]` rule inline — the history is that CSV DBH is user-authoritative (may demand large scale) while yield-table DBH is a calibration target (should already be close).
- **1B. Twig geometry validation.** In [`obj_export.py` `_read_twig_mesh_classified`](src/growpy/io/helios/obj_export.py#L54-L156), when the "all faces → leaf" fallback triggers, emit a WARNING with the twig path and face count. Add a unit test with a no-subset USDA fixture asserting the warning.
- **1C. Calibration failure diagnostics.** In [`yield_tables.py:106-170`](src/growpy/utils/yield_tables.py#L106-L170), when FPY estimation fails, log (at DEBUG) the list of yield tables considered, their RMSEs, and the chosen fallback. Add a top-level INFO summary: `"<species>: calibration OK/failed (fpy=X, rmse=Y)"`. Write summary to `data/output/calibration_report.csv`.
- **1D. Strict-mode flag.** Add `[calibration] strict = false` to `growpy.toml`; when `true`, a missing/malformed `_yield_table_calibration` block raises instead of silently falling back.
- **1E. Growth-cycle-limit scope.** Audit `pipelines/forest_stages.py` — change the limit to a per-tree termination check (`tree.height >= target_height OR cycles >= per_tree_cap`) rather than a grove-wide counter. Regression test with a mixed CSV (spruce @ 30 m + beech @ 15 m).

### Tranche 2 — Packaging & portability

**Goal:** make the project installable on any machine, align deps, reduce footguns.

- **2A. Fix `pyproject.toml`.**
  - Replace `pylometree @ file:///D:/Git/pylometree` with `pylometree` (expect it on PATH/PyPI) and document the editable-install workflow in README (`pip install -e D:/Git/pylometree` as a dev step).
  - Add declared runtime deps: `matplotlib`, `scikit-learn`, `pillow`, `openyieldtables`.
  - Move `bpy`, `tabula-py` into `[project.optional-dependencies] blender` / `pdf`.
  - Pin upper bounds conservatively (e.g. `numpy>=1.20,<3`).
- **2B. Reconcile `environment.yml`.** Drop deps that `pyproject.toml` now owns; keep only conda-preferred binaries (Python, compilers).
- **2C. Guard `bpy` imports in CLI.** In [`convert_twigs.py`](src/growpy/cli/convert_twigs.py) and [`generate_forest.py`](src/growpy/cli/generate_forest.py), move `import bpy` behind a function-local import or a `try/except ImportError` at module load that sets `bpy = None`, checked before Blender ops are invoked.

### Tranche 3 — Targeted refactors

**Goal:** reduce the biggest hotspots of duplication and coupling without a ground-up rewrite.

- **3A. `build_tree_mesh` options object.** Introduce `@dataclass TreeMeshOptions` in [`tree_export.py`](src/growpy/io/usd/tree_export.py) grouping the skeleton / material / export-flag parameters. Keep the two non-optional args (`model`, `output_path`) positional; all others move onto the dataclass. Adapt callers in `forest_export.py`, `assembly_export.py`. Net-zero behavior change; the test suite is the safety net.
- **3B. Shared CLI scaffold.** Create `src/growpy/cli/_common.py` exporting:
  - `make_parser(description, epilog) -> ArgumentParser` with `--config`, `--verbose`, `--dry-run` pre-wired.
  - `resolve_config(args) -> GrowPyConfig`.
  - `init_logging(args)`.
  Migrate the 6+ CLI scripts to use it. Saves ~100 LOC and makes adding flags globally trivial.
- **3C. Typed config surface.** Replace the `_deep_merge` dict flow with schema validation. Cheapest route: keep the existing `GrowPyConfig` dataclass, add a `GrowPyConfig.validate()` classmethod that walks known fields and raises on unknown keys (detects TOML typos). Nicer route: pull in `pydantic` for `GrowPyConfig` — but that adds a dep, so only do it if the user wants stricter guarantees.
- **3D. Grove abstraction seam.** Create `src/growpy/_grove_adapter.py` re-exporting the symbols growpy actually uses (`Grove`, `Tree`, `Skeleton`, `manual_prune`, `build_shade_geometry`, …). Change consumer modules to `from growpy._grove_adapter import Grove` instead of `import the_grove_23_core as gc`. A future Grove upgrade becomes a one-file migration.
- **3E. Drop deprecated `target_edge_factor`.** Remove from `twig_geometry.py` signatures and callers (grep shows no live use).

### Tranche 4 — Features & deferred work

- **4A. Leaf-area summary (per existing plan).** Implement the plan in [`memory/leaf_area_plan.md`](C:\Users\Max\.claude\projects\d--Git-growpy\memory\leaf_area_plan.md): reuse the tube/plane classifier on numpy face arrays to compute leaf-only area per twig prototype; multiply by PointInstancer instance counts; write `leaf_area_summary.csv` alongside the Helios OBJ output.
- **4B. Integration smoke test.** Add `src/growpy/tests/integration/test_pipeline_smoke.py`: runs the 4-step pipeline on `data/input/test_single.csv` inside a `tmp_path`, asserts expected USD + OBJ outputs exist. Mark `@pytest.mark.slow`; opt-in via `-m slow`.
- **4C. Per-species config override file.** Support `data/input/species/<species>.toml` that can override any `GrowPyConfig` field for a single species — addresses the "5 files must align to add a species" friction without breaking the global-config model.
- **4D. README + ADRs.** Finish `README.md` (architecture diagram, troubleshooting, dev-install order), create `docs/adr/` with one ADR per major decision already made (Grove 2.3 migration, pylometree split, three-lever DBH calibration, radial-scaling approach).

---

## Critical Files to Modify (by tranche)

| Tranche | File |
|---|---|
| 1A | [`src/growpy/io/forest_export.py:281-292`](src/growpy/io/forest_export.py#L281-L292) |
| 1B | [`src/growpy/io/helios/obj_export.py:~54-156`](src/growpy/io/helios/obj_export.py#L54-L156) |
| 1C/1D | [`src/growpy/utils/yield_tables.py:106-170`](src/growpy/utils/yield_tables.py#L106-L170), [`src/growpy/config/core.py`](src/growpy/config/core.py), [`src/growpy/cli/create_growth_models.py`](src/growpy/cli/create_growth_models.py) |
| 1E | [`src/growpy/pipelines/forest_stages.py`](src/growpy/pipelines/forest_stages.py) |
| 2A–2B | [`pyproject.toml`](pyproject.toml), [`environment.yml`](environment.yml), [`README.md`](README.md) |
| 2C | [`src/growpy/cli/convert_twigs.py:7`](src/growpy/cli/convert_twigs.py#L7), [`src/growpy/cli/generate_forest.py:10`](src/growpy/cli/generate_forest.py#L10) |
| 3A | [`src/growpy/io/usd/tree_export.py:71`](src/growpy/io/usd/tree_export.py#L71), [`src/growpy/io/forest_export.py`](src/growpy/io/forest_export.py), [`src/growpy/io/usd/assembly_export.py`](src/growpy/io/usd/assembly_export.py) |
| 3B | new `src/growpy/cli/_common.py` + all `src/growpy/cli/*.py` |
| 3C | [`src/growpy/config/core.py:66-108`](src/growpy/config/core.py#L66-L108) |
| 3D | new `src/growpy/_grove_adapter.py` + ~10 consumers |
| 4A | [`src/growpy/io/helios/obj_export.py`](src/growpy/io/helios/obj_export.py) |
| 4B | new `src/growpy/tests/integration/test_pipeline_smoke.py` |

---

## Existing Utilities to Reuse

- **Twig tube/plane classifier** (`_read_twig_mesh_classified` in [`obj_export.py`](src/growpy/io/helios/obj_export.py#L54-L156)) — reuse for leaf area (4A) instead of re-deriving.
- **`setup_logging`** in [`src/growpy/utils/log.py`](src/growpy/utils/log.py) — use in the shared CLI scaffold (3B).
- **`GrowPyConfig.from_toml`** in [`config/core.py`](src/growpy/config/core.py) — keep as entry point; add validation alongside (3C).
- **`get_twig_files_by_type`** in [`config/paths.py`](src/growpy/config/paths.py) — works correctly; note the `_twig` double-append quirk in a comment rather than refactoring.

---

## Verification

For each tranche, verify end-to-end before moving on:

- **Tranche 1 (correctness):** run the 4-step pipeline on `data/input/test_quick.csv` (spruce + beech). Check `calibration_report.csv` exists and lists both species. Intentionally break `seed.json` for one species to confirm strict-mode raises (1D). Diff USD filenames before/after to confirm DBH clamp-suffix behavior (1A). Run with a stripped-subset twig fixture to confirm 1B warning fires.
- **Tranche 2 (packaging):** in a fresh conda env: `mamba create -n growpy-verify python=3.11 && mamba activate growpy-verify && pip install -e .` — must succeed with no path-not-found errors. `python -c "import growpy; growpy.cli.prepare_assets"` without `bpy` installed must not ImportError.
- **Tranche 3 (refactor):** full pytest suite must stay green. Byte-diff USD output of `data/input/test_single.csv` before/after `build_tree_mesh` refactor to confirm zero behavior change.
- **Tranche 4 (features):** `growpy-generate-forest --csv data/input/test_quick.csv` produces a `leaf_area_summary.csv` (4A). Integration test runs under `pytest -m slow` in <5 min on CI (4B).

Each tranche is independently mergeable; recommend one PR per tranche, sized 200–600 LOC.
