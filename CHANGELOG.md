# Changelog

All notable user-facing changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `.editorconfig` for cross-editor consistency.
- `CONTRIBUTING.md` with contribution workflow.
- `CHANGELOG.md` (this file).
- `docs/reference/package-api.md`: Package API reference with Python examples.
- `docs/reference/testing.md`: Test suite documentation.

### Changed
- `pyproject.toml`: `requires-python` from `>=3.9` to `>=3.12`.
- `environment.yml`: Python version from `3.11` to `3.12`.
- `README.md`: Configuration section updated to reference the user-editable
  `config/` directory and the packaged template layout.
- `src/growpy/README.md` → `docs/reference/package-api.md`: Package API reference.
- `src/growpy/tests/README.md` → `docs/reference/testing.md`: Test suite docs.
- `src/growpy/config/templates/README.md`: Rewritten as brief pointer to
  user-editable `config/` directory.

### Removed
- `.coverage` test coverage artifact removed from version control and added
  to `.gitignore`.
- Stale redirect file `docs/growpy/cli-reference.md` removed; live docs are
  in `docs/cli-reference.md`.
- Empty `src/the_grove_23/groves/` directory removed.

## [0.1.0]

Initial release of the Grove API integration pipeline: procedural forest
generation for Unreal Engine 5.7 Nanite skeletal-mesh assemblies, multi-stage
dataset production, and yield-table calibrated growth models.
