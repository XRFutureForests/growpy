# Codebase Audit — Final Report: `growpy`

**Run:** codebase-audit-20260610-091208
**Scope:** `D:/Git/growpy/src/growpy` (Python 3.11+ src-layout package). Excluded: `.conda` vendored env, `*.mypy_cache`, `__pycache__`, and vendored `src/the_grove_23`.
**Coordinator:** ln-620 · **Workers:** ln-621 … ln-629 (all 9 executed)
**Date:** 2026-06-10

## Executive Summary

`growpy` is a local, single-process CLI/batch pipeline (field data → growth models → procedural trees → USD/Unreal export). It has **no network, database, or HTML surface**, so classic web-security and service-lifecycle risk is largely N/A — and the concurrency model is genuinely well-built (spawn-safe picklable workers, `__main__` guards on all entry points, deliberate avoidance of cross-process write races).

The real risk is **engineering hygiene that will block reliable delivery and slow maintenance**, concentrated in three places:

1. **The delivery gate is broken and unenforced.** `pytest` collection aborts with a native crash; `ruff` reports 186 errors (including 4 latent `NameError`s); there is no CI workflow and no pre-commit.
2. **Maintainability is the weakest category.** 20 functions exceed cyclomatic complexity 40, and five modules run 1,700–2,300 lines.
3. **The dependency manifest is incomplete** — `scipy`, `matplotlib`, and `Pillow` are imported but undeclared, so a clean `pip install` cannot run the analysis/plotting/texture features.

**Overall verdict: NEEDS WORK.** No critical security exposure, but the test gate must be fixed and CI stood up before this can be trusted to ship changes safely.

### Category Scorecard

| Worker | Category | Score | C | H | M | L |
|--------|----------|------:|--:|--:|--:|--:|
| ln-621 | Security boundary | 9.5 | 0 | 0 | 1 | 0 |
| ln-622 | Build & delivery gate | 5.5 | 1 | 2 | 1 | 0 |
| ln-623 | Duplication & over-abstraction | 9.3 | 0 | 0 | 1 | 1 |
| ln-624 | Maintainability hotspots | 2.0 | 0 | 7 | 2 | 0 |
| ln-625 | Dependency & reuse | 7.8 | 0 | 1 | 2 | 1 |
| ln-626 | Dead code | 8.4 | 0 | 0 | 2 | 2 |
| ln-627 | Diagnosability | 9.3 | 0 | 0 | 1 | 1 |
| ln-628 | Concurrency | 9.8 | 0 | 0 | 0 | 1 |
| ln-629 | Runtime lifecycle & config | 9.0 | 0 | 0 | 2 | 0 |
| **Total** | | | **1** | **10** | **12** | **6** |

29 findings total. Research basis: PyPA pip-audit, 2026 Python tooling guidance (ruff/mypy/CI), joblib/multiprocessing official docs, supply-chain best practice (see `research-evidence.md`).

## Prioritized Remediation Plan

**P0 — Restore the delivery gate (do first; everything else rides on it)**
1. Fix the pytest collection crash (I1) — make USD/bpy imports lazy so the suite is collectable headless.
2. Fix the 4 `F821` undefined-name bugs (I2) — these are latent runtime `NameError`s.
3. Stand up CI (ruff + mypy + pytest) and pre-commit (I3); add `[tool.ruff]`/`[tool.mypy]` config (I4).

**P1 — Make the package installable and honest**
4. Declare `scipy`, `matplotlib`, `Pillow` (I5); pin the `pylometree` git dependency (I6).

**P2 — Pay down maintainability**
5. Refactor the worst CC>40 functions and split the 1,700–2,300-line god modules (I7); adopt a CC budget (ruff `C901`).

**P3 — Cleanup & robustness**
6. Auto-fix dead code (I8), harden `shell=True` subprocess calls (I9), add config validation (I10), route library `print()` through the logger (I11), declare optional extras (I12), bound worker thread oversubscription (I13).

## Consolidated Issue Register

| ID | Sev | Category | Location | Issue | Action | Fix | Effort | Acceptance |
|----|-----|----------|----------|-------|--------|-----|--------|------------|
| I1 | CRITICAL | Delivery gate (ln-622) | tests/test_assembly_export.py:6 → io/usd/assembly_export.py:45 → utils/pxr_init.py:21 | `pytest` collection aborts with native fault `0xc0000139` when `import bpy` runs at import time; not catchable by `except ImportError`, so the whole suite can't run. | FIX_DELIVERY_GATE | Make bpy/pxr import lazy (inside functions) or skip module when bpy absent; ensure headless collection. | M | `pytest --co -q` exits 0 |
| I2 | HIGH | Delivery gate (ln-622) | io/usd/tree_export.py:880 (`species_name`); io/usd/twig_export.py:805 (`rename_prim_recursive`), :1424 (`textures_dir`); blender/operators.py:309 (`unregister` F811) | 4 undefined-name + redefinition errors = latent `NameError` at runtime on those code paths. | FIX_DELIVERY_GATE | Define/scope the missing names; remove shadowed `unregister`. | S–M | `ruff check --select F821,F811` clean |
| I3 | HIGH | Delivery gate (ln-622) | `.github/` (no workflows); repo root (no `.pre-commit-config.yaml`) | No CI and no pre-commit; lint/type/test signals never enforced. | FAIL_CI_ON_SIGNAL | Add GitHub Actions (ruff+mypy+pytest, fail on non-zero) and pre-commit. | M | CI runs and gates PRs |
| I4 | MEDIUM | Delivery gate (ln-622) | pyproject.toml:20-21 | ruff/black declared but no `[tool.ruff]`/`[tool.mypy]` config → inconsistent behavior. | FIX_DELIVERY_GATE | Add tool config blocks to pyproject. | S | Config present; `ruff`/`mypy` run from pyproject |
| I5 | HIGH | Dependency (ln-625) | pyproject.toml:12-18 vs utils/analysis.py:19, utils/plotting.py:6, io/usd/texture_utils.py:22 | `scipy`, `matplotlib`, `Pillow` imported at module level but undeclared → clean install raises `ImportError`. | PATCH_DEPENDENCY | Add to dependencies (or a viz/analysis extra). | S | `pip install` in clean env imports all modules |
| I6 | MEDIUM | Dependency (ln-625) | pyproject.toml:17 | `pylometree @ git+…` unpinned (tracks HEAD) → non-reproducible, supply-chain risk. | PATCH_DEPENDENCY | Pin to commit SHA or tag. | S | Dependency has explicit `@<rev>` |
| I7 | HIGH | Maintainability (ln-624) | twig_export.py:1237 (CC110), pipelines/forest_stages.py:86 (CC90), config/core.py:279 (CC82), io/usd/assembly_export.py:89 (CC79), io/unreal/pve_grove_mapper.py:917 (CC71); god modules twig_export.py(2302), tree_export.py(1923), unreal_scripts.py(1916), pve_grove_mapper.py(1729), assembly_export.py(1694); 20 functions CC>40 total | Systemic complexity makes the export path hard to test/change. | REFACTOR_HOTSPOT | Decompose top functions into stage helpers; split god modules; adopt CC budget (`ruff C901`/radon gate). | L | Top offenders < CC 30; modules split; CC gate enforced |
| I8 | MEDIUM | Dead code (ln-626) | 45 F841 unused vars (twig_export 13, assembly_export 10, …); 93 F401 unused imports; F811 dup `unregister` | Discarded computed values may mask bugs; large cleanup surface. | DELETE_DEAD_CODE | Review F841 in exporters (intentional?), then `ruff --fix` F401/F841; enforce in gate. | M | `ruff --select F401,F841` clean |
| I9 | MEDIUM | Security (ln-621) | pipelines/step_runner.py:82, :146 | `subprocess.run(conda_cmd, shell=True)` interpolates CSV/species-derived paths into cmd.exe; shell metacharacters in names could inject. Local/internal-data only. | HARDEN_SECURITY_BOUNDARY | Drop `shell=True`; resolve conda via `shutil.which`/`CONDA_EXE` and pass the arg list directly. | S | No `shell=True`; pipeline still runs |
| I10 | MEDIUM | Lifecycle/config (ln-629) | config/core.py:279-410 + path fields | Misspelled/unknown TOML keys silently dropped (defaults used); required input paths not validated at startup → fail late. | ADD_CONFIG_VALIDATION | Schema-validate keys (warn/raise on unknown); add `validate()` for path existence/writability at boot. | M | Unknown key warns/errors; missing path fails fast |
| I11 | MEDIUM | Diagnosability (ln-627) | utils/gbif_species.py, pipelines/sensitivity_pipeline.py, cli/create_growth_models.py, tools/* (~60 host-side `print()`) | Library/pipeline modules bypass the central `growpy` logger; output not level-filterable/redirectable. | STRUCTURE_LOGS | Replace host-side `print()` in library/pipeline code with `logger.*`; keep UE-embedded script prints. | M | Library code uses logger; verbose/quiet honored |
| I12 | MEDIUM | Duplication (ln-623) | tools/ue_exec.py:49,120 and io/unreal/unreal_scripts.py:161,179 | `_get_gpu_vram` / `_vram_bar` (and RAM helpers) duplicated host-side. | MERGE_DUPLICATION | Extract `growpy/utils/resource_monitor.py`; import in both. | M | Single shared implementation |
| I13 | LOW | Concurrency (ln-628) | utils/analysis.py:972, pipelines/step_runner.py:183 | `ProcessPoolExecutor` × numpy/scipy BLAS threads → CPU oversubscription (perf only). | CONTROL_ASYNC_SIDE_EFFECT | Set `OMP_NUM_THREADS=1` etc. in worker env, or document max_workers trade-off. | S | Throughput stable on many-core host |
| I14 | LOW | Dependency (ln-625) | tools/ue_exec.py:77, io/unreal/unreal_scripts.py:87 (psutil); utils/gbif_species.py:40 (pygbif) | Optional deps undeclared even as extras → silent feature degradation. | PATCH_DEPENDENCY | Declare optional-dependencies extras. | S | Extras documented |
| I15 | LOW | Dead code (ln-626) | core/forest.py:290,735; config/core.py:388; config/pve_species_overrides.py:132 | Legacy/backward-compat branches with no removal timeline. | REMOVE_OBSOLETE_COMPAT | Confirm unused, remove or document removal version. | M | Branches removed or scheduled |
| I16 | LOW | Maintainability (ln-624) | io/usd exporters | Raw `dict`/`tuple` returns + inline magic thresholds (constants.py underused). | SIMPLIFY_SIGNATURE / EXTRACT_CONSTANT | TypedDict/dataclass results; centralize tuning literals. | M | Typed results; literals in constants |
| I17 | LOW | Dependency (ln-625) | pyproject.toml:12-22 | `>=` floors, no lock file → non-reproducible installs. | PATCH_DEPENDENCY | Add uv.lock / pinned requirements for CI. | M | Lock file committed |

## Deduplication & Conflict Notes

- **F401/F841 (unused imports/vars)** surfaced in both ln-622 (as a delivery-gate signal, I3 context) and ln-626 (as deletion actions, I8). Per `codebase_audit_worker_boundaries.md`, ln-622 owns the gate, ln-626 owns the deletion — kept as one register entry (I8) with the gate cross-reference.
- **F821/F811** appear in ln-622 (gate) and ln-626 (the dead duplicate `unregister`). Consolidated: I2 owns the undefined-name bugs; the dead-definition cleanup is folded into I2/I8.
- **`shell=True` / subprocess** appeared in ln-621 (security, I9) and was visible to ln-628; ln-628 correctly classified it as security, not concurrency. No double-count.
- **env defaults**: ln-629 owns startup config validation (I10); ln-621 found no sensitive defaults — no overlap.
- **Duplication vs hotspots**: ln-623 owns the `_get_gpu_vram` duplication (I12); ln-624 kept only local complexity (I7). No double-count.

## Warnings / Open Questions

- The pytest crash (I1) was observed in the local `growpy` conda env (bpy DLL `0xc0000139`); it may be partly environment-specific, but the import-time `bpy` load is a real structural fragility regardless. Full test pass/fail counts could not be obtained.
- MCP Ref was unavailable this session; research used Context7 (joblib) + web best-practice + official PyPA docs (recorded `completed_minimal`).

## Cleanup Note

Temporary per-worker markdown reports removed after consolidation into this final report:
- `audit-report/ln-621--global.md`
- `audit-report/ln-622--global.md`
- `audit-report/ln-623--principles.md`
- `audit-report/ln-624--quality.md`
- `audit-report/ln-625--global.md`
- `audit-report/ln-626--global.md`
- `audit-report/ln-627--global.md`
- `audit-report/ln-628--global.md`
- `audit-report/ln-629--global.md`

Retained: this final report, all `evaluation-worker/*.json` summaries, `manifest.json`, and `research-evidence.md`.
