#!/bin/bash
# LM Studio Benchmark Container Entry Point
# Validates environment, calls LM Studio API, and executes the benchmark task.
#
# WildClawBench injects TASK_PROMPT via environment variable before container start.

set -euo pipefail

# --- Proxy Cleanup ---
# Unset any proxy settings that might interfere with local API calls
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY

# --- Environment Validation ---

# Required: TASK_PROMPT must be set by WildClawBench
if [ -z "${TASK_PROMPT:-}" ]; then
    echo "ERROR: TASK_PROMPT not set (injected by WildClawBench)." >&2
    exit 1
fi

# Model configuration with defaults
MODEL="${DEFAULT_MODEL:-qwen3.5-9b}"
API_BASE="${LM_STUDIO_API_BASE:-http://host.docker.internal:1234/v1}"
API_KEY="${LM_STUDIO_API_KEY:-lm-studio}"
MAX_TOKENS="${LM_STUDIO_MAX_TOKENS:-4096}"
TEMPERATURE="${LM_STUDIO_TEMPERATURE:-0.0}"

# --- Workspace Validation ---

# Ensure workspace directories exist
mkdir -p /tmp_workspace/results
mkdir -p /tmp_workspace/workspace

# --- Signal Handling ---

cleanup() {
    echo "Received shutdown signal, preserving artifacts..." >&2
    exit 0
}
trap cleanup SIGTERM SIGINT

# --- Execute Benchmark ---

echo "LM Studio Benchmark Container starting..." >&2
echo "Model endpoint: ${API_BASE}" >&2
echo "Model: ${MODEL}" >&2
echo "Task prompt length: ${#TASK_PROMPT} chars" >&2

# Create a Python script to call the LM Studio API and execute the task
cat > /tmp_workspace/run_task.py << 'PYEOF'
#!/usr/bin/env python3
"""LM Studio benchmark task runner."""

import json
import os
import subprocess
import sys
import time
import requests
from pathlib import Path

def call_llm(prompt: str, model: str, api_base: str, api_key: str,
             max_tokens: int = 4096, temperature: float = 0.0) -> str:
    """Call LM Studio OpenAI-compatible API."""
    url = f"{api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=300)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"API call failed: {e}", file=sys.stderr)
        raise

def main():
    task_prompt = os.environ.get("TASK_PROMPT", "")
    model = os.environ.get("DEFAULT_MODEL", "qwen3.5-9b")
    api_base = os.environ.get("LM_STUDIO_API_BASE", "http://host.docker.internal:1234/v1")
    api_key = os.environ.get("LM_STUDIO_API_KEY", "lm-studio")
    max_tokens = int(os.environ.get("LM_STUDIO_MAX_TOKENS", "4096"))
    temperature = float(os.environ.get("LM_STUDIO_TEMPERATURE", "0.0"))

    workspace = Path("/tmp_workspace/workspace")
    results = Path("/tmp_workspace/results")

    print(f"Processing task with model {model}...", file=sys.stderr)

    # Call the LLM with the task prompt
    start_time = time.time()
    try:
        response = call_llm(task_prompt, model, api_base, api_key, max_tokens, temperature)
        elapsed = time.time() - start_time

        # Save the response
        response_file = results / "llm_response.txt"
        response_file.write_text(response)

        # Parse and execute code blocks from the response
        # Look for Python code blocks
        import re
        code_blocks = re.findall(r'```python\n(.*?)```', response, re.DOTALL)

        if code_blocks:
            for i, code in enumerate(code_blocks):
                script_name = workspace / f"script_{i}.py"
                script_name.write_text(code)
                print(f"Extracted script: {script_name}", file=sys.stderr)

                # Try to run the script
                try:
                    result = subprocess.run(
                        [sys.executable, str(script_name)],
                        cwd=str(workspace),
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result.returncode == 0:
                        print(f"Script {script_name} executed successfully", file=sys.stderr)
                    else:
                        print(f"Script {script_name} failed: {result.stderr}", file=sys.stderr)
                except subprocess.TimeoutExpired:
                    print(f"Script {script_name} timed out", file=sys.stderr)

        # Save transcript
        transcript = results / "transcript.jsonl"
        with open(transcript, "w") as f:
            event = {
                "type": "llm_response",
                "model": model,
                "prompt_length": len(task_prompt),
                "response_length": len(response),
                "elapsed_time": elapsed,
                "usage": {
                    "total_tokens": len(response.split())  # rough estimate
                }
            }
            f.write(json.dumps(event) + "\n")

        print(f"Task completed in {elapsed:.1f}s", file=sys.stderr)

    except Exception as e:
        print(f"Task failed: {e}", file=sys.stderr)
        # Save error
        error_file = results / "error.txt"
        error_file.write_text(str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
PYEOF

# Install requests if not available
pip install requests -q 2>/dev/null || true

# Run the task
python3 /tmp_workspace/run_task.py
