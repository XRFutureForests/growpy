# Changelog

All notable user-facing changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `.editorconfig` for cross-editor consistency.
- `CONTRIBUTING.md` with contribution workflow.
- `CHANGELOG.md` (this file).

### Changed
- `pyproject.toml`: `pylometree` dependency now points to the GitLab
  repository via `git+https` rather than an absolute local Windows path.
- `README.md`: Configuration section updated to reference the user-editable
  `config/` directory and the packaged template layout.

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
