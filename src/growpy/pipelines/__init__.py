"""Multi-step pipeline orchestration for GrowPy.

Sibling package to `core/` (simulation primitives) and `io/` (file-format
exporters). Modules here implement multi-step workflows that glue together
simulation + export + file planning. They have no argparse code of their
own -- CLI front-ends in `growpy.cli.*` are thin wrappers that parse
arguments and dispatch into these functions.

Modules:
    forest_stages       Pipeline A: height-threshold snapshot exports.
    forest_exports      Pipeline B: standard cycle-based forest exports.
    step_runner         Generic multi-step pipeline runner with state.
    dataset_csv_planner Dataset generation CSV planning helpers.
    dataset_job_planner Dataset generation job planning helpers.

This package intentionally does not re-export symbols at the top level --
import from the specific module you need.
"""
