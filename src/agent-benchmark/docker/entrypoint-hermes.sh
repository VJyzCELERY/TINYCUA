#!/bin/bash
# WildClawBench Hermes Agent Entrypoint — one-shot benchmark execution.
#
# Environment variables:
#   TASK_PROMPT         — Required. The benchmark task prompt.
#   HERMES_MODEL        — Model to use (e.g., "openrouter/anthropic/claude-sonnet-4").
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

# Configure Hermes for custom provider
MODEL="${HERMES_MODEL:-${DEFAULT_MODEL:-${LLM_MODEL:-}}}"
API_BASE="${LLM_API_BASE:-http://host.docker.internal:1234/v1}"
API_KEY="${LLM_API_KEY:-lm-studio}"

# Set environment variables for hermes lmstudio provider
export LM_BASE_URL="${API_BASE}"
export LM_API_KEY="${API_KEY}"
export OPENROUTER_API_KEY="${API_KEY}"

echo "Hermes Agent starting..." >&2
echo "Model: ${MODEL:-default}" >&2
echo "API Base: ${API_BASE}" >&2
echo "Task prompt length: ${#TASK_PROMPT} chars" >&2

# Write Hermes config
mkdir -p /root/.hermes
cat > /root/.hermes/config.yaml << 'YAMLEOF'
tools:
  profile: coding
  web:
    search:
      enabled: true
      provider: brave
model:
  context_length: 65536
auxiliary:
  compression:
    context_length: 65536
compression:
  enabled: true
  threshold: 0.9
memory:
  memory_enabled: false
YAMLEOF

# Symlink workspace
ln -sfn "${WORKSPACE}" /root/.hermes/workspace 2>/dev/null || true

# Run agent programmatically
python3 -c "
import os, json, sys
sys.path.insert(0, '/opt/hermes')

# Patch minimum context length to allow 4K models
import agent.model_metadata as _mm
import agent.agent_init as _ai
_mm.MINIMUM_CONTEXT_LENGTH = 2048
_ai.MINIMUM_CONTEXT_LENGTH = 2048

from run_agent import AIAgent

task_prompt = '''${TASK_PROMPT}'''
model = '${MODEL}'

# Use lmstudio provider with custom base URL
agent = AIAgent(
    base_url=os.environ.get('LM_BASE_URL', 'http://host.docker.internal:1234/v1'),
    api_key=os.environ.get('LM_API_KEY', 'lm-studio'),
    model=model,
    quiet_mode=True,
    skip_memory=True,
    skip_context_files=True,
    max_iterations=90,
    save_trajectories=True,
)
result = agent.run_conversation(task_prompt)
print(result)
" 2>"${RESULTS}/stderr.txt" > "${RESULTS}/response.txt"

# Find and convert trajectory transcript
TRAJ_DIR="/root/.hermes/logs"
if [ -d "${TRAJ_DIR}" ]; then
    LATEST=$(ls -t "${TRAJ_DIR}"/session_*.json 2>/dev/null | head -1 || true)
    if [ -n "${LATEST}" ]; then
        python3 -c "
import json
with open('${LATEST}') as f:
    session = json.load(f)
with open('${RESULTS}/transcript.jsonl', 'w') as out:
    for msg in session.get('messages', []):
        out.write(json.dumps(msg) + '\n')
"
    fi
fi
