# agent-benchmark

WildClawBench — benchmark 3 coding agents (OpenClaw, OpenCode, HermesAgent) on the same tasks.

## Quick Start

```bash
# 1. Start your LLM server (any of these, or your own)
lms server start          # LM Studio (port 1234)
ollama serve              # Ollama (port 11434)
vllm serve <model>        # vLLM (port 8000)
# ...or any server on any port

# 2. Run benchmark (first time shows setup wizard)
bash benchmark.sh
```

> Docker and SearXNG are started automatically when running benchmarks.

## Commands

| Command | Description |
|---------|-------------|
| `bash benchmark.sh` | Run (first time: setup wizard) |
| `bash benchmark.sh run` | Run with saved config |
| `bash benchmark.sh config` | Change provider |
| `bash benchmark.sh status` | Show results |
| `bash benchmark.sh searxng` | Manage SearXNG (up\|down\|status) |
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
  5) Custom local server   - Your own localhost port
  6) Custom remote API     - Full URL endpoint

  Enter choice [1-6] (default: 1):
```

**Option 5** lets you type any port number:
```
Enter your local server port or URL:
Examples: 8080, 5000, http://localhost:9090/v1

Port or URL: 9090
→ Provider: local-custom
→ API Base: http://localhost:9090/v1
```

**Timeout** is set during setup:
```
  Task timeout:
    - Enter seconds (e.g. 600 for 10 minutes)
    - Type 'unlimited' for no timeout

  Timeout (default: 600): unlimited
```

Configuration is saved to `.provider-config` and reused on next run.

## SearXNG (Local Search)

SearXNG provides web search capabilities without API keys. It starts automatically when running benchmarks.

```bash
# Manual control
bash benchmark.sh searxng up      # Start SearXNG
bash benchmark.sh searxng status  # Check status
bash benchmark.sh searxng down    # Stop SearXNG

# Test search API
curl "http://localhost:8888/search?q=docker&format=json" | jq '.results[:2]'
```

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
--timeout N         # Task timeout: seconds or 'unlimited' (default: 600)
```

Examples:
```bash
bash benchmark.sh run --agent opencode
bash benchmark.sh run --model llama3 --api-base http://localhost:11434/v1
bash benchmark.sh run --category 01_Productivity_Flow
bash benchmark.sh run --timeout unlimited    # No timeout
bash benchmark.sh run --timeout 300          # 5 minutes
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

Agents run sequentially (one at a time) with progress tracking:

```
Running openclaw...
────────────────────────────────────────
[1/5] ✓ productivity_01 (0.85) - 12.3s
[2/5] ✓ productivity_02 (0.92) - 8.1s
[3/5] ✓ code_01 (0.78) - 15.2s
[4/5] ✗ code_02 (0.00) - 10.5s
[5/5] ✓ search_01 (0.90) - 9.8s

  Progress: 5/5 tasks completed
  Results:  ✓ 4 passed  ✗ 1 failed
```

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

## Environment Variables

No manual setup needed. When you run `bash benchmark.sh`:

1. **API keys** (OpenRouter, etc.) are saved automatically to `.env` during setup wizard
2. **SearXNG URL** is set automatically
3. **Provider config** is saved to `.provider-config`

Just run:
```bash
bash benchmark.sh
```

The script handles everything.

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
