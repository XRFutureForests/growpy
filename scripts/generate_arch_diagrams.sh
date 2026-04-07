#!/usr/bin/env bash
# Regenerate the auto-generated architecture diagrams under
# docs/architecture/generated/.
#
# Requires the `growpy` conda environment with `pylint`, `code2flow`, and
# `graphviz` (system `dot`) installed:
#
#     mamba install -n growpy -c conda-forge graphviz python-graphviz
#     conda run -n growpy pip install pylint code2flow
#
# Usage (from the project root):
#     bash scripts/generate_arch_diagrams.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_ROOT/docs/architecture/generated"
SRC="$REPO_ROOT/src/growpy"

CONDA="${CONDA_EXE:-conda}"
RUN="$CONDA run -n growpy"

mkdir -p "$OUT"
cd "$OUT"

echo "[1/4] pyreverse: class + package UML"
$RUN pyreverse -o svg -p growpy --colorized --max-color-depth 6 "$SRC"

echo "[2/4] code2flow: dataset orchestration call graph"
$RUN code2flow --output "$OUT/callgraph_pipeline.svg" --language py \
    "$SRC/cli/dataset_pipeline.py" \
    "$SRC/core/orchestration/step_runner.py" \
    "$SRC/core/orchestration/dataset_csv_planner.py" \
    "$SRC/core/orchestration/dataset_job_planner.py"

echo "[3/4] code2flow: core simulation call graph"
$RUN code2flow --output "$OUT/callgraph_core.svg" --language py \
    "$SRC/core/forest.py" \
    "$SRC/core/grove.py" \
    "$SRC/core/tree.py" \
    "$SRC/core/skeleton.py" \
    "$SRC/core/twig.py"

echo "[4/4] code2flow: export call graph"
$RUN code2flow --output "$OUT/callgraph_export.svg" --language py \
    "$SRC/io/assembly_export.py" \
    "$SRC/io/tree_export.py" \
    "$SRC/io/obj_export.py" \
    "$SRC/io/helios_scene.py" \
    "$SRC/io/wind_json.py" \
    "$SRC/io/pve_grove_mapper.py" \
    "$SRC/io/unreal_scripts.py"

echo "Done. Outputs in: $OUT"
ls -1 "$OUT"
