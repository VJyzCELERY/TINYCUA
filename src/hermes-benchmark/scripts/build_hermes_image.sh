#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Build Hermes Docker image with layer caching.
# Usage:
#   bash scripts/build_hermes_image.sh
#
# Uses Docker's build cache to avoid rebuilding unchanged layers.
# Expected image size: ~5GB.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="${IMAGE_NAME:-hermes-agent}"
DOCKERFILE="${DOCKERFILE:-${PROJECT_DIR}/docker/Dockerfile.hermes}"

echo "==> Building Hermes Docker image: ${IMAGE_NAME}"
echo "    Dockerfile: ${DOCKERFILE}"
echo "    Context:    ${PROJECT_DIR}"
echo ""

docker build \
    --file "${DOCKERFILE}" \
    --tag "${IMAGE_NAME}" \
    --cache-from "${IMAGE_NAME}:latest" \
    "${PROJECT_DIR}"

echo ""
echo "==> Build complete. Image: ${IMAGE_NAME}"
echo "    Run 'docker run --rm ${IMAGE_NAME} --help' to verify."
