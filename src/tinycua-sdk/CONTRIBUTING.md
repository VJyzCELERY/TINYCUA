# Contributing

## Running Tests

```bash
# Run all unit tests
uv run pytest tests/unit/

# Run lint checks
uv run ruff check .

# Run type checks
uv run mypy tinycua_sdk/
```

## Integration Tests

Integration tests talk to a live LLM server. Provider-specific environment
variables (`OPENAI_RESPONSES_*`, `OPENAI_CHAT_COMPLETIONS_*`) take
precedence over generic `LLM_*` fallbacks for base URL, model, and API key.

API keys can be dummy values when using a local compatible server
(e.g., LM Studio). Real API keys are only required when connecting to
the actual OpenAI API.

The committed template `.env.test.example` provides defaults (including
dummy keys) and is auto-loaded by the test suite when no `.env.test` file
exists. To override settings, copy and edit the template:

```bash
cp .env.test.example .env.test
```

Example overrides for local development:

```
OPENAI_RESPONSES_API_KEY=dummy
OPENAI_CHAT_COMPLETIONS_API_KEY=dummy
```

Integration tests are gated by provider reachability and model
configuration — they skip automatically when the LLM server is
unreachable or required model env vars are unset:

```bash
uv run pytest tests/integration/
```
