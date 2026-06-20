#!/bin/bash
# WildClawBench OpenClaw Agent Entrypoint — one-shot benchmark execution.
#
# Environment variables:
#   TASK_PROMPT         — Required. The benchmark task prompt.
#   LLM_API_BASE        — Custom API base URL (OpenAI-compatible).
#   LLM_API_KEY         — API key for custom providers.
#   LLM_MODEL           — Model name on the custom API.

set -euo pipefail

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY

if [ -z "${TASK_PROMPT:-}" ]; then
    echo "ERROR: TASK_PROMPT not set." >&2
    exit 1
fi

MODEL="${LLM_MODEL:-${DEFAULT_MODEL:-}}"
RESULTS="/tmp_workspace/results"
WORKSPACE="/tmp_workspace/workspace"
mkdir -p "${RESULTS}" "${WORKSPACE}"

echo "OpenClaw Agent starting..." >&2
echo "Model: ${MODEL:-default}" >&2
echo "Task prompt length: ${#TASK_PROMPT} chars" >&2

# Configure custom provider via openclaw config patch
API_BASE="${LLM_API_BASE:-http://host.docker.internal:1234/v1}"
API_KEY="${LLM_API_KEY:-lm-studio}"
MODEL_NAME="${MODEL:-qwen/qwen3.5-9b}"

# Create config patch with provider and models (models must be array)
cat > /tmp/openclaw-patch.json5 << EOF
{
  "models": {
    "mode": "merge",
    "providers": {
      "custom": {
        "baseUrl": "${API_BASE}",
        "apiKey": "${API_KEY}",
        "contextWindow": 16384,
        "models": [
          {
            "id": "${MODEL_NAME}",
            "name": "${MODEL_NAME}",
            "api": "openai-completions",
            "contextWindow": 16384,
            "maxTokens": 4096
          }
        ]
      }
    }
  }
}
EOF

openclaw config patch --file /tmp/openclaw-patch.json5 2>&1 || true

# Symlink workspace
ln -sfn "${WORKSPACE}" /root/.openclaw/workspace 2>/dev/null || true

# Run agent with custom model
openclaw agent --agent main --message "${TASK_PROMPT}" --json --local --timeout 600 \
    --model "custom/${MODEL_NAME}" \
    2>"${RESULTS}/stderr.txt" > "${RESULTS}/response.json" || true

# Extract transcript from latest session
TRANSCRIPT_DIR="/root/.openclaw/agents/main/sessions"
if [ -d "${TRANSCRIPT_DIR}" ]; then
    LATEST=$(ls -t "${TRANSCRIPT_DIR}"/*.jsonl 2>/dev/null | head -1)
    if [ -n "${LATEST}" ]; then
        cp "${LATEST}" "${RESULTS}/transcript.jsonl"
    fi
fi
