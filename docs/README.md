# GrowPy Documentation

## Quick start

| | |
|---|---|
| [quickstart.md](quickstart.md) | Install, configure, and run the pipeline end-to-end |

## Project Documentation

| Document | What it covers |
|---|---|
| [project/requirements.md](project/requirements.md) | Functional requirements (FR-XXX-NNN) with MoSCoW |
| [project/architecture.md](project/architecture.md) | arc42 system architecture with C4 diagrams |
| [project/tech_stack.md](project/tech_stack.md) | Technology versions, CLI scripts, dev commands |
| [project/infrastructure.md](project/infrastructure.md) | Host requirements, env vars, CLI entry points |
| [principles.md](principles.md) | Development principles and anti-patterns |
| [documentation_standards.md](documentation_standards.md) | Documentation rules and verification requirements |

## Task Management

| Document | What it covers |
|---|---|
| [tasks/README.md](tasks/README.md) | Task workflow, Linear integration, templates |
| [tasks/kanban_board.md](tasks/kanban_board.md) | Live kanban board (Linear XRFF team) |

## ADRs and Guides

| Document | What it covers |
|---|---|
| [reference/README.md](reference/README.md) | Reference hub: ADRs, guides, manuals, research |
| [reference/adrs/adr-001-tree-engine.md](reference/adrs/adr-001-tree-engine.md) | ADR: The Grove 2.3 tree engine selection |
| [reference/adrs/adr-002-usd-pipeline-format.md](reference/adrs/adr-002-usd-pipeline-format.md) | ADR: Pixar USD as pipeline format |
| [reference/adrs/adr-003-conda-environment.md](reference/adrs/adr-003-conda-environment.md) | ADR: conda environment management |
| [reference/guides/01-pipeline-subprocess-pattern.md](reference/guides/01-pipeline-subprocess-pattern.md) | Guide: Pipeline subprocess isolation pattern |

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
