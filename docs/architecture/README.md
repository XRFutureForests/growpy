# GrowPy Architecture Reference

This folder is the entry point for understanding the **internals** of the GrowPy
package: how the pipeline is wired, what each module is responsible for, what it
takes as input and produces as output, and where to make changes when fixing
bugs or adding features.

If you are looking for *how to use* GrowPy from the command line, see
[../reference/cli-reference.md](../reference/cli-reference.md). If you are looking for
the *historical* functional description, see
[../growpy-functional-description.md](../growpy-functional-description.md). The
documents in this folder focus on **structure and connections**.

## Documents in this folder

| Document | What it covers |
|----------|----------------|
| [pipeline-overview.md](pipeline-overview.md) | The 4-step + dataset orchestration pipeline as Mermaid flowcharts, with the modules each step touches |
| [module-graph.md](module-graph.md) | Module-level dependency graph: who imports who, grouped by layer (cli / core / io / config / utils) |
| [module-reference.md](module-reference.md) | Per-module reference: purpose, key functions/classes, inputs, outputs, and downstream consumers |
| [data-flow.md](data-flow.md) | What data structures flow between steps (CSV schemas, in-memory tree/grove objects, on-disk artefacts) |

## How to read these docs

1. Start with [pipeline-overview.md](pipeline-overview.md) — it gives you the
   "what does the package do, end to end" picture in one page.
2. Then [module-graph.md](module-graph.md) — it tells you which modules form the
   spine of the pipeline and which are leaves.
3. Use [module-reference.md](module-reference.md) as a lookup table when you
   need to know "where does X live" or "what does function Y return".
4. Use [data-flow.md](data-flow.md) when a bug spans two steps and you need to
   understand the on-disk contract between them.

## Companion documents (already in the repo)

- [../internals/module-audit.md](../internals/module-audit.md) — flat inventory of every module,
  including standalone scripts and removed modules (this is the "what files
  exist" doc; the architecture docs here are the "how they work together" doc).
- [../growpy-functional-description.md](../growpy-functional-description.md) —
  long-form prose description of the package's purpose and capabilities.
- [../reference/coordinate-systems.md](../reference/coordinate-systems.md) — how Grove, USD, and
  Unreal coordinate frames map to each other.
- [../reference/yield-table-calibration.md](../reference/yield-table-calibration.md) — the math and
  decision tree behind growth-model calibration.
