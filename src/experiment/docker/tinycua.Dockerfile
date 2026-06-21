FROM python:3.12-slim

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /usr/local/bin/uv

# Install common development tools the agent may need via run_shell.
# curl/wget: fetching URLs, downloading dependencies
# git: version control, cloning repos
# jq: JSON parsing (useful for API responses)
# ripgrep: fast content search (agent can use via run_shell)
# sqlite3: the agent builds SQLite databases in experiment-4
# build-essential/pkg-config: compiling C extensions for pip packages
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

COPY src/tinycua-sdk ./tinycua-sdk
COPY src/tinycua ./tinycua
RUN uv pip install --no-cache-dir --system ./tinycua-sdk \
 && uv pip install --no-cache-dir --system ./tinycua

CMD ["sh", "-lc", "tinycua run --prompt \"$EXPERIMENT_PROMPT\" --dir \"${EXPERIMENT_WORKSPACE:-/workspace/experiment-${EXPERIMENT_NUM}}\" --provider-url \"$EXPERIMENT_LLM_BASE_URL\" --api-key \"$EXPERIMENT_LLM_API_KEY\" --model \"$EXPERIMENT_LLM_MODEL\" --provider-type \"${EXPERIMENT_TINYCUA_PROVIDER_TYPE:-openai-chat-completions}\" --timeout \"${EXPERIMENT_TIMEOUT_SECONDS:-3600}\""]