# Tests — growpy

**Last Updated:** 2026-09-15

Automated tests live in **`src/growpy/tests/`** (73 files, pytest discovery via
`pyproject.toml` → `[tool.pytest.ini_options]`, `testpaths = ["src/growpy/tests"]`,
`pythonpath = ["src", "src/the_grove_23/modules"]`). This directory holds only
manual-run scratch:

```
tests/
`-- manual/
    `-- results/     # outputs of manual runs (gitignored)
```

There is no CI (all pipelines are off workspace-wide since 2026-09-01) and no
pre-commit hook; run pytest yourself before committing. The strategy — what is
worth automating, what is not — is in [docs/reference/testing.md](../docs/reference/testing.md).

## Running

Inside the `growpy` conda env (R and Java live there; calling `python.exe`
directly hides them — use `conda run -n growpy` from outside):

```shell
pytest                                             # everything
pytest src/growpy/tests/test_step_runner.py -v     # one file
pytest -k "species or allometry" -v                # by keyword
pytest -n auto                                     # parallel (joblib-heavy tests)
pytest --cov=src --cov-report=term-missing         # coverage
```

## What the suite covers

| Area | Files |
|------|-------|
| Pipeline steps and orchestration | `test_step_runner.py`, `test_orchestration.py`, `test_dataset_pipeline.py` |
| Allometry and tree generation | `test_yield_tables.py`, `test_tree.py`, `test_skeleton.py` |
| USD export and validation | `test_analyze_usda.py`, `test_assembly_export.py`, `test_tree_export.py`, `test_twig_export.py` |
| Species lookup, config, paths, naming | `test_gbif_species.py`, `test_config.py`, `test_paths.py`, `test_naming.py` |

Test business logic, not numpy, pandas or the USD framework.
