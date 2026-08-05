FROM node:24-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    jq \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g openclaw@2026.7.1-2

CMD ["sh", "-lc", "mkdir -p ~/.openclaw; searxng_base=\"${SEARXNG_BASE_URL%/search}\"; printf '%s' '{\"tools\":{\"profile\":\"full\",\"web\":{\"search\":{\"provider\":\"searxng\"}}},\"plugins\":{\"entries\":{\"searxng\":{\"enabled\":true,\"config\":{\"webSearch\":{\"baseUrl\":\"'\"$searxng_base\"'\"}}}}},\"agents\":{\"list\":[{\"id\":\"main\",\"default\":true,\"workspace\":\"'\"$EXPERIMENT_WORKSPACE\"'\",\"experimental\":{\"localModelLean\":true}}],\"defaults\":{\"sandbox\":{\"mode\":\"off\"},\"model\":{\"primary\":\"local/'\"$EXPERIMENT_LLM_MODEL\"'\"},\"models\":{\"local/'\"$EXPERIMENT_LLM_MODEL\"'\":{\"alias\":\"local\"}},\"memorySearch\":{\"enabled\":false}}},\"models\":{\"mode\":\"merge\",\"providers\":{\"local\":{\"baseUrl\":\"'\"$EXPERIMENT_LLM_BASE_URL\"'\",\"apiKey\":\"'\"$EXPERIMENT_LLM_API_KEY\"'\",\"timeoutSeconds\":'\"${EXPERIMENT_OPENCLAW_PROVIDER_TIMEOUT_SECONDS:-600}\"',\"api\":\"openai-completions\",\"models\":[{\"id\":\"'\"$EXPERIMENT_LLM_MODEL\"'\",\"name\":\"'\"$EXPERIMENT_LLM_MODEL\"'\",\"input\":[\"text\"],\"reasoning\":true,\"contextWindow\":128000,\"contextTokens\":120000}]}}}}' > ~/.openclaw/openclaw.json; openclaw agent --local --agent main --session-key \"agent:main:experiment-${EXPERIMENT_NUM}\" --message \"$EXPERIMENT_PROMPT\" --model \"${EXPERIMENT_OPENCLAW_MODEL:-local/$EXPERIMENT_LLM_MODEL}\" --thinking \"${EXPERIMENT_OPENCLAW_THINKING:-off}\" --verbose on --timeout \"${EXPERIMENT_TIMEOUT_SECONDS:-14400}\""]
