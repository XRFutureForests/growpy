# GrowPy

Procedural forest generation pipeline: CSV species/position data → The Grove 2.3 growth simulation → USD Nanite assemblies for Unreal Engine 5.7+. Yield-table-calibrated multi-species light competition. Outputs USD assemblies, PVE JSON, OBJ for Helios++ LiDAR.

<!-- SCOPE: Canonical machine-facing entry point with repo map, critical rules, command overview, and links to detailed documentation ONLY. -->
<!-- DOC_KIND: index -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Start here when you need the project map, local rules, or the next canonical document. -->
<!-- SKIP_WHEN: Skip when you already know the exact target document or code area. -->
<!-- PRIMARY_SOURCES: AGENTS.md, docs/README.md -->

## Quick Navigation

| Need | Read |
|------|------|
| Documentation map | [docs/README.md](docs/README.md) |
| Standards | [docs/documentation_standards.md](docs/documentation_standards.md) |
| Principles | [docs/principles.md](docs/principles.md) |
| Quickstart | [docs/quickstart.md](docs/quickstart.md) |
| Dataset workflow | [docs/guides/dataset-workflow.md](docs/guides/dataset-workflow.md) |
| Forest generation | [docs/guides/forest-generation.md](docs/guides/forest-generation.md) |

## Source Layout

| Path | Contents |
|------|----------|
| `src/growpy/cli/` | argparse entry points for all CLI scripts |
| `src/growpy/core/` | forest.py, tree.py, twig.py, skeleton.py, grove.py |
| `src/growpy/pipelines/` | step_runner.py, forest_stages.py, forest_exports.py, dataset_csv_planner.py |
| `src/growpy/io/usd/` | USD/Nanite exporters |
| `src/growpy/io/unreal/` | PVE JSON, import scripts, wind |
| `src/growpy/io/helios/` | OBJ export, Helios scene XML |
| `src/growpy/config/` | TOML config, species overrides |
| `src/growpy/utils/` | yield tables, analysis, logging, GBIF |
| `src/growpy/tools/` | ue_exec, diagnostics |
| `src/growpy/blender/` | grove_extract, twig_converter |

## CLI Scripts

| Script | Purpose |
|--------|---------|
| `growpy-init-config` | Initialise project TOML config |
| `growpy-prepare-assets` | Prepare input assets |
| `growpy-convert-twigs` | Convert twig meshes via Blender/Grove |
| `growpy-create-models` | Create tree models |
| `growpy-generate-forest` | Run full forest generation pipeline |
| `growpy-dataset-pipeline` | Dataset CSV planning and execution |
| `growpy-ue-exec` | Execute Unreal Engine import scripts |
| `growpy-analyze-usda` | Analyse USD assembly output |
| `growpy-diagnose-growth` | Diagnose growth simulation results |
| `growpy-visualize-tree` | Visualise individual tree output |
| `growpy-sensitivity-analysis` | Run parameter sensitivity analysis |

## Agent Entry

- Purpose: Canonical repo map and routing layer for agents.
- Read when: You need the project overview, local rules, or the next canonical doc.
- Skip when: You already know the exact file or document to inspect.
- Canonical: Yes.
- Read next: `docs/README.md`, then the relevant canonical doc for the task.
- Primary sources: `AGENTS.md`, `docs/README.md`.

## Critical Rules

| Category | Rule | When to Apply |
|----------|------|---------------|
| Confirmation | Never commit or push without explicit user confirmation | Always |
| Scope | Modify only what the request requires — no adjacent cleanup | Always |
| Clarity | State assumptions explicitly; ask when uncertain rather than guessing | Before coding |
| Simplicity | Minimum code that solves the problem — no speculative features | Always |
| Verification | Define success criteria before starting; verify each step | Per task |
| Task tracking | Use Linear MCP for all issue operations — check before creating new issues | Always |
| Language | Keep project code and documentation in English | For all written artifacts |
| Research | Prefer official Python and USD documentation sources | Before stack-specific decisions |

## MCP Tool Preferences

| Need | Preferred flow |
|------|----------------|
| Discover files | `inspect_path` with narrow path |
| Search text | `grep_search(output_mode="summary")`, narrow before content mode |
| Read code | `outline` or targeted `read_file` |
| Edit code | `read_file(edit_ready=true)` → `edit_file(base_revision)` → verify |
| Semantic risk | `index_project` → symbol/architecture analysis |

Use `hex-line` first for repository text reads, search, and edits. Use `hex-graph` first for semantic questions: symbol identity, references, architecture, edit blast radius. Fall back to built-in Read/Edit/Write/Grep/Glob only when MCP is unavailable or task is shell-native.

## Development Commands

| Task | Command |
|------|---------|
| Create conda env | `conda env create -f environment.yml` |
| Activate env | `conda activate growpy` |
| Install (editable) | `pip install -e .` |
| Run tests | `pytest` |
| Format | `black .` |
| Lint | `ruff check .` |

## Maintenance

**Update Triggers:**
- When root navigation or canonical document links change
- When CLI scripts are added or removed
- When core commands change
- When critical project rules change

**Verification:**
- [ ] Links resolve
- [ ] Commands match current project setup
- [ ] CLI script table matches `pyproject.toml` entry points
- [ ] Canonical docs listed here still exist

**Last Updated:** 2026-05-11
