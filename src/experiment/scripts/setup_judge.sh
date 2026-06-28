#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

printf '%s\n' "=== Hermes Judge Setup ==="
printf '%s\n' ""

# Step 1: Build
printf '%s\n' "Building judge Docker image..."
docker compose build judge
printf '%s\n' ""

# Step 2: Start
printf '%s\n' "Starting judge container..."
docker compose up -d judge
sleep 2
printf '%s\n' ""

# Step 3: Interactive provider setup
printf '%s\n' "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf '%s\n' "  Configure the LLM provider for the judge."
printf '%s\n' "  The Hermes setup wizard will appear below."
printf '%s\n' "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf '%s\n' ""
docker compose exec -it judge hermes setup model

printf '%s\n' ""
printf '%s\n' "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf '%s\n' "  Setup complete!"
printf '%s\n' ""
printf '%s\n' "  Test it:"
printf '%s\n' "    docker compose exec judge hermes -p judge -z \"say hello\""
printf '%s\n' ""
printf '%s\n' "  Usage:"
printf '%s\n' "    docker compose exec judge hermes -p judge -z \\"
printf '%s\n' "      \"Evaluate the submission at /workspace/results/...\""
printf '%s\n' ""
printf '%s\n' "  Reconfigure: docker compose exec -it judge hermes setup model"
printf '%s\n' "  Cleanup:     bash scripts/cleanup_judge.sh"
printf '%s\n' "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
