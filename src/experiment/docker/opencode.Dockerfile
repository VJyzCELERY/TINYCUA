FROM node:24-slim

RUN npm install -g opencode-ai

CMD ["sh", "-lc", "mkdir -p ~/.config/opencode; printf '%s' '{\"provider\":{\"lmstudio\":{\"npm\":\"@ai-sdk/openai-compatible\",\"name\":\"LM Studio (local)\",\"options\":{\"baseURL\":\"'\"$EXPERIMENT_LLM_BASE_URL\"'\"},\"models\":{\"'\"$EXPERIMENT_LLM_MODEL\"'\":{\"name\":\"'\"$EXPERIMENT_LLM_MODEL\"'\"}}}}}' > ~/.config/opencode/opencode.json; OPENAI_API_KEY=\"$EXPERIMENT_LLM_API_KEY\" opencode run --model \"${EXPERIMENT_OPENCODE_MODEL:-lmstudio/$EXPERIMENT_LLM_MODEL}\" \"$EXPERIMENT_PROMPT\""]
