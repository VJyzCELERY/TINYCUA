FROM python:3.12-slim

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /usr/local/bin/uv
COPY src/tinycua-sdk ./tinycua-sdk
COPY src/tinycua ./tinycua
RUN uv pip install --no-cache-dir --system ./tinycua-sdk \
 && uv pip install --no-cache-dir --system ./tinycua

CMD ["sh", "-lc", "tinycua run --prompt \"$EXPERIMENT_PROMPT\" --dir \"${EXPERIMENT_WORKSPACE:-/workspace/experiment-${EXPERIMENT_NUM}}\" --provider-url \"$EXPERIMENT_LLM_BASE_URL\" --api-key \"$EXPERIMENT_LLM_API_KEY\" --model \"$EXPERIMENT_LLM_MODEL\" --provider-type \"${EXPERIMENT_TINYCUA_PROVIDER_TYPE:-openai-chat-completions}\" --timeout \"${EXPERIMENT_TIMEOUT_SECONDS:-900}\""]
