# Auto-generated architecture diagrams

These diagrams are produced statically from the source tree by `pyreverse`
(class + package UMLs) and `code2flow` (function-level call graphs). They
complement the hand-maintained docs in the parent folder
([../pipeline-overview.md](../pipeline-overview.md),
[../module-graph.md](../module-graph.md),
[../module-reference.md](../module-reference.md)).

**Regenerate** any time you change the package layout:

```bash
bash scripts/generate_arch_diagrams.sh
```

The script uses the `growpy` conda environment and writes its output back into
this folder.

## Files

| File | Tool | What it shows |
|---|---|---|
| [classes_growpy.svg](classes_growpy.svg) | `pyreverse` | Class UML for the entire `growpy` package: every class with attributes, methods, and inheritance edges. Best entry point if you're looking for "what classes exist and how do they relate". |
| [packages_growpy.svg](packages_growpy.svg) | `pyreverse` | Module-level dependency graph (which `.py` imports which). The auto-generated equivalent of [../module-graph.md](../module-graph.md). |
| [callgraph_pipeline.svg](callgraph_pipeline.svg) | `code2flow` | Static call graph for the **dataset orchestration** layer: `dataset_pipeline.py` + `core/orchestration/`. Shows which functions in the orchestrator invoke which step-runner / planner functions. |
| [callgraph_core.svg](callgraph_core.svg) | `code2flow` | Static call graph for the **core simulation** layer: `core/forest.py`, `core/grove.py`, `core/tree.py`, `core/skeleton.py`, `core/twig.py`. |
| [callgraph_export.svg](callgraph_export.svg) | `code2flow` | Static call graph for the **export** layer: `io/assembly_export.py`, `io/tree_export.py`, `io/obj_export.py`, `io/helios_scene.py`, `io/wind_json.py`, `io/pve_grove_mapper.py`, `io/unreal_scripts.py`. This is the largest graph and is best viewed full-screen. |

## Caveats

- **`code2flow` is purely static.** It cannot resolve calls made through
  `getattr`, dynamic dispatch, or `subprocess` boundaries. In particular it
  does **not** show the cross-process edges from `step_runner.py` to the
  step scripts — those are documented in [../pipeline-overview.md](../pipeline-overview.md).
- **`bpy`-touching modules** (`io/twig_export.py`, `cli/convert_twigs.py`,
  `cli/generate_forest.py`) are intentionally **not** included in the
  call-graph commands above, because they import `bpy` at module level and
  the call-graph parser sometimes chokes on the resulting indirect calls.
  The class UML and package graph still cover them.
- **Inheritance is shallow** in this codebase — most "classes" are
  dataclasses or single-purpose containers (`PresetOverrides`, `ProfileTimer`,
  `SpeciesGrowthAnalyzer`). The class UML is therefore mostly a compact way
  of seeing field/method lists per module rather than a deep hierarchy.

## Tooling versions used at last regeneration

| Tool | Version | Install command |
|---|---|---|
| `pylint` (provides `pyreverse`) | 4.0.5 | `conda run -n growpy pip install pylint` |
| `code2flow` | latest | `conda run -n growpy pip install code2flow` |
| `graphviz` (`dot`) | 14.1.2 | `mamba install -n growpy -c conda-forge graphviz python-graphviz` |
