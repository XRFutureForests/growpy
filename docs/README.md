# GrowPy Documentation

## Start here

| Document | What it covers |
|---|---|
| [quickstart.md](quickstart.md) | Install, configure, and run the pipeline end-to-end |
| [guides/dataset-workflow.md](guides/dataset-workflow.md) | Produce the multi-species dataset: config, species selection, growth interval/range, run recipes |
| [guides/forest-generation.md](guides/forest-generation.md) | Build a single forest by hand from your own CSV (the 4-step pipeline) |

## Guides

Task-oriented walkthroughs.

| Document | What it covers |
|---|---|
| [guides/dataset-workflow.md](guides/dataset-workflow.md) | Full dataset production with `dataset_pipeline.py` |
| [guides/forest-generation.md](guides/forest-generation.md) | Manual single-forest run, step by step |
| [guides/unreal-import.md](guides/unreal-import.md) | UE 5.7+ import: drag-drop vs scripts, wind, PVE, Nanite |
| [guides/pve-preset-workflow.md](guides/pve-preset-workflow.md) | Procedural Vegetation Editor preset generation |
| [guides/helios-export.md](guides/helios-export.md) | OBJ/MTL + Helios++ scene XML for LiDAR (secondary feature) |

## Reference

Look-up docs: CLI flags, configuration, Python API, domain concepts.

| Document | What it covers |
|---|---|
| [reference/cli-reference.md](reference/cli-reference.md) | All CLI flags for every script |
| [reference/configuration.md](reference/configuration.md) | Every TOML key + `tree_asset_lookup.csv` columns (incl. `Dataset`) |
| [reference/package-api.md](reference/package-api.md) | Python API for embedding growpy |
| [reference/grove-preset-reference.md](reference/grove-preset-reference.md) | Grove growth parameters and cycle-based curves |
| [reference/pve-attribute-reference.md](reference/pve-attribute-reference.md) | PVE JSON schema and Grove-to-UE mapping |
| [reference/pve-python-api.md](reference/pve-python-api.md) | PVE Python API reference |
| [reference/grove-api-attributes.md](reference/grove-api-attributes.md) | Grove 2.3 API attribute reference |
| [reference/nanite-import-settings.md](reference/nanite-import-settings.md) | UE Nanite import settings and rationale |
| [reference/usd-builder.md](reference/usd-builder.md) | USD export internals (prims, layers, instancing) |
| [reference/yield-table-calibration.md](reference/yield-table-calibration.md) | Yield table calibration math and decision tree |
| [reference/coordinate-systems.md](reference/coordinate-systems.md) | Grove / Blender / USD / Unreal coordinate frames |
| [reference/naming-conventions.md](reference/naming-conventions.md) | Species, file, and directory naming standards |
| [reference/testing.md](reference/testing.md) | Testing framework and coverage |
| [reference/adrs/](reference/adrs/) | Architecture decision records (tree engine, USD format, conda) |
| [reference/guides/01-pipeline-subprocess-pattern.md](reference/guides/01-pipeline-subprocess-pattern.md) | Pipeline subprocess isolation pattern |

## Architecture

How the pipeline is wired and how data flows between steps.

| Document | What it covers |
|---|---|
| [architecture/README.md](architecture/README.md) | Architecture hub |
| [architecture/pipeline-overview.md](architecture/pipeline-overview.md) | 4-step + dataset pipeline as flowcharts |
| [architecture/processing-logic.md](architecture/processing-logic.md) | Per-step algorithm walkthrough |
| [architecture/module-reference.md](architecture/module-reference.md) | Per-module reference: purpose, key functions, inputs, outputs |
| [architecture/module-graph.md](architecture/module-graph.md) | Mermaid dependency graph grouped by layer |
| [architecture/data-flow.md](architecture/data-flow.md) | On-disk artefact contracts between steps |

## Dataset

| Document | What it covers |
|---|---|
| [dataset/dataset-specification.md](dataset/dataset-specification.md) | Species catalogue, asset hierarchy, naming |
| [dataset/dataset-overview.md](dataset/dataset-overview.md) | Production status and preview gallery |

## Project

| Document | What it covers |
|---|---|
| [project/requirements.md](project/requirements.md) | Functional requirements (FR-XXX-NNN) with MoSCoW |
| [project/architecture.md](project/architecture.md) | arc42 system architecture with C4 diagrams |
| [project/tech_stack.md](project/tech_stack.md) | Technology versions, CLI scripts, dev commands |
| [project/infrastructure.md](project/infrastructure.md) | Host requirements, env vars, CLI entry points |
| [principles.md](principles.md) | Development principles and anti-patterns |
| [documentation_standards.md](documentation_standards.md) | Documentation rules and verification requirements |
| [tasks/README.md](tasks/README.md) | Task workflow, Linear integration, templates |
| [tasks/kanban_board.md](tasks/kanban_board.md) | Live kanban board (Linear XRFF team) |

## Internals

Low-level implementation and reverse-engineering notes.

| Document | What it covers |
|---|---|
| [internals/nanite-assembly-readme.md](internals/nanite-assembly-readme.md) | Nanite Assembly USD construction details |
| [internals/pve-json-reverse-engineering.md](internals/pve-json-reverse-engineering.md) | PVE JSON format reverse-engineering notes |

## The Grove 2.3 (vendored upstream reference)

| | |
|---|---|
| [reference/vendor/the-grove/](reference/vendor/the-grove/) | Grove 2.3 core API documentation and website guides (third-party, kept verbatim) |
| [internals/the-grove-addon-analysis/](internals/the-grove-addon-analysis/) | First-party reverse-engineering analysis of the vendored Grove addon (not third-party) |
| [architecture/the-grove-tldr.md](architecture/the-grove-tldr.md) | First-party dev onboarding summary of Grove's architecture |
