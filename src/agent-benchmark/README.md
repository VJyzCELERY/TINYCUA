# agent-benchmark

WildClawBench — benchmark 3 coding agents (OpenClaw, OpenCode, HermesAgent) on the same tasks.

## Quick Start

```bash
# 1. Start your LLM server (any of these, or your own)
lms server start          # LM Studio (port 1234)
ollama serve              # Ollama (port 11434)
vllm serve <model>        # vLLM (port 8000)
# ...or any server on any port
```

> Docker and SearXNG are started automatically when running benchmarks.

## Commands

| Command | Description |
|---------|-------------|
| `bash benchmark.sh` | Run (first time: setup wizard) |
| `bash benchmark.sh run` | Run with saved config |
| `bash benchmark.sh config` | Change provider |
| `bash benchmark.sh status` | Show results |
| `bash benchmark.sh help` | Show help |

## First Time Setup

When you run `bash benchmark.sh` for the first time:

```
==========================================
  WildClawBench - Provider Setup
==========================================

Choose your LLM provider:

  1) LM Studio (local)     - http://localhost:1234/v1
  2) Ollama (local)        - http://localhost:11434/v1
  3) vLLM (local/remote)   - http://localhost:8000/v1
  4) OpenRouter (cloud)    - https://openrouter.ai/api/v1
  5) Custom API            - Your own endpoint

  Enter choice [1-5] (default: 1):

  Provider: lm-studio
  API Base: http://localhost:1234/v1

  Enter model name (default: qwen3.5-9b): qwen3.5-9b

[OK] Configuration saved to .provider-config
```

Configuration is saved to `.provider-config` and reused on next run.

## Change Provider

```bash
# Run setup wizard again
bash benchmark.sh config

# Or override without changing saved config
bash benchmark.sh run --model llama3
bash benchmark.sh run --api-base http://my-server:8000/v1
```

## Override Options

```bash
--model MODEL       # Override model name
--api-base URL      # Override API base URL
--category CAT      # Run specific category
--agent AGENT       # Run one agent only
--parallel N        # Parallel tasks (default: 1)
```

Examples:
```bash
bash benchmark.sh run --agent opencode
bash benchmark.sh run --model llama3 --api-base http://localhost:11434/v1
bash benchmark.sh run --category 01_Productivity_Flow
```

## Supported Providers

| Provider | Default URL | Notes |
|----------|-------------|-------|
| LM Studio | `http://localhost:1234/v1` | Local |
| Ollama | `http://localhost:11434/v1` | Local |
| vLLM | `http://localhost:8000/v1` | Local/Remote |
| OpenRouter | `https://openrouter.ai/api/v1` | Cloud |
| Custom local | `http://localhost:<port>/v1` | Any local server |
| Custom remote | User-specified URL | Any API endpoint |

## Execution Flow

Agents run sequentially (one at a time):

1. **openclaw** → `output/openclaw/`
2. **opencode** → `output/opencode/`
3. **hermesagent** → `output/hermesagent/`

## Task Categories

| Category | Tasks |
|----------|-------|
| `all` | All tasks |
| `01_Productivity_Flow` | `productivity_01`, `productivity_02` |
| `02_Code_Intelligence` | `code_01`, `code_02` |
| `03_Search_Retrieval` | `search_01` |
| `04_Data_Processing` | `data_01` |
| `05_Safety_Alignment` | `safety_01` |

## Environment Variables (.env)

```bash
# API keys (optional for local providers)
OPENROUTER_API_KEY=sk-or-...
LM_STUDIO_API_KEY=lm-studio
OLLAMA_API_KEY=ollama

# Model defaults
DEFAULT_MODEL=qwen3.5-9b
JUDGE_MODEL=openai/gpt-5.4

# Local search (SearXNG - no API key needed)
SEARXNG_URL=http://localhost:8888
```

## Output Structure

```
output/
├── run_summary.json
├── openclaw/
├── opencode/
└── hermesagent/
    └── <category>/<task>/<model>_<timestamp>_<run_id>/
        ├── usage.json
        ├── score.json
        ├── transcript.jsonl
        ├── llm_response.txt
        └── error.txt (if failed)
```

## Scoring

Each task scored 0.0-1.0 on:
- Response quality (25%)
- File creation (25%)
- Code execution (25%)
- Output correctness (25%)

Disable: `bash benchmark.sh run --no-score`

## Help

```bash
bash benchmark.sh help
```
