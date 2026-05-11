# Pipeline Subprocess Isolation Pattern

<!-- SCOPE: Pattern documentation for GrowPy's subprocess isolation strategy ONLY. Contains principle, implementation summary, Do/Don't/When patterns. -->
<!-- DO NOT add here: Architectural decisions → ADR-001, Step implementation details → docs/architecture/pipeline-overview.md, CLI flags → docs/reference/cli-reference.md -->
<!-- NO_CODE_EXAMPLES: Guides document PATTERNS, not implementations.
     FORBIDDEN: Full function implementations, class definitions, code blocks > 5 lines
     ALLOWED: Do/Don't/When tables, method signatures (1 line), pseudocode (1-3 lines max)
     INSTEAD OF CODE: Reference real code location, e.g., "See src/growpy/pipelines/step_runner.py:82" -->
<!-- DOC_KIND: reference -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Read when you need to understand why steps run as subprocesses and how to add new pipeline steps safely. -->
<!-- SKIP_WHEN: Skip when you only need CLI flags — see docs/reference/cli-reference.md. -->
<!-- PRIMARY_SOURCES: docs/project/architecture.md, docs/reference/adrs/, src/growpy/pipelines/step_runner.py -->

## Quick Navigation

- [Reference Hub](../README.md)
- [Architecture](../../project/architecture.md)
- [ADRs](../adrs/)

## Agent Entry

| Signal | Value |
|--------|-------|
| Purpose | Captures the subprocess isolation pattern used by GrowPy's 4-step pipeline and the rules for extending it safely. |
| Read When | You need conventions for adding pipeline steps or understanding why bpy forces subprocess isolation. |
| Skip When | You only need a one-off decision record or CLI flags. |
| Canonical | Yes |
| Next Docs | [Architecture](../../project/architecture.md), [ADR-001: Tree Engine](../adrs/adr-001-tree-engine.md), [Pipeline Overview](../../architecture/pipeline-overview.md) |
| Primary Sources | `docs/project/architecture.md`, `src/growpy/pipelines/step_runner.py` |

## Principle

Python processes that import `bpy` (Blender Python API) cannot co-exist in the same process with non-Blender code due to global interpreter state mutations. The standard pattern for bpy-dependent batch pipelines is subprocess isolation: the orchestrator process never imports `bpy`; each step that requires it runs in a dedicated subprocess via `subprocess.run`. Source: [Blender Developer Docs — Python API Overview](https://docs.blender.org/api/current/info_overview.html), 2026.

## Our Implementation

GrowPy's `dataset_pipeline.py` (orchestrator) spawns every step as a subprocess using `step_runner.run_step123()` and `run_species_step4()`. Step 4 (`generate_forest.py`) is the only step that imports `bpy`; Steps 1–3 use the same subprocess pattern for consistency so the orchestrator process remains clean. Parallel Step 4 runs use `ProcessPoolExecutor` (see `src/growpy/pipelines/step_runner.py:170-200`). Each subprocess is invoked inside the `growpy` conda environment via `conda run -n growpy python ...`.

## Patterns

| Do This | Don't Do This | When to Use |
|---------|--------------|-------------|
| Add new steps as separate CLI scripts with an argparse `main()` and register them in `STEP_SCRIPTS` | Import bpy at module level in any file imported by `dataset_pipeline.py` | Adding a new generation or export step |
| Pass file paths between steps via `data/` directories (explicit artefact contracts) | Use shared in-memory objects across subprocess boundaries | Transferring data between pipeline steps |
| Use `subprocess.run(cmd_list, shell=False, check=False)` with an explicit conda prefix | Use `shell=True` with unsanitised species name strings | Invoking any pipeline subprocess on Windows |
| Validate species names against `^[A-Za-z0-9_\- ]+$` before building subprocess commands | Assume species names from CSV are safe shell tokens | When species name originates from user-controlled CSV data |

## Sources

- [Blender Python API — bpy module constraints](https://docs.blender.org/api/current/info_overview.html)
- [Python subprocess docs — security considerations](https://docs.python.org/3/library/subprocess.html#security-considerations)
- Internal: [Pipeline Overview](../../architecture/pipeline-overview.md), `src/growpy/pipelines/step_runner.py`

## Related

**ADRs:** [ADR-001: Tree Engine](../adrs/adr-001-tree-engine.md), [ADR-003: conda Environment](../adrs/adr-003-conda-environment.md)
**Guides:** —

## Maintenance

**Last Updated:** 2026-05-11

**Update Triggers:**
- bpy packaging model changes (e.g., standalone bpy without Blender runtime)
- Pipeline step count changes
- subprocess security guidance updated

**Verification:**
- [ ] Do/Don't/When rows still match current project practice in `step_runner.py`
- [ ] Related links resolve
- [ ] Guidance still references current architecture
