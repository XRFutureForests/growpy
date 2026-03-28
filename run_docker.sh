#!/usr/bin/env bash
# Launch a resource-limited Jupyter container for growpy.
#
# Usage:
#   ./run_docker.sh              # defaults: 20 cores, 100 GB RAM
#   ./run_docker.sh 10 50        # 10 cores, 50 GB RAM
#
# The container:
#   - Builds from the existing Dockerfile (includes growpy + deps)
#   - Mounts your mesh data and growpy source read-write
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
MESH_DIR="/mnt/data/tj1023/meshes"

echo "=== Building Docker image '${IMAGE_NAME}' ==="
docker build -t "${IMAGE_NAME}" "${GROWPY_DIR}"

echo ""
echo "=== Starting container ==="
echo "  CPUs:   ${CPUS}"
echo "  Memory: ${MEMORY}"
echo "  Port:   ${PORT}"
echo ""

# Remove previous container if it exists
docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

docker run \
    --name "${CONTAINER_NAME}" \
    --cpus="${CPUS}" \
    --memory="${MEMORY}" \
    -p "0.0.0.0:${PORT}:8888" \
    -v "${GROWPY_DIR}:${GROWPY_DIR}" \
    -v "${MESH_DIR}:${MESH_DIR}:ro" \
    -w "${GROWPY_DIR}" \
    -e JUPYTER_TOKEN=growpy \
    "${IMAGE_NAME}"
