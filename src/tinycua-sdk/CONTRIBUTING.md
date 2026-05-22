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

Integration tests for the OpenAI Responses provider require
an `OPENAI_API_KEY` environment variable. Copy the example
env file and set your key:

```bash
cp .env.test.example .env.test
```

Edit `.env.test` and set `OPENAI_API_KEY`:

```
OPENAI_API_KEY=sk-...
```

Tests are guarded and will skip automatically when the
environment variable is not set:

```bash
uv run pytest tests/integration/
```
