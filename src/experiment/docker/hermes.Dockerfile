FROM python:3.12-slim

RUN python -m pip install --no-cache-dir --upgrade hermes-agent==0.16.0

CMD ["sh", "-lc", "LM_BASE_URL=\"$EXPERIMENT_LLM_BASE_URL\" LM_API_KEY=\"$EXPERIMENT_LLM_API_KEY\" hermes chat --query \"$EXPERIMENT_PROMPT\" --verbose --yolo --provider \"${EXPERIMENT_HERMES_PROVIDER:-lmstudio}\" --model \"$EXPERIMENT_LLM_MODEL\" --ignore-user-config --ignore-rules --max-turns \"${EXPERIMENT_HERMES_MAX_TURNS:-90}\""]
