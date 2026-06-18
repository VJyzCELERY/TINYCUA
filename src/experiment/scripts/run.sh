#!/usr/bin/env sh
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"
experiment_dir="$script_dir/.."

usage() {
  printf '%s\n' "Usage: scripts/run.sh [OPTIONS] EXPERIMENT_NUM PROMPT" >&2
  printf '%s\n' "" >&2
  printf '%s\n' "Options:" >&2
  printf '%s\n' "  --overwrite    Replace existing result directories" >&2
  printf '%s\n' "" >&2
  printf '%s\n' "Example: scripts/run.sh 1 \"Make me a simple clock animation app\"" >&2
  printf '%s\n' "Example: scripts/run.sh --overwrite 1 \"Make me a simple clock animation app\"" >&2
  exit 2
}

overwrite=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --overwrite) overwrite="--overwrite"; shift ;;
    -*) printf 'Unknown option: %s\n' "$1" >&2; usage ;;
    *) break ;;
  esac
done

if [ "$#" -lt 2 ]; then
  usage
fi

num="$1"
shift

uv run python "$experiment_dir/run_experiment.py" --num "$num" --prompt "$*" $overwrite