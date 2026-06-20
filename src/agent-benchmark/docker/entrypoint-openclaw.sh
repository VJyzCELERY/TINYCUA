#!/bin/bash
# WildClawBench OpenClaw Agent Entrypoint — one-shot benchmark execution.
#
# Uses direct LLM API calls instead of openclaw agent mode to avoid
# context overflow with small-context local models.
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

# Configure provider
API_BASE="${LLM_API_BASE:-http://host.docker.internal:1234/v1}"
API_KEY="${LLM_API_KEY:-lm-studio}"
MODEL_ID="${MODEL##*/}"

# Symlink workspace
ln -sfn "${WORKSPACE}" /root/.openclaw/workspace 2>/dev/null || true

# Write Python runner script
cat > /tmp_workspace/run_task.py << 'PYEOF'
#!/usr/bin/env python3
"""OpenClaw benchmark task runner — direct API calls."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests module not available", file=sys.stderr)
    sys.exit(1)


def call_llm(prompt, model, api_base, api_key, max_tokens=4096, temperature=0.0):
    """Call OpenAI-compatible API."""
    url = f"{api_base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    response = requests.post(url, headers=headers, json=data, timeout=300)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def main():
    task_prompt = os.environ.get("TASK_PROMPT", "")
    model = os.environ.get("LLM_MODEL", os.environ.get("DEFAULT_MODEL", "qwen3.5-9b"))
    api_base = os.environ.get("LLM_API_BASE", "http://host.docker.internal:1234/v1")
    api_key = os.environ.get("LLM_API_KEY", "")
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "4096"))
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0.0"))

    workspace = Path("/tmp_workspace/workspace")
    results = Path("/tmp_workspace/results")

    print(f"Processing task with model {model}...", file=sys.stderr)

    start_time = time.time()
    try:
        response = call_llm(task_prompt, model, api_base, api_key, max_tokens, temperature)
        elapsed = time.time() - start_time

        # Save response
        (results / "llm_response.txt").write_text(response)

        # Parse and execute code blocks
        code_blocks = re.findall(r"```python\n(.*?)```", response, re.DOTALL)
        if code_blocks:
            for i, code in enumerate(code_blocks):
                script = workspace / f"script_{i}.py"
                script.write_text(code)
                print(f"Extracted script: {script}", file=sys.stderr)
                try:
                    result = subprocess.run(
                        [sys.executable, str(script)],
                        cwd=str(workspace),
                        capture_output=True, text=True, timeout=60,
                    )
                    if result.returncode == 0:
                        print(f"Script {script} executed successfully", file=sys.stderr)
                    else:
                        print(f"Script {script} failed: {result.stderr[:200]}", file=sys.stderr)
                except subprocess.TimeoutExpired:
                    print(f"Script {script} timed out", file=sys.stderr)

        # Save transcript
        transcript = results / "transcript.jsonl"
        with open(transcript, "w") as f:
            f.write(json.dumps({
                "type": "llm_response",
                "model": model,
                "provider": api_base,
                "prompt_length": len(task_prompt),
                "response_length": len(response),
                "elapsed_time": elapsed,
                "usage": {"total_tokens": len(response.split())},
            }) + "\n")

        print(f"Task completed in {elapsed:.1f}s", file=sys.stderr)

    except Exception as e:
        print(f"Task failed: {e}", file=sys.stderr)
        (results / "error.txt").write_text(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
PYEOF

# Run the task
python3 /tmp_workspace/run_task.py
exit 0
