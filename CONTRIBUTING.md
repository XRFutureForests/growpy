# Contributing

Thanks for your interest in contributing. This project is developed by the
XR Future Forests Lab at the University of Freiburg.

## Ways to contribute

- **Report bugs** via the [GitLab issue tracker](https://gitlab.uni-freiburg.de/xr-future-forests-lab/growpy/-/issues).
- **Suggest features** — especially new species, yield-table integrations, or
  Unreal-side workflow improvements.
- **Submit merge requests** for bug fixes, docs, or pipeline enhancements.
- **Improve documentation** — the 17-file `docs/` tree covers CLI usage,
  dataset specification, yield-table calibration, and Grove API notes.

## License implications

growpy itself is released under **CC BY-NC 4.0** (non-commercial). See
[LICENSE](LICENSE). Note that The Grove 2.3 engine is a separate commercial
product from [thegrove3d.com](https://thegrove3d.com/) and is required at
runtime for tree generation — your usage of growpy must comply with both
licenses.

Contributions are accepted under the same CC BY-NC 4.0 license.

## Development workflow

1. Create the environment: `conda env create -f environment.yml`.
2. Activate: `conda activate growpy`.
3. Install growpy editable: `pip install -e ".[dev,export]"`.
4. Bootstrap user config: `growpy-init-config`.
5. Run tests: `pytest`.
6. Make focused changes — one logical change per merge request.
7. Update `CHANGELOG.md` under `[Unreleased]` for user-visible changes.
8. Open a merge request with a clear description.

## Repository structure

- `src/growpy/` — growpy package source
- `src/the_grove_23/` — vendored Grove 2.3 addon (third-party, do not modify)
- `config/` — user-editable TOML configuration files
- `data/input/` — curated input assets (custom twigs, tables); gitignored for
  generated output
- `docs/` — user and developer documentation
- `src/growpy/tests/` — test suite

## Code style

- **Python**: Black (88 char line length), snake_case, type hints on public
  functions, prefer early returns over nested conditionals.
- **CLI**: each pipeline stage exposes an entry point (`growpy-*`) via
  `[project.scripts]` in `pyproject.toml`.
- `.editorconfig` enforces whitespace conventions.

## Data and artifacts

- Never commit generated trees, preview renders, USD output, or Nanite
  assemblies — all of `data/output/`, `data/assets/`, and `data/tmp/` is
  gitignored.
- `data/input/custom_twigs/` contains committed Blender assets; keep new
  additions small (< 10 MB) or discuss externalization with the maintainer.

## Questions

Open an issue or contact the maintainer.
