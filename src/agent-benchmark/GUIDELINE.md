# WildClawBench Agent Benchmark Guidelines

This document provides comprehensive instructions for setting up and running the WildClawBench agent benchmark.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Detailed Setup](#detailed-setup)
5. [Running Benchmarks](#running-benchmarks)
6. [Checking Results](#checking-results)
7. [Custom Models](#custom-models)
8. [Troubleshooting](#troubleshooting)

---

## Overview

WildClawBench is a benchmark suite for evaluating AI coding agents across three harnesses:

- **OpenClaw** - Open-source coding agent
- **OpenCode** - OpenCode harness with Qwen 3.5 9B
- **Hermes Agent** - Hermes coding agent

Each harness is containerized with Docker for reproducible evaluation.

---

## Prerequisites

### Required Software

| Software | Version | Installation |
|----------|---------|--------------|
| Docker | 20.10+ | [Install Docker](https://docs.docker.com/get-docker/) |
| Python | 3.10+ | [Install Python](https://www.python.org/downloads/) |
| uv | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| huggingface-hub | Latest | `pip install -U "huggingface_hub[cli]"` |

### Required for Data Preparation

| Software | Purpose | Installation |
|----------|---------|--------------|
| yt-dlp | Download YouTube videos | `brew install yt-dlp` (macOS) |
| ffmpeg | Video processing | `brew install ffmpeg` (macOS) |
| gdown | Download Google Drive files | `brew install gdown` (macOS) |

### API Keys

| Key | Required For | How to Get |
|-----|--------------|------------|
| `PROVIDER_API_KEY` | Agent provider API access | Set during setup wizard |
| `JUDGE_PROVIDER_API_KEY` | Judge-based grading | Set during setup wizard |

### Local Search (SearXNG)

SearXNG provides web search capabilities without API keys. It starts automatically when running benchmarks.

```bash
# Manual control
bash benchmark.sh searxng up      # Start SearXNG
bash benchmark.sh searxng status  # Check status
bash benchmark.sh searxng down    # Stop SearXNG

# Test search API
curl "http://localhost:8888/search?q=docker&format=json" | jq '.results[:2]'
```

---

## Quick Start

### 1. Start Your LLM Server

Choose one:

| Provider | Start Command | Default URL |
|----------|---------------|-------------|
| LM Studio | `lms server start` | `http://localhost:1234/v1` |
| Ollama | `ollama serve` | `http://localhost:11434/v1` |
| vLLM | `vllm serve <model>` | `http://localhost:8000/v1` |
| OpenRouter | (cloud, no local start) | `https://openrouter.ai/api/v1` |
| Custom local | Your own server | `http://localhost:<port>/v1` |
| Custom remote | Any API endpoint | User-specified URL |

### 2. Run Benchmark

```bash
# First time: interactive setup wizard + auto-build images
bash benchmark.sh

# Subsequent runs: uses saved config
bash benchmark.sh run
```

> Agent Docker images are built automatically on first run if not present.

### First Time Setup Wizard

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

Configuration is saved to `.env` and reused automatically.

---

## Detailed Setup

### Available Commands

| Command | What it does |
|---------|-------------|
| `bash benchmark.sh` | Run (first time: setup wizard) |
| `bash benchmark.sh run` | Run with saved configuration |
| `bash benchmark.sh config` | Change provider configuration |
| `bash benchmark.sh status` | Show latest results |
| `bash benchmark.sh searxng` | Manage SearXNG (up\|down\|status) |
| `bash benchmark.sh build` | Build agent Docker images |
| `bash benchmark.sh help` | Show help |

### Step 1: Install Dependencies

```bash
# Install Python dependencies
uv pip install -e ".[dev]"
```

### Step 2: Build Docker Images

```bash
# Build all agent images
docker compose --profile hermes --profile opencode --profile openclaw build

# Or build specific agent
docker compose --profile hermes build hermes-agent
docker compose --profile opencode build opencode-agent
docker compose --profile openclaw build openclaw-agent

# Or use the script
bash benchmark.sh build
```

### Step 3: Prepare Task Data

```bash
# Run the preparation script
bash scripts/prepare.sh
```

**What the preparation script does:**

1. Downloads 3 YouTube videos (football match, lecture, product launch event)
2. Extracts the first half of the football match
3. Renames and copies videos to task directories
4. Extracts `dot_git.tar.gz` for Safety Alignment tasks
5. Downloads SAM3 model weights for Code Intelligence tasks

### Step 4: Run Benchmark

No manual `.env` setup needed. When you run `benchmark.sh`:

```bash
# First time: interactive setup wizard
bash benchmark.sh

# Subsequent runs: uses saved config
bash benchmark.sh run
```

The script automatically:
- Saves provider config to `.env` during setup wizard
- Sets SearXNG URL
- Configures judge provider

> Docker and SearXNG are started automatically when running benchmarks.

---

## Running Benchmarks

### Single Script Usage

```bash
bash benchmark.sh run [options]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--category` | Task category to run | `all` |
| `--agent` | Run specific agent only | All agents |
| `--model` | Model to evaluate | From `.env` |
| `--api-base` | Override API base URL | From `.env` |
| `--parallel` | Parallel tasks per agent | `1` |
| `--timeout` | Task timeout: seconds or 'unlimited' | `600` |

### Examples

```bash
# Run all agents sequentially
bash benchmark.sh run

# Run with specific model
bash benchmark.sh run --model openrouter/openai/gpt-5.5

# Run only one agent
bash benchmark.sh run --agent hermesagent

# Run specific category for all agents
bash benchmark.sh run --category 01_Productivity_Flow

# Run Hermes with specific model on Code Intelligence tasks
bash benchmark.sh run --agent hermesagent --model openai/gpt-5.5 --category 02_Code_Intelligence

# Run with unlimited timeout (no timeout)
bash benchmark.sh run --timeout unlimited

# Run with 5 minute timeout
bash benchmark.sh run --timeout 300
```

### Sequential Execution with Progress

Agents run **one at a time** with real-time progress tracking:

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

After all complete, a summary is saved to `output/<agent>/summary_all.json`.

### Scoring Options

```bash
# Run with scoring (default)
bash benchmark.sh run

# Run without scoring
bash benchmark.sh run --no-score

# Run with verbose scoring output
bash benchmark.sh run --verbose

# Run specific agent with verbose scoring
bash benchmark.sh run --agent opencode --verbose
```

### Model Name Conventions

| Harness | Format | Example |
|---------|--------|---------|
| OpenClaw | `openrouter/<provider>/<model>` | `openrouter/openai/gpt-5.5` |
| OpenCode / Hermes | `<provider>/<model>` | `qwen3.5-9b` |

---

## Scoring System

WildClawBench includes a rule-based scoring system that evaluates task output on a 0.0-1.0 scale.

### How Scoring Works

After each task completes, the scoring engine evaluates:

1. **Response Quality (25 pts)**: LLM response contains valid code blocks and required imports
2. **File Creation (25 pts)**: Expected files exist with correct names
3. **Code Execution (25 pts)**: Scripts run without errors (exit code 0)
4. **Output Correctness (25 pts)**: Output matches expected patterns (logs, reports, etc.)

### Score Output

Each task directory contains `score.json` after scoring:
```json
{
  "task_id": "productivity_01",
  "score": 0.75,
  "raw_score": 75.0,
  "max_score": 100.0,
  "criteria": [
    {"name": "llm_response_exists", "points": 5.0, "max_points": 5.0, "passed": true},
    {"name": "code_block_valid", "points": 10.0, "max_points": 10.0, "passed": true},
    {"name": "script_executes", "points": 15.0, "max_points": 15.0, "passed": true}
  ]
}
```

### Aggregate Scores

`summary_all.json` includes aggregate scoring:
```json
{
  "average_score": 0.72,
  "min_score": 0.45,
  "max_score": 0.95,
  "category_scores": {
    "01_Productivity_Flow": {"average_score": 0.80, "count": 2},
    "02_Code_Intelligence": {"average_score": 0.75, "count": 2}
  }
}
```

### Disable Scoring

Use `--no-score` to skip scoring for faster execution:
```bash
bash benchmark.sh run --no-score
```

### Verbose Scoring

Use `--verbose` to see detailed scoring breakdown:
```bash
bash benchmark.sh run --verbose
```

Output example:
```
Task productivity_01 completed in 69.1s
  Score: 0.75 (75/100 points)
    ✓ llm_response_exists: 5/5 - LLM response file found
    ✓ code_block_valid: 10/10 - Valid Python code block found
    ✓ script_executes: 15/15 - Script executed successfully
    ✗ log_file_created: 0/10 - File not found: organize_files_log.txt
```

---

## Checking Results

### Output Structure

Results are saved under `output/<harness>/<category>/<task_id>/<model_timestamp_runid>/`:

```
output/
├── run_summary.json              # Global run summary
├── openclaw/                     # OpenClaw agent results
│   ├── summary_all.json          # Agent-level summary
│   └── <category>/
│       └── <task_id>/
│           └── <model>_<timestamp>_<run_id>/
│               ├── usage.json        # Task execution stats
│               ├── transcript.jsonl  # LLM interaction log
│               ├── llm_response.txt  # Raw LLM output
│               └── error.txt         # Error message (if failed)
├── opencode/                     # OpenCode agent results
│   └── ...
└── hermesagent/                  # HermesAgent results
    └── ...
```

### Subdirectory Naming

The subdirectory name follows the pattern: `<model>_<timestamp>_<run_id>`

| Field | Description | Example |
|-------|-------------|---------|
| `model` | Model identifier | `qwen3.5-9b`, `step-3.5-flash_free` |
| `timestamp` | UTC timestamp `YYYYMMDDTHHmmSSZ` | `20260618T041243Z` |
| `run_id` | Random 6-char hex identifier | `721a60` |

### Output Files

#### `usage.json`
Task execution statistics:
```json
{
  "task_id": "productivity_01",
  "category": "01_Productivity_Flow",
  "model": "qwen3.5-9b",
  "elapsed_time": 69.15,
  "status": "success",
  "usage": {
    "requests": 1,
    "total_tokens": 495,
    "cost": 0.001238
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Task identifier |
| `category` | string | Task category |
| `model` | string | Model used |
| `elapsed_time` | float | Execution time in seconds |
| `status` | string | `success` or `error` |
| `usage.requests` | int | Number of LLM API calls |
| `usage.total_tokens` | int | Total tokens consumed |
| `usage.cost` | float | Estimated cost (USD) |

#### `transcript.jsonl`
JSON Lines file with LLM interaction events:
```json
{"type": "llm_response", "model": "qwen3.5-9b", "prompt_length": 297, "response_length": 4718, "elapsed_time": 68.16, "usage": {"total_tokens": 495}}
```

#### `llm_response.txt`
Raw text output from the LLM (may contain code blocks, explanations, etc.).

#### `error.txt`
Error message if the task failed (only present on failures).

### Summary Reports

After completion, summary reports are generated:

- `output/run_summary.json` - Global summary with agent pass/fail status
- `output/<agent>/summary_all.json` - Per-agent summary with task-level details

#### `run_summary.json`
```json
{
  "timestamp": "2026-06-18T02:37:45Z",
  "duration_seconds": 4,
  "category": "all",
  "model": "from .env",
  "agents": {
    "openclaw": {"status": "PASS", "duration_seconds": 2},
    "opencode": {"status": "PASS", "duration_seconds": 1},
    "hermesagent": {"status": "PASS", "duration_seconds": 1}
  }
}
```

---

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

### Services

| Service | Profile | Description |
|---------|---------|-------------|
| `searxng` | (always) | Local search engine |
| `hermes-agent` | `hermes` | Hermes agent harness |
| `opencode-agent` | `opencode` | OpenCode agent harness |
| `openclaw-agent` | `openclaw` | OpenClaw agent harness |

---

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

---

## Custom Models

### Using OpenRouter

Default configuration uses OpenRouter. Set your model in `.env`:

```bash
PROVIDER_MODEL=openrouter/anthropic/claude-sonnet-4.6
```

### Using Custom Endpoint

For custom API endpoints, set the base URL in `.env`:

```bash
PROVIDER_BASE_URL=http://your-server:8000/v1
PROVIDER_MODEL=your-model-name
PROVIDER_API_KEY=your_api_key_here
```

---

## Troubleshooting

### Common Issues

#### Docker Not Running

```bash
# Check Docker status
docker info

# Start Docker (macOS)
open -a Docker
```

#### SearXNG Not Starting

```bash
# Check SearXNG status
bash benchmark.sh searxng status

# View SearXNG logs
docker logs searxng

# Restart SearXNG
bash benchmark.sh searxng down
bash benchmark.sh searxng up
```

#### Image Build Fails

```bash
# Check Docker resource limits
docker system info

# Increase Docker memory limit in Docker Desktop settings

# Rebuild with no cache
docker compose --profile hermes build --no-cache hermes-agent
```

#### API Key Errors

```bash
# Verify environment variables
source .env
echo $PROVIDER_API_KEY
echo $JUDGE_PROVIDER_API_KEY

# Test API connectivity
curl -H "Authorization: Bearer $PROVIDER_API_KEY" \
     $PROVIDER_BASE_URL/models
```

### Getting Help

1. Check the [Troubleshooting Guide](docs/troubleshooting.md)
2. Search [existing issues](https://github.com/TINYCUA/TINYCUA/issues)
3. Create a new issue with:
   - Your OS and Docker version
   - The command you ran
   - Full error output
   - Relevant logs from `output/`

---

## Task Categories

| Category | Description |
|----------|-------------|
| `01_Productivity_Flow` | Task automation and workflow |
| `02_Code_Intelligence` | Code understanding and generation |
| `03_Search_Retrieval` | Information retrieval tasks |
| `04_Data_Processing` | Data manipulation and analysis |
| `05_Safety_Alignment` | Safety and alignment tasks |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Adding new tasks
- Implementing new harnesses
- Improving evaluation metrics
- Reporting bugs

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
