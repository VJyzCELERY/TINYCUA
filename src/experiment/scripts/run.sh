#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ "$#" -lt 2 ]; then
  printf '%s\n' "Usage: scripts/run.sh EXPERIMENT_NUM PROMPT" >&2
  printf '%s\n' "Example: scripts/run.sh 1 \"Make me a simple clock animation app in a single HTML file\"" >&2
  exit 2
fi

num="$1"
shift

uv run python run_experiment.py --num "$num" --prompt "$*"
