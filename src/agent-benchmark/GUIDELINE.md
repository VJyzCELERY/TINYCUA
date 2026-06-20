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
| `OPENROUTER_API_KEY` | OpenRouter API access | [OpenRouter](https://openrouter.ai/) |
| `JUDGE_MODEL` | Judge-based grading (optional) | Defaults to `openai/gpt-5.4` |
| `LM_STUDIO_API_KEY` | Local LLM via LM Studio | Set to `lm-studio` (no real key needed) |

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

### Local LLM Setup (LM Studio)

For running benchmarks with local models:

1. **Install LM Studio** and download a model (e.g., `qwen/qwen3.5-9b`)
2. **Start the server** on port 1234
3. **Update `.env`**:
   ```bash
   LM_STUDIO_API_KEY=lm-studio
   DEFAULT_MODEL=qwen3.5-9b
   ```
4. **Update agent configs** (`opencode-config.yaml`, `hermes-config.yaml`):
   ```yaml
   api_base: http://localhost:1234/v1
   api_key_env: LM_STUDIO_API_KEY
   model: qwen3.5-9b
   ```

See `SETUP_LMSTUDIO.md` for detailed instructions.

---

## Quick Start

### 1. Setup

```bash
# Full setup (installs deps, downloads Docker images, creates .env)
bash benchmark.sh setup
```

### 2. Start Your LLM Server

Choose one:

| Provider | Start Command | Default URL |
|----------|---------------|-------------|
| LM Studio | `/Users/jonaja29/.lmstudio/bin/lms server start` | `http://localhost:1234/v1` |
| Ollama | `ollama serve` | `http://localhost:11434/v1` |
| vLLM | `vllm serve <model>` | `http://localhost:8000/v1` |
| OpenRouter | (cloud, no local start) | `https://openrouter.ai/api/v1` |

### 3. Run Benchmark

```bash
# First time: interactive setup wizard
bash benchmark.sh

# Subsequent runs: uses saved config
bash benchmark.sh run
```

> Docker is started automatically when running benchmarks. No need to start it manually.

### First Time Setup Wizard

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

  Enter model name (default: qwen3.5-9b):

[OK] Configuration saved to .provider-config
```

Configuration is saved to `.provider-config` and reused automatically.

---

## Detailed Setup

### Available Commands

| Command | What it does |
|---------|-------------|
| `bash benchmark.sh` | Run (first time: setup wizard) |
| `bash benchmark.sh run` | Run with saved configuration |
| `bash benchmark.sh config` | Change provider configuration |
| `bash benchmark.sh status` | Show latest results |
| `bash benchmark.sh help` | Show help |

### Step 1: Install Dependencies

```bash
# Install Python dependencies
uv pip install -e ".[dev]"

# Or use the setup script
bash setup.sh --step 1
```

### Step 2: Download Docker Images

```bash
# Download all images
bash script/download_images.sh --all

# Download specific harness
bash script/download_images.sh --harness hermesagent

# Or use the setup script
bash setup.sh --step 2
```

**Available Images:**

| Harness | Image Tarball | Loaded Tag |
|---------|---------------|------------|
| OpenClaw | `wildclawbench-ubuntu_v1.3.tar` | `wildclawbench-ubuntu:v1.3` |
| OpenCode | `wildclawbench-ubuntu_v1.3.tar` | `wildclawbench-ubuntu:v1.3` |
| Hermes Agent | `wildclawbench-hermes-agent-v0.5.tar.gz` | `wildclawbench-hermes-agent:v0.5` |

### Step 3: Prepare Task Data

```bash
# Run the preparation script
bash script/prepare.sh

# Or use the setup script
bash setup.sh --step 3
```

**What the preparation script does:**

1. Downloads 3 YouTube videos (football match, lecture, product launch event)
2. Extracts the first half of the football match
3. Renames and copies videos to task directories
4. Extracts `dot_git.tar.gz` for Safety Alignment tasks
5. Downloads SAM3 model weights for Code Intelligence tasks

### Step 4: Setup Environment

```bash
# Create .env file from template
cp .env.example .env

# Edit with your API keys
nano .env

# Or use the setup script
bash setup.sh --step 4
```

**Environment Variables:**

```bash
# Required (for OpenRouter/cloud providers)
OPENROUTER_API_KEY=your_api_key_here

# Optional
JUDGE_MODEL=openai/gpt-5.4
DEFAULT_MODEL=qwen3.5-9b

# Local search (SearXNG - starts automatically)
SEARXNG_URL=http://localhost:8888
```

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
| `--parallel` | Parallel tasks per agent | `1` |

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
```

### Sequential Execution

Due to limited resources, agents run **one at a time**:

1. openclaw → results saved
2. opencode → results saved
3. hermesagent → results saved

After all complete, a summary is printed and saved to `output/run_summary.json`.

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

## Custom Models

### Using OpenRouter

Default configuration uses OpenRouter. Set your model in `.env`:

```bash
DEFAULT_MODEL=openrouter/anthropic/claude-sonnet-4.6
```

### Using Custom Endpoint (OpenClaw Only)

For OpenClaw, you can use a custom API endpoint instead of OpenRouter:

1. **Create a JSON configuration file** (`my_api.json`):

```json
{
  "providers": {
    "my-openai-proxy": {
      "baseUrl": "http://host.docker.internal:8000/v1",
      "apiKey": "${MY_PROXY_API_KEY}",
      "api": "openai-completions",
      "models": [
        {
          "id": "my-model",
          "name": "My Model"
        }
      ]
    }
  }
}
```

2. **Set environment variables** in `.env`:

```bash
MY_PROXY_API_KEY=your_api_key_here
```

3. **Run with custom config**:

```bash
python3 eval/run_batch.py --category 01_Productivity_Flow \
                          --models-config my_api.json \
                          --model my-openai-proxy/my-model
```

**Important:** Some task prompts and evaluation scripts have OpenRouter explicitly mentioned. If you bypass OpenRouter, you may need to adjust these references manually.

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

#### Image Download Fails

```bash
# Check huggingface-hub installation
pip show huggingface-hub

# Reinstall if needed
pip install -U "huggingface_hub[cli]"

# Login if required
huggingface-cli login
```

#### YouTube Download Fails

```bash
# Update yt-dlp
pip install -U yt-dlp

# Try with cookies
yt-dlp --cookies-from-browser chrome <url>
```

#### Memory Issues

```bash
# Check Docker resource limits
docker system info

# Increase Docker memory limit in Docker Desktop settings
```

#### API Key Errors

```bash
# Verify environment variables
source .env
echo $OPENROUTER_API_KEY

# Test API connectivity
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
     https://openrouter.ai/api/v1/models
```

### Getting Help

1. Check the [Troubleshooting Guide](docs/troubleshooting.md)
2. Search [existing issues](https://github.com/your-org/wildclawbench/issues)
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