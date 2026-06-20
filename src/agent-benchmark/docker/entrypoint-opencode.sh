#!/bin/bash
# WildClawBench OpenCode Agent Entrypoint — one-shot benchmark execution.
#
# Environment variables:
#   TASK_PROMPT         — Required. The benchmark task prompt.
#   OPENCODE_MODEL      — Model to use (e.g., "anthropic/claude-sonnet-4").
#   LLM_API_BASE        — Custom API base URL (OpenAI-compatible).
#   LLM_API_KEY         — API key for custom providers.
#   LLM_MODEL           — Model name on the custom API.

set -euo pipefail

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY

if [ -z "${TASK_PROMPT:-}" ]; then
    echo "ERROR: TASK_PROMPT not set." >&2
    exit 1
fi

RESULTS="/tmp_workspace/results"
WORKSPACE="/tmp_workspace/workspace"
mkdir -p "${RESULTS}" "${WORKSPACE}"

# Build opencode config for custom OpenAI-compatible provider
API_BASE="${LLM_API_BASE:-http://host.docker.internal:1234/v1}"
API_KEY="${LLM_API_KEY:-lm-studio}"
MODEL_NAME="${LLM_MODEL:-${OPENCODE_MODEL:-${DEFAULT_MODEL:-qwen3.5-9b}}}"
PROVIDER_ID="custom"

# Create opencode.json with custom provider config
cat > /tmp_workspace/opencode.json <<OCEOF
{
  "provider": {
    "${PROVIDER_ID}": {
      "id": "${PROVIDER_ID}",
      "name": "Custom",
      "api": "openai",
      "options": {
        "baseURL": "${API_BASE}",
        "apiKey": "${API_KEY}"
      },
      "models": {
        "${MODEL_NAME}": {
          "id": "${MODEL_NAME}",
          "name": "${MODEL_NAME}"
        }
      }
    }
  },
  "model": "${PROVIDER_ID}/${MODEL_NAME}"
}
OCEOF

# Use the provider/model format for opencode
OPENCODE_MODEL_REF="${PROVIDER_ID}/${MODEL_NAME}"

CMD=(opencode run "${TASK_PROMPT}" --format json --dangerously-skip-permissions)
CMD+=(--model "${OPENCODE_MODEL_REF}")

echo "OpenCode Agent starting..." >&2
echo "Model: ${OPENCODE_MODEL_REF}" >&2
echo "API Base: ${API_BASE}" >&2
echo "Task prompt length: ${#TASK_PROMPT} chars" >&2

cd /tmp_workspace

"${CMD[@]}" 2>"${RESULTS}/stderr.txt" | \
    python3 -c "
import sys, json
events = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        events.append(json.loads(line))
    except json.JSONDecodeError:
        pass
with open('${RESULTS}/transcript.jsonl', 'w') as f:
    for e in events:
        f.write(json.dumps(e) + '\n')
    f.write(json.dumps({'type': 'opencode_summary', 'events_count': len(events)}) + '\n')
print(f'Task completed: {len(events)} events', file=sys.stderr)
"
