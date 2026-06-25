FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /usr/local/bin/uv

# Install common development tools the agent may need via run_shell.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    jq \
    ripgrep \
    sqlite3 \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY src/tinycua-sdk /app/tinycua-sdk
COPY src/tinycua /app/tinycua
RUN cd /app && uv pip install --no-cache-dir --system ./tinycua-sdk \
 && cd /app && uv pip install --no-cache-dir --system ./tinycua

CMD ["sh", "-lc", "max_ctx_arg=''; if [ -n \"${EXPERIMENT_TINYCUA_MAX_CONTEXT:-}\" ]; then max_ctx_arg=\"--max-context ${EXPERIMENT_TINYCUA_MAX_CONTEXT}\"; fi; recovery_arg=''; if [ -n \"${EXPERIMENT_TINYCUA_RECOVERY_STRATEGY:-}\" ]; then recovery_arg=\"--recovery-strategy ${EXPERIMENT_TINYCUA_RECOVERY_STRATEGY}\"; fi; tinycua run --trace --task-tree --prompt \"$EXPERIMENT_PROMPT\" --dir \"${EXPERIMENT_WORKSPACE:-/workspace/experiment-${EXPERIMENT_NUM}}\" --provider-url \"$EXPERIMENT_LLM_BASE_URL\" --api-key \"$EXPERIMENT_LLM_API_KEY\" --model \"$EXPERIMENT_LLM_MODEL\" --provider-type \"${EXPERIMENT_TINYCUA_PROVIDER_TYPE:-openai-chat-completions}\" --timeout \"${EXPERIMENT_TIMEOUT_SECONDS:-3600}\" $max_ctx_arg $recovery_arg"]