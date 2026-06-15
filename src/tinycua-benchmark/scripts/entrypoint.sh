#!/bin/bash
# TinyCUA Benchmark Container Entry Point
# Validates environment, configures TinyCUA, and executes the benchmark task.
#
# WildClawBench injects TASK_PROMPT via environment variable before container start.
# See src/tinycua/docs/benchmark/README.md for configuration details.

set -euo pipefail

# --- Environment Validation ---

# Required: TINYCUA_BASE_URL must be set for model endpoint
if [ -z "${TINYCUA_BASE_URL:-}" ]; then
    echo "ERROR: TINYCUA_BASE_URL not set." >&2
    echo "Set TINYCUA_BASE_URL to your OpenAI-compatible model endpoint." >&2
    exit 1
fi

# Required: TASK_PROMPT must be set by WildClawBench
if [ -z "${TASK_PROMPT:-}" ]; then
    echo "ERROR: TASK_PROMPT not set (injected by WildClawBench)." >&2
    exit 1
fi

# Optional: Set defaults for model configuration
export TINYCUA_API_KEY="${TINYCUA_API_KEY:-}"
export TINYCUA_MODEL="${TINYCUA_MODEL:-llama3}"
export TINYCUA_LOG_LEVEL="${TINYCUA_LOG_LEVEL:-INFO}"
export TINYCUA_TIMEOUT="${TINYCUA_TIMEOUT:-300}"

# --- Workspace Validation ---

# Ensure /tmp_workspace exists and is writable
if [ ! -d "/tmp_workspace" ]; then
    echo "ERROR: /tmp_workspace directory not found." >&2
    echo "Mount the task workspace at /tmp_workspace." >&2
    exit 1
fi

if [ ! -w "/tmp_workspace" ]; then
    echo "ERROR: /tmp_workspace is not writable." >&2
    exit 1
fi

# Create results directory for benchmark artifacts
mkdir -p /tmp_workspace/results

# --- Signal Handling ---

# Trap SIGTERM and SIGINT for graceful shutdown
cleanup() {
    echo "Received shutdown signal, preserving artifacts..." >&2
    exit 0
}
trap cleanup SIGTERM SIGINT

# --- Execute Benchmark ---

echo "TinyCUA Benchmark Container starting..." >&2
echo "Model endpoint: ${TINYCUA_BASE_URL}" >&2
echo "Model: ${TINYCUA_MODEL}" >&2
echo "Task prompt length: ${#TASK_PROMPT} chars" >&2

# Pass TASK_PROMPT via environment variable to avoid shell interpretation of
# special characters (quotes, backticks, $ signs) in the prompt string.
# The CLI reads from TASK_PROMPT env var when --prompt is not provided.
export TASK_PROMPT
exec tinycua benchmark run \
    --workspace /tmp_workspace \
    --output /tmp_workspace/results \
    --transcript /tmp_workspace/transcript.jsonl \
    --timeout "${TINYCUA_TIMEOUT}"
