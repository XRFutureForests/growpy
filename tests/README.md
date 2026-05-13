# Test Documentation

**Last Updated:** 2026-05-12

<!-- SCOPE: Test organization structure and Story-Level Test Task Pattern ONLY. Contains test directories organization, test execution commands, quick navigation. -->
<!-- DOC_KIND: index -->
<!-- DOC_ROLE: canonical -->
<!-- READ_WHEN: Read when you need the current test layout, execution commands, or links to test policy. -->
<!-- SKIP_WHEN: Skip when you only need the universal testing philosophy. -->
<!-- PRIMARY_SOURCES: src/growpy/tests/, pyproject.toml, docs/reference/guides/testing-strategy.md -->
<!-- DO NOT add here: Test code -> test files, Story implementation -> docs/tasks/kanban_board.md, Test strategy -> docs/reference/guides/testing-strategy.md -->

## Quick Navigation

- [Testing Strategy](../docs/reference/guides/testing-strategy.md)
- [Task Rules](../docs/tasks/README.md)
- [Kanban Board](../docs/tasks/kanban_board.md)
- [Guides](../docs/reference/guides/)

## Agent Entry

| Signal | Value |
|--------|-------|
| Purpose | Maps the test directories, execution commands, and links to the broader testing policy. |
| Read When | You need to find tests, run them, or understand the local test layout. |
| Skip When | You only need general testing philosophy. |
| Canonical | Yes |
| Next Docs | [Testing Strategy](../docs/reference/guides/testing-strategy.md) |
| Primary Sources | `src/growpy/tests/`, `pyproject.toml` |

---

## Overview

This directory contains manual test scripts and test results infrastructure. Automated tests live in **`src/growpy/tests/`** (configured via `pyproject.toml`) following the **Story-Level Test Task Pattern** — tests are consolidated in the final Story test task rather than scattered across implementation tasks.

---

## Testing Philosophy

**Test your code, not frameworks.** Focus on business logic and integration usage — pipeline step execution, allometry model correctness, USD asset output validity, species lookup behavior. Avoid testing numpy internals, pandas read logic, or USD framework defaults.

**Risk-based testing:** Automate only Priority `>=15` scenarios (`Business Impact x Probability`). Each test should satisfy the usefulness criteria in [testing-strategy.md](../docs/reference/guides/testing-strategy.md).

---

## Test Organization

```
src/growpy/tests/            # Automated test root (configured in pyproject.toml)
|-- test_step_runner.py      # Pipeline step execution
|-- test_tree.py             # Tree generation logic
|-- test_twig.py             # Twig processing
|-- test_assembly_export.py  # USD asset assembly export
|-- test_tree_export.py      # Tree USD export
|-- test_twig_export.py      # Twig USD export
|-- test_analyze_usda.py     # USD asset validation
|-- test_gbif_species.py     # Species lookup (GBIF)
|-- test_yield_tables.py     # Allometry model integration
|-- test_forest.py           # Forest generation pipeline
|-- test_orchestration.py    # Orchestration/pipeline integration
|-- test_dataset_pipeline.py # Dataset pipeline step execution
|-- test_config.py           # Configuration loading and validation
|-- test_naming.py           # Asset naming conventions
|-- test_paths.py            # Path resolution
`-- ... (46 test files total)

tests/                       # Manual tests and infrastructure (this directory)
`-- manual/
    |-- results/             # Test outputs (in .gitignore)
    `-- NN-feature/          # Test suites by Story
        |-- samples/         # Input files
        |-- expected/        # Expected outputs (REQUIRED)
        `-- test-*.sh        # Test scripts
```

**Framework:** pytest (Python 3.11+)
**Naming convention:** `test_*.py` (46 files, standard pytest discovery)
**Test path:** configured in `pyproject.toml` → `[tool.pytest.ini_options]` → `testpaths = ["src/growpy/tests"]`

---

## Story-Level Test Task Pattern

**Rule:** All integration and unit tests for a Story are written in the **final Story test task** created after manual testing.

**Workflow:**
1. Implementation tasks complete.
2. Manual testing runs (scripts in `tests/manual/NN-feature/`) and bugs are fixed.
3. Test planner creates the final Story test task.
4. Test executor adds automated tests to `src/growpy/tests/`.
5. Story is done only after `pytest` passes.

---

## Running Tests

**Run all tests:**

```shell
pytest
```

**Run a single test file:**

```shell
pytest src/growpy/tests/test_step_runner.py -v
```

**Run tests matching a keyword:**

```shell
pytest -k "species or allometry" -v
```

**Run with coverage:**

```shell
pytest --cov=src --cov-report=term-missing
```

**Run with parallel workers (joblib-heavy tests):**

```shell
pytest -n auto
```

> pytest is configured via `pyproject.toml`: `pythonpath = ["src", "src/the_grove_23/modules"]`

---

## Key Test Scenarios

| Scenario | Test File(s) | Priority |
|----------|-------------|----------|
| Pipeline step execution | `test_step_runner.py`, `test_orchestration.py`, `test_dataset_pipeline.py` | High |
| Allometry model integration | `test_yield_tables.py`, `test_tree.py`, `test_skeleton.py` | High |
| USD asset output validation | `test_analyze_usda.py`, `test_assembly_export.py`, `test_tree_export.py`, `test_twig_export.py` | High |
| Species lookup | `test_gbif_species.py` | Medium |
| Config loading | `test_config.py`, `test_paths.py` | Medium |

---

## Maintenance

**Update Triggers:**
- When adding new test files to `src/growpy/tests/`
- When changing pytest configuration in `pyproject.toml`
- When adding new manual test suites under `tests/manual/`
- When modifying Story-Level Test Task Pattern workflow

**Verification:**
- [ ] `src/growpy/tests/` is the configured `testpaths` in `pyproject.toml`
- [ ] `tests/manual/results/` is in `.gitignore`
- [ ] Test execution commands work with current virtual environment
- [ ] Links to testing strategy and task workflow resolve

**Last Updated:** 2026-05-12
