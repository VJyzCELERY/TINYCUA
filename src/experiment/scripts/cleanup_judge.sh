#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

printf '%s\n' "=== Hermes Judge Cleanup ==="
printf '%s\n' ""

# Stop, remove container AND volume in one go
printf '%s\n' "Stopping judge and removing data..."
docker compose down -v judge 2>/dev/null || true

# Verify volume is gone
if docker volume ls | grep -q judge-hermes-home; then
  printf '%s\n' "⚠ Volume may still exist. Removing manually..."
  docker volume rm experiment_judge-hermes-home 2>/dev/null || true
  docker volume rm src-experiment_judge-hermes-home 2>/dev/null || true
else
  printf '%s\n' "✓ Credentials volume removed."
fi

# Optionally remove the Docker image
printf '%s\n' ""
read -r -p "Remove the judge Docker image as well? [y/N] " response
if [[ "$response" =~ ^[Yy]$ ]]; then
  docker rmi experiment-judge 2>/dev/null || true
  printf '%s\n' "Image removed."
else
  printf '%s\n' "Image kept. Remove later with: docker rmi experiment-judge"
fi

printf '%s\n' ""
printf '%s\n' "Judge cleaned up."
printf '%s\n' "To set up again: bash scripts/setup_judge.sh"
