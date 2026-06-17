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
| `BRAVE_API_KEY` | Search & Retrieval tasks | [Brave Search API](https://brave.com/search/api/) |
| `JUDGE_MODEL` | Judge-based grading (optional) | Defaults to `openai/gpt-5.4` |

---

## Quick Start

### 1. Check What's Installed

```bash
# Pre-flight check — see what's already installed vs what's missing
bash benchmark.sh check
```

This shows the status of Docker, uv, Python, Docker images, and API keys.

### 3. Clone the Repository

```bash
git clone https://github.com/your-org/wildclawbench.git
cd wildclawbench
```

### 4. Run Setup

```bash
# Full setup (installs deps, downloads all 4 Docker images, creates .env)
bash benchmark.sh setup
```

### 5. Configure Environment

```bash
# Edit .env file with your API keys
nano .env
```

### 6. Run Benchmarks

```bash
# Run all agents sequentially (one at a time)
bash benchmark.sh run

# Or run with specific model
bash benchmark.sh run --model openrouter/openai/gpt-5.5
```

---

## Detailed Setup

### Available Commands

| Command | What it does |
|---------|-------------|
| `bash benchmark.sh check` | Pre-flight check — see what's installed |
| `bash benchmark.sh setup` | Full setup (deps, images, env) |
| `bash benchmark.sh run` | Run all agents sequentially |
| `bash benchmark.sh status` | Show latest results |

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
# Required
OPENROUTER_API_KEY=your_api_key_here
BRAVE_API_KEY=your_brave_key_here

# Optional
JUDGE_MODEL=openai/gpt-5.4
DEFAULT_MODEL=openrouter/stepfun/step-3.5-flash:free
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

### Model Name Conventions

| Harness | Format | Example |
|---------|--------|---------|
| OpenClaw | `openrouter/<provider>/<model>` | `openrouter/openai/gpt-5.5` |
| OpenCode / Hermes | `<provider>/<model>` | `qwen3.5-9b` |

---

## Checking Results

### Output Structure

Results are saved under `output/<harness>/<category>/<task_id>/<model_timestamp_runid>/`:

```
output/<harness>/<category>/<task_id>/<model_timestamp_runid>/
├── score.json          # per-metric scores
├── usage.json          # token counts, cost, elapsed time
├── agent.log           # agent execution log
├── chat.jsonl          # full conversation trace (OpenClaw)
├── gateway.log         # gateway log (OpenClaw)
└── task_output/        # files produced by the agent
```

### Subdirectory Naming

The subdirectory name follows the pattern: `<short_model>_<timestamp>_<runid>`

- `short_model`: Last segment of the model path (e.g., `claude-sonnet-4.6` from `openrouter/anthropic/claude-sonnet-4.6`)
- `timestamp`: When the run started
- `runid`: 6-char random hex string (ensures parallel/repeated runs never collide)

### Summary Reports

After completion, summary reports are generated:

- `output/summary_all.json` - Global summary
- Per-category summaries in respective directories

Each metric is scored from 0.00 to 1.00.

### Verification

For independent verification, reference results are available in our Google Drive folder:

- [overall_results.json](https://drive.google.com/file/d/your-file-id/view)
- [overall_dashboard.html](https://drive.google.com/file/d/your-file-id/view)
- Detailed results for each model

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