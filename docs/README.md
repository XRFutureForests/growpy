# GrowPy Documentation

## Quick start

| | |
|---|---|
| [quickstart.md](quickstart.md) | Install, configure, and run the pipeline end-to-end |

## Guides

Task-oriented walkthroughs for specific workflows.

| Document | What it covers |
|---|---|
| [guides/helios-export.md](guides/helios-export.md) | OBJ/MTL export + Helios++ scene XML for LiDAR simulation |
| [guides/unreal-import.md](guides/unreal-import.md) | UE 5.7+ import: drag-drop vs scripts, wind, PVE, Nanite |
| [guides/pve-preset-workflow.md](guides/pve-preset-workflow.md) | Procedural Vegetation Editor preset generation |

## Architecture

How the pipeline is wired, what each module does, and how data flows between steps.

| Document | What it covers |
|---|---|
| [architecture/pipeline-overview.md](architecture/pipeline-overview.md) | 4-step + dataset pipeline as flowcharts; modules per step |
| [architecture/processing-logic.md](architecture/processing-logic.md) | Per-step algorithm walkthrough with call trees and pseudocode |
| [architecture/module-graph.md](architecture/module-graph.md) | Mermaid dependency graph grouped by layer |
| [architecture/module-reference.md](architecture/module-reference.md) | Per-module reference: purpose, key functions, inputs, outputs |
| [architecture/data-flow.md](architecture/data-flow.md) | On-disk artefact contracts between steps |

## Reference

Look-up docs: CLI flags, Python API, configuration schemas, domain concepts.

| Document | What it covers |
|---|---|
| [reference/cli-reference.md](reference/cli-reference.md) | All CLI flags for every script |
| [reference/package-api.md](reference/package-api.md) | Python API for embedding growpy in other code |
| [reference/grove-preset-reference.md](reference/grove-preset-reference.md) | Grove growth parameters and cycle-based curves |
| [reference/pve-attribute-reference.md](reference/pve-attribute-reference.md) | PVE JSON schema and Grove-to-UE attribute mapping |
| [reference/nanite-import-settings.md](reference/nanite-import-settings.md) | UE Nanite import settings and rationale |
| [reference/usd-builder.md](reference/usd-builder.md) | USD export internals (prims, layers, instancing) |
| [reference/yield-table-calibration.md](reference/yield-table-calibration.md) | Yield table calibration math and decision tree |
| [reference/coordinate-systems.md](reference/coordinate-systems.md) | Grove / Blender / USD / Unreal coordinate frames |
| [reference/naming-conventions.md](reference/naming-conventions.md) | Species, file, and directory naming standards |
| [reference/grove-api-attributes.md](reference/grove-api-attributes.md) | Grove 2.3 API attribute reference |
| [reference/pve-python-api.md](reference/pve-python-api.md) | PVE Python API reference |
| [reference/testing.md](reference/testing.md) | Testing framework and coverage |

## Dataset

| Document | What it covers |
|---|---|
| [dataset/dataset-specification.md](dataset/dataset-specification.md) | Species catalog, layout, and production plan |
| [dataset/dataset-overview.md](dataset/dataset-overview.md) | Production status and preview gallery |
| [dataset/dataset-update-april-2026.md](dataset/dataset-update-april-2026.md) | April 2026 dataset update notes |

## Internals

Low-level implementation notes and reverse-engineering logs.

| Document | What it covers |
|---|---|
| [internals/module-audit.md](internals/module-audit.md) | Flat inventory of every module, including removed files |
| [internals/nanite-assembly-readme.md](internals/nanite-assembly-readme.md) | Nanite Assembly USD construction details |
| [internals/pve-json-reverse-engineering.md](internals/pve-json-reverse-engineering.md) | PVE JSON format reverse-engineering notes |

## The Grove 2.3

| | |
|---|---|
| [the_grove/](the_grove/) | Grove 2.3 core API documentation and website guides |
