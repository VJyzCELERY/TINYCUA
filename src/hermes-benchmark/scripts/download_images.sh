#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Download and load WildClawBench Docker images.
#
# Usage:
#   bash scripts/download_images.sh              # Hermes Agent only (default)
#   bash scripts/download_images.sh --all        # All four harnesses
#   bash scripts/download_images.sh --harness openclaw
#   bash scripts/download_images.sh --harness claudecode
#   bash scripts/download_images.sh --harness codex
#   bash scripts/download_images.sh --harness hermesagent
#
# Requires: pip install -U "huggingface_hub[cli]"
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DOWNLOAD_DIR="${PROJECT_DIR}/Images"
mkdir -p "${DOWNLOAD_DIR}"

# Image definitions: tag tarball
declare -A IMAGES=(
  [openclaw]="wildclawbench-ubuntu_v1.3.tar"
  [claudecode]="wildclawbench-claudecode-ubuntu_v0.2-patched.tar"
  [codex]="wildclawbench-codex-ubuntu_v0.0.tar"
  [hermesagent]="wildclawbench-hermes-agent-v0.5.tar.gz"
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

usage() {
  cat <<'EOF'
Usage: bash scripts/download_images.sh [OPTION]

Options:
  (none)          Download Hermes Agent only (default)
  --all           Download all four harnesses
  --harness NAME  Download a specific harness: openclaw, claudecode, codex, hermesagent
  --list          List available images
  -h, --help      Show this help
EOF
  exit 0
}

list_images() {
  echo "Available images:"
  for key in openclaw claudecode codex hermesagent; do
    echo "  ${key}: ${IMAGES[$key]}"
  done
  echo ""
  echo "Loaded tag for hermesagent: wildclawbench-hermes-agent:v0.5"
}

# Parse args
HARNESS="hermesagent"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      for key in openclaw claudecode codex hermesagent; do
        download_and_load "$key"
      done
      exit 0
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
  echo "Valid options: openclaw, claudecode, codex, hermesagent" >&2
  exit 1
fi

download_and_load "$HARNESS"
echo "==> Image loaded. Verify with: docker images | grep wildclawbench"
