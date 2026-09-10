# docs — growpy

Reference and workflow detail. Start with [README.md](../README.md) for what growpy is, and
[RUNBOOK.md](../RUNBOOK.md) for the pipeline end to end.

## Guides — doing a thing

| Document | Contents |
|----------|----------|
| [guides/dataset-workflow.md](guides/dataset-workflow.md) | Full multi-species dataset production |
| [guides/forest-generation.md](guides/forest-generation.md) | A single forest run from your own CSV |
| [guides/pve-preset-workflow.md](guides/pve-preset-workflow.md) | Procedural Vegetation Editor integration |
| [guides/unreal-import.md](guides/unreal-import.md) | Getting assemblies into Unreal |
| [guides/helios-export.md](guides/helios-export.md) | OBJ + scene XML for Helios++ LiDAR simulation |

## Reference — looking a thing up

| Document | Contents |
|----------|----------|
| [reference/cli-reference.md](reference/cli-reference.md) | Every CLI flag |
| [reference/configuration.md](reference/configuration.md) | All TOML keys and species-lookup CSV columns |
| [reference/module-reference.md](reference/module-reference.md) | Package modules and their responsibilities |
| [reference/module-graph.md](reference/module-graph.md) | Import graph |
| [reference/package-api.md](reference/package-api.md) | Public Python API |
| [reference/usd-builder.md](reference/usd-builder.md) | How USD stages are assembled |
| [reference/coordinate-systems.md](reference/coordinate-systems.md) | Axis and unit conventions across the pipeline |
| [reference/naming-conventions.md](reference/naming-conventions.md) | Asset and file naming |
| [reference/nanite-import-settings.md](reference/nanite-import-settings.md) | Unreal-side import settings |
| [reference/grove-api-attributes.md](reference/grove-api-attributes.md) | Grove API attributes used |
| [reference/grove-preset-reference.md](reference/grove-preset-reference.md) | Grove preset parameters |
| [reference/crown-parameter-response.md](reference/crown-parameter-response.md) | How crown parameters respond |
| [reference/pve-attribute-reference.md](reference/pve-attribute-reference.md) | PVE attributes |
| [reference/pve-python-api.md](reference/pve-python-api.md) | PVE Python API |
| [reference/testing.md](reference/testing.md) | Test suite layout and coverage |

## Internals

| Document | Contents |
|----------|----------|
| [internals/nanite-assembly-readme.md](internals/nanite-assembly-readme.md) | How a Nanite assembly is structured |
| [internals/pve-json-reverse-engineering.md](internals/pve-json-reverse-engineering.md) | The PVE JSON format, as reverse-engineered |

## Dataset

| Document | Contents |
|----------|----------|
| [dataset/dataset-specification.md](dataset/dataset-specification.md) | Species catalogue and the full spec |
| [dataset/dataset-overview.md](dataset/dataset-overview.md) | What the dataset contains and how it is organised |

---

Design rationale — why The Grove, why USD, the crown-density calibration record, the
yield-table calibration study, and the Grove API analysis — lives in the XR Future Forests Lab
knowledge hub under `04-LOGIC-TIER/growpy*` and `99-RESOURCES/vendor/the-grove/`. The Grove's
own product documentation is not redistributed here; see
[thegrove3d.com](https://www.thegrove3d.com).
