# agent-benchmark

WildClawBench — benchmark 3 coding agents (OpenClaw, OpenCode, HermesAgent) on the same tasks.

## Quick Start

```bash
# 1. Start your LLM server (any of these, or your own)
lms server start          # LM Studio (port 1234)
ollama serve              # Ollama (port 11434)
vllm serve <model>        # vLLM (port 8000)
# ...or any server on any port

# 2. Run benchmark
bash benchmark.sh
```

## What Happens When You Run `bash benchmark.sh`

### First Time

```
┌─────────────────────────────────────────────────────────┐
│  Step 1: Setup Wizard                                   │
│  - Choose agent provider (name, URL, model, API key)    │
│  - Choose judge provider (for grading)                  │
│  - Set timeout                                          │
│  → Saved to .env                                        │
├─────────────────────────────────────────────────────────┤
│  Step 2: Auto-Build Images                              │
│  - Builds hermes, opencode, openclaw Docker images      │
│  - Skipped if images already exist                      │
├─────────────────────────────────────────────────────────┤
│  Step 3: Start SearXNG                                  │
│  - Local search engine for web search tasks             │
├─────────────────────────────────────────────────────────┤
│  Step 4: Run Benchmark                                  │
│  - Runs tasks for each agent sequentially               │
│  - Scores results                                       │
│  - Saves to output/                                     │
└─────────────────────────────────────────────────────────┘
```

### Subsequent Runs

```
┌─────────────────────────────────────────────────────────┐
│  Step 1: Load Config                                    │
│  - Reads .env file                                      │
├─────────────────────────────────────────────────────────┤
│  Step 2: Check Images                                   │
│  - Images exist → skip build                            │
├─────────────────────────────────────────────────────────┤
│  Step 3: Start SearXNG (if not running)                 │
├─────────────────────────────────────────────────────────┤
│  Step 4: Run Benchmark                                  │
└─────────────────────────────────────────────────────────┘
```

## Commands

| Command | Description |
|---------|-------------|
| `bash benchmark.sh` | Run (first time: setup wizard) |
| `bash benchmark.sh run` | Run with saved config |
| `bash benchmark.sh config` | Change provider |
| `bash benchmark.sh status` | Show results |
| `bash benchmark.sh searxng` | Manage SearXNG (up\|down\|status) |
| `bash benchmark.sh build` | Build agent Docker images |
| `bash benchmark.sh help` | Show help |

## First Time Setup

When you run `bash benchmark.sh` for the first time, the setup wizard asks for:

1. **Agent Provider** (for running tasks):
   - Provider name (e.g., `lm-studio`, `openrouter`)
   - Base URL (e.g., `http://localhost:1234/v1`)
   - Model name (e.g., `qwen3.5-9b`)
   - API key (if needed)

2. **Judge Provider** (for grading responses):
   - Provider name (e.g., `openrouter`)
   - Base URL (e.g., `https://openrouter.ai/api/v1`)
   - Model name (e.g., `openai/gpt-5.4`)
   - API key

3. **Timeout**:
   - Enter seconds (e.g., 600 for 10 minutes)
   - Type `unlimited` for no timeout

Configuration is saved to `.env` and reused on next run.

## Docker Compose Profiles

Agent harnesses use Docker Compose profiles for selective startup:

```bash
# Build all agent images
docker compose --profile hermes --profile opencode --profile openclaw build

# Build specific agent
docker compose --profile hermes build hermes-agent

# Run agent directly (one-shot)
docker compose --profile hermes run --rm hermes-agent

# Start SearXNG only
docker compose up -d searxng
```

**Services:**

| Service | Profile | Description |
|---------|---------|-------------|
| `searxng` | (always) | Local search engine |
| `hermes-agent` | `hermes` | Hermes agent harness |
| `opencode-agent` | `opencode` | OpenCode agent harness |
| `openclaw-agent` | `openclaw` | OpenClaw agent harness |

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

## Environment Variables

Configuration is managed via `.env` file (created by setup wizard):

```bash
# Agent Provider
PROVIDER_NAME=your_provider_name
PROVIDER_BASE_URL=http://localhost:1234/v1
PROVIDER_MODEL=your_model_here
PROVIDER_API_KEY=your_key_here

# Judge Provider (for grading)
JUDGE_PROVIDER_NAME=your_judge_provider_name
JUDGE_PROVIDER_BASE_URL=https://openrouter.ai/api/v1
JUDGE_PROVIDER_MODEL=your_judge_model_here
JUDGE_PROVIDER_API_KEY=your_key_here

# Local search
SEARXNG_URL=http://localhost:8888

# Runtime
LOG_LEVEL=INFO
TIMEOUT=600

# Docker Compose paths
OUTPUT_DIR=./output
WORKSPACE_DIR=./workspace
```

See `.env.example` for the full template.

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
