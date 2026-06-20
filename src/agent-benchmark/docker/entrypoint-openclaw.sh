#!/bin/bash
# WildClawBench OpenClaw Agent Entrypoint — one-shot benchmark execution.
#
# Environment variables:
#   TASK_PROMPT         — Required. The benchmark task prompt.
#   OPENCLAW_MODEL      — Model to use (e.g., "openrouter/openai/gpt-5.5").
#   OPENROUTER_API_KEY  — OpenRouter API key.
#   OPENROUTER_BASE_URL — OpenRouter base URL (default: https://openrouter.ai/api/v1).

set -euo pipefail

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY

if [ -z "${TASK_PROMPT:-}" ]; then
    echo "ERROR: TASK_PROMPT not set." >&2
    exit 1
fi

MODEL="${OPENCLAW_MODEL:-${DEFAULT_MODEL:-}}"
RESULTS="/tmp_workspace/results"
WORKSPACE="/tmp_workspace/workspace"
mkdir -p "${RESULTS}" "${WORKSPACE}"

echo "OpenClaw Agent starting..." >&2
echo "Model: ${MODEL:-default}" >&2
echo "Task prompt length: ${#TASK_PROMPT} chars" >&2

# Write auth profile if API key provided
if [ -n "${OPENROUTER_API_KEY:-}" ]; then
    mkdir -p /root/.openclaw/agents/main/agent
    cat > /root/.openclaw/agents/main/agent/auth-profiles.json << PROJEOF
{
  "profiles": [
    {
      "provider": "openrouter",
      "apiKey": "${OPENROUTER_API_KEY}",
      "baseUrl": "${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}"
    }
  ]
}
PROJEOF
fi

# Set model if provided
if [ -n "${MODEL}" ]; then
    openclaw models set "${MODEL}" 2>/dev/null || true
fi

# Symlink workspace
ln -sfn "${WORKSPACE}" /root/.openclaw/workspace 2>/dev/null || true

# Run agent
openclaw agent --agent main --message "${TASK_PROMPT}" --json --local --timeout 600 \
    2>"${RESULTS}/stderr.txt" > "${RESULTS}/response.json" || true

# Extract transcript from latest session
TRANSCRIPT_DIR="/root/.openclaw/agents/main/sessions"
if [ -d "${TRANSCRIPT_DIR}" ]; then
    LATEST=$(ls -t "${TRANSCRIPT_DIR}"/*.jsonl 2>/dev/null | head -1)
    if [ -n "${LATEST}" ]; then
        cp "${LATEST}" "${RESULTS}/transcript.jsonl"
    fi
fi
