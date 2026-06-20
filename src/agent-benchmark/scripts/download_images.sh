#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Download or build WildClawBench Docker images.
#
# Usage:
#   bash scripts/download_images.sh              # Hermes Agent only (default)
#   bash scripts/download_images.sh --all        # All harnesses
#   bash scripts/download_images.sh --harness openclaw
#   bash scripts/download_images.sh --harness opencode
#   bash scripts/download_images.sh --harness hermesagent
#   bash scripts/download_images.sh --build       # Build all from Dockerfiles
#   bash scripts/download_images.sh --build --harness opencode
#
# Requires: pip install -U "huggingface_hub[cli]" (for --harness downloads)
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DOCKER_DIR="${PROJECT_DIR}/docker"
DOWNLOAD_DIR="${PROJECT_DIR}/Images"
mkdir -p "${DOWNLOAD_DIR}"

# Image definitions: tag -> tarball (for download mode)
declare -A IMAGES=(
  [openclaw]="wildclawbench-ubuntu_v1.3.tar"
  [opencode]="wildclawbench-ubuntu_v1.3.tar"
  [hermesagent]="wildclawbench-hermes-agent-v0.5.tar.gz"
)

# Dockerfile definitions: tag -> dockerfile path (for build mode)
declare -A DOCKERFILES=(
  [openclaw]="Dockerfile.openclaw"
  [opencode]="Dockerfile.opencode"
  [hermesagent]="Dockerfile.hermes"
)

# Image tags assigned after build
declare -A BUILD_TAGS=(
  [openclaw]="wildclawbench-openclaw:latest"
  [opencode]="wildclawbench-opencode:latest"
  [hermesagent]="wildclawbench-hermes-agent:latest"
)

download_and_load() {
  local name="$1"
  local tarball="${IMAGES[$name]}"
  echo "==> Downloading ${name} image: ${tarball}"
  hf download internlm/WildClawBench "Images/${tarball}" \
    --repo-type dataset --local-dir "${PROJECT_DIR}"
  echo "==> Loading into Docker..."
  docker load -i "${DOWNLOAD_DIR}/${tarball}"
  echo "==> Done: ${name}"
  echo ""
}

build_from_dockerfile() {
  local name="$1"
  local dockerfile="${DOCKERFILES[$name]}"
  local tag="${BUILD_TAGS[$name]}"
  local dockerfile_path="${DOCKER_DIR}/${dockerfile}"

  if [[ ! -f "${dockerfile_path}" ]]; then
    echo "ERROR: Dockerfile not found: ${dockerfile_path}" >&2
    return 1
  fi

  echo "==> Building ${name} image from ${dockerfile}..."
  docker build \
    -f "${dockerfile_path}" \
    -t "${tag}" \
    "${PROJECT_DIR}"
  echo "==> Done: ${name} -> ${tag}"
  echo ""
}

usage() {
  cat <<'EOF'
Usage: bash scripts/download_images.sh [OPTION]

Options:
  (none)            Download Hermes Agent only (default)
  --all             Download all harnesses
  --harness NAME    Download/build a specific harness: openclaw, opencode, hermesagent
  --build           Build from Dockerfiles instead of downloading
  --list            List available images
  -h, --help        Show this help

Examples:
  bash scripts/download_images.sh --all                # Download all from HuggingFace
  bash scripts/download_images.sh --build --all        # Build all from Dockerfiles
  bash scripts/download_images.sh --build --harness opencode  # Build OpenCode only
  bash scripts/download_images.sh --harness openclaw   # Download OpenClaw from HuggingFace
EOF
  exit 0
}

list_images() {
  echo "Available images:"
  echo ""
  echo "  Download (from HuggingFace):"
  for key in openclaw opencode hermesagent; do
    echo "    ${key}: ${IMAGES[$key]}"
  done
  echo ""
  echo "  Build (from Dockerfiles):"
  for key in openclaw opencode hermesagent; do
    echo "    ${key}: ${DOCKERFILES[$key]} -> ${BUILD_TAGS[$key]}"
  done
  echo ""
  echo "Loaded tag for openclaw/opencode (download): wildclawbench-ubuntu:v1.3"
  echo "Loaded tag for hermesagent (download): wildclawbench-hermes-agent:v0.5"
}

# Parse args
HARNESS="hermesagent"
BUILD_MODE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      if [[ "${BUILD_MODE}" == "true" ]]; then
        for key in openclaw opencode hermesagent; do
          build_from_dockerfile "$key"
        done
      else
        for key in openclaw opencode hermesagent; do
          download_and_load "$key"
        done
      fi
      exit 0
      ;;
    --build)
      BUILD_MODE=true
      shift
      ;;
    --harness)
      HARNESS="${2:?--harness requires a name}"
      shift 2
      ;;
    --list)
      list_images
      exit 0
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      ;;
  esac
done

if [[ -z "${IMAGES[$HARNESS]+x}" ]]; then
  echo "ERROR: Unknown harness '${HARNESS}'" >&2
  echo "Valid options: openclaw, opencode, hermesagent" >&2
  exit 1
fi

if [[ "${BUILD_MODE}" == "true" ]]; then
  build_from_dockerfile "$HARNESS"
else
  download_and_load "$HARNESS"
fi

echo "==> Verify with: docker images | grep wildclawbench"
