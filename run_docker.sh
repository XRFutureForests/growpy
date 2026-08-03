#!/usr/bin/env bash
# Launch a resource-limited Jupyter container for growpy.
#
# Usage:
#   ./run_docker.sh                    # defaults: 20 cores, 100 GB RAM
#   ./run_docker.sh 10 50              # 10 cores, 50 GB RAM
#   GROWPY_MESH_DIR=/path/to/meshes ./run_docker.sh
#
# The container:
#   - Builds from the existing Dockerfile (includes growpy + deps)
#   - Mounts growpy source read-write, and GROWPY_MESH_DIR read-only if set
#   - Exposes Jupyter on port 8889
#   - Enforces CPU + RAM limits via Docker cgroups
#
# After launch, open the URL printed in the terminal (http://127.0.0.1:8889/...)

set -euo pipefail

CPUS="${1:-20}"
MEMORY="${2:-100}g"
IMAGE_NAME="growpy-bench"
CONTAINER_NAME="growpy-bench"
PORT=8889

GROWPY_DIR="$(cd "$(dirname "$0")" && pwd)"
# Directory containing large mesh/point-cloud input data, mounted read-only.
# No default -- set per-host, since this is local resource data, not repo content.
MESH_DIR="${GROWPY_MESH_DIR:-}"

echo "=== Building Docker image '${IMAGE_NAME}' ==="
docker build -t "${IMAGE_NAME}" "${GROWPY_DIR}"

echo ""
echo "=== Starting container ==="
echo "  CPUs:   ${CPUS}"
echo "  Memory: ${MEMORY}"
echo "  Port:   ${PORT}"
if [ -n "${MESH_DIR}" ]; then
    echo "  Mesh dir: ${MESH_DIR} (read-only)"
else
    echo "  Mesh dir: not set (export GROWPY_MESH_DIR to mount one)"
fi
echo ""

# Remove previous container if it exists
docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

MOUNT_ARGS=(-v "${GROWPY_DIR}:${GROWPY_DIR}")
if [ -n "${MESH_DIR}" ]; then
    MOUNT_ARGS+=(-v "${MESH_DIR}:${MESH_DIR}:ro")
fi

docker run \
    --name "${CONTAINER_NAME}" \
    --cpus="${CPUS}" \
    --memory="${MEMORY}" \
    -p "0.0.0.0:${PORT}:8888" \
    "${MOUNT_ARGS[@]}" \
    -w "${GROWPY_DIR}" \
    -e JUPYTER_TOKEN=growpy \
    "${IMAGE_NAME}"
