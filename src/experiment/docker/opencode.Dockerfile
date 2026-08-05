FROM node:24-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    jq \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g opencode-ai@1.18.4

CMD ["sh", "-lc", "mkdir -p ~/.config/opencode; printf '%s' '{\"provider\":{\"lmstudio\":{\"npm\":\"@ai-sdk/openai-compatible\",\"name\":\"LM Studio (local)\",\"options\":{\"baseURL\":\"'\"$EXPERIMENT_LLM_BASE_URL\"'\"},\"models\":{\"'\"$EXPERIMENT_LLM_MODEL\"'\":{\"name\":\"'\"$EXPERIMENT_LLM_MODEL\"'\"}}}}}' > ~/.config/opencode/opencode.json; OPENAI_API_KEY=\"$EXPERIMENT_LLM_API_KEY\" opencode run --pure --print-logs --format json --thinking --dangerously-skip-permissions --model \"${EXPERIMENT_OPENCODE_MODEL:-lmstudio/$EXPERIMENT_LLM_MODEL}\" \"$EXPERIMENT_PROMPT\""]
