#!/usr/bin/env bash
# Hot-swap the hermes-judge container's model/provider without rebuild.
# Assumes the judge container is already running (set up via setup_judge.sh).
# Credentials persist in the judge-hermes-home Docker volume.
set -euo pipefail

cd "$(dirname "$0")/.."

printf '%s\n' "=== Hermes Judge Reconfigure ==="
printf '%s\n' "Launching provider setup TUI (container must be running)…"
printf '%s\n' ""
docker compose exec -it judge hermes setup model

printf '%s\n' ""
printf '%s\n' "Done. Active model now:"
docker compose exec -T judge hermes config show | grep -A2 "◆ Model" || true
printf '%s\n' ""
printf '%s\n' "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf '%s\n' "  Reconfigure complete. Re-run anytime to swap the judge model."
printf '%s\n' "  Full reset (wipe credentials): bash scripts/cleanup_judge.sh"
printf '%s\n' "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"