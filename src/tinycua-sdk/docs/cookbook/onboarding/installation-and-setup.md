# Installation and Setup

**Prerequisites**: Python 3.12 or later and a terminal.

## Overview

This page walks you through installing the TINYCUA SDK, configuring environment
variables, and verifying that everything works.

The SDK supports two provider paths:

- **Local** — a local LLM server (an OpenAI-compatible endpoint) at
  `http://localhost:1234/v1`. No API key needed.
- **Remote** — OpenAI's API (Responses or Chat Completions endpoint). Requires
  an API key.

You can switch between the two by changing a few lines of configuration.

## Installation

```bash
# pip
pip install tinycua-sdk

# uv
uv pip install tinycua-sdk
```

Inside a project:

```bash
# pip + requirements.txt
echo "tinycua-sdk" >> requirements.txt
pip install -r requirements.txt

# uv + pyproject.toml
uv add tinycua-sdk
```

For development extras (linting, testing):

```bash
pip install "tinycua-sdk[dev]"
```

## Environment Variables

Create a `.env` file in your project root:

```bash
# ── Required for remote providers ──
OPENAI_API_KEY=sk-your-key-here

# ── Model selection (optional) ──
LLM_MODEL=gpt-4o-mini

# ── Local server (optional) ──
# LLM_BASE_URL=http://localhost:1234/v1
```

Load it with `python-dotenv` (install separately: `pip install python-dotenv`):

```python
from dotenv import load_dotenv

load_dotenv()
```

Or set variables inline:

```python
import os

os.environ["OPENAI_API_KEY"] = "sk-your-key-here"
os.environ["LLM_MODEL"] = "gpt-4o-mini"
```

### Key Variables

| Variable | Purpose |
|---|---|
| `LLM_MODEL` | Fallback model when no explicit `model_name` is given |
| `OPENAI_API_KEY` | Default API key for all OpenAI providers |
| `OPENAI_RESPONSES_API_KEY` | Override key for the Responses provider |
| `OPENAI_CHAT_COMPLETIONS_API_KEY` | Override key for Chat Completions |
| `OPENAI_RESPONSES_MODEL` | Default model for Responses provider |
| `OPENAI_CHAT_COMPLETIONS_MODEL` | Default model for Chat Completions |
| `LLM_BASE_URL` | Base URL for the `openai-compatible` provider (e.g., local server) |
| `OPENAI_COMPATIBLE_API_KEY` | Override key for the `openai-compatible` provider |
| `OPENAI_COMPATIBLE_MODEL` | Default model for `openai-compatible` provider |
| `TINYCUA_CACHE_DIR` | Fallback cache directory (used if `cache_dir` is not passed to `Agent`) |

## Verify Installation

```bash
uv run python -c "from tinycua_sdk import Agent; print('SDK installed successfully')"
```

Expected output:

```
SDK installed successfully
```

To check the version:

```bash
uv run python -c "import tinycua_sdk; print(tinycua_sdk.__version__)"
```

## Provider Setup Paths

### Local — Local LLM Server

Start your local server, load a model (e.g., `qwen/qwen3.5-9b`), and enable the local
server on port `1234`. Then:

```python
from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-compatible",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
)

agent = Agent(
    name="local-assistant",
    instructions="You are a helpful assistant.",
    llm_model=model,
)
```

With `LLM_BASE_URL` set in `.env`, omit `base_url`:

```python
from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-compatible",
    model_name="qwen/qwen3.5-9b",
    # base_url read from LLM_BASE_URL env var
)

agent = Agent(
    name="local-assistant",
    instructions="You are a helpful assistant.",
    llm_model=model,
)
```

### Remote — OpenAI

Responses endpoint:

```python
import os

from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="remote-assistant",
    instructions="You are a helpful assistant.",
    llm_model=model,
)
```

Chat Completions endpoint:

```python
import os

from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-chat-completions",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="remote-assistant",
    instructions="You are a helpful assistant.",
    llm_model=model,
)
```

## Common Pitfalls

**Forgetting to load `.env`**. The SDK does not auto-load `.env` files. Always
call `load_dotenv()` early, or set environment variables manually before
importing SDK modules that read them.

**Local server not running**. If the local server is unreachable, the SDK
raises a connection error. Verify your server is running and the port matches your
`base_url` (default `1234`).

**Missing `api_key` for remote providers**. If `api_key` is `None` and
`OPENAI_API_KEY` is not set, calls to `agent.run()` fail with an authentication
error.

## Next Steps

- **[Your First Agent](./your-first-agent.md)** — Create an agent and get your
  first response.