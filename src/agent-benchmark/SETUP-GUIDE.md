# WildClawBench Setup Guide

Step-by-step guide for setting up and running WildClawBench agent benchmarks.

---

## Prerequisites

Install these before starting:

```bash
# Docker
# macOS: Download from https://docs.docker.com/desktop/install/mac-install/
# Ubuntu: 
curl -fsSL https://get.docker.com | sh

# Python package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# HuggingFace CLI (for downloading images)
pip install -U "huggingface_hub[cli]"

# Optional: for task data preparation
brew install yt-dlp ffmpeg gdown  # macOS
# or
apt install yt-dlp ffmpeg gdown   # Ubuntu
```

---

## Quick Setup

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd wildclawbench

# 2. Run setup (downloads all 4 Docker images, installs deps, creates .env)
bash benchmark.sh setup

# 3. Edit .env with your API keys
nano .env

# 4. Run benchmarks
bash benchmark.sh run
```

---

## Step-by-Step Setup

### Step 1: Clone Repository

```bash
git clone <repo-url>
cd wildclawbench
```

### Step 2: Run Setup Script

```bash
bash benchmark.sh setup
```

This will:
- Check prerequisites (docker, uv, huggingface-hub)
- Install Python dependencies
- Download 4 Docker images (~5GB each):
  - `wildclawbench-ubuntu:v1.3` (OpenClaw)
  - `wildclawbench-claudecode-ubuntu:v0.2` (Claude Code)
  - `wildclawbench-codex-ubuntu:v0.0` (Codex)
  - `wildclawbench-hermes-agent:v0.5` (Hermes)
- Create `.env` file from template

### Step 3: Configure API Keys

Edit `.env`:

```bash
nano .env
```

Set these values:

```bash
# Required: Get from https://openrouter.ai/
OPENROUTER_API_KEY=sk-or-v1-...

# Required: Get from https://brave.com/search/api/ (free tier available)
BRAVE_API_KEY=BSA...

# Optional: Model to evaluate
DEFAULT_MODEL=openrouter/stepfun/step-3.5-flash:free

# Optional: Judge model for grading
JUDGE_MODEL=openai/gpt-5.4
```

### Step 4: Verify Setup

```bash
# Check Docker images are loaded
docker images | grep wildclawbench

# Should show:
# wildclawbench-ubuntu              v1.3
# wildclawbench-claudecode-ubuntu   v0.2
# wildclawbench-codex-ubuntu        v0.0
# wildclawbench-hermes-agent        v0.5

# Check .env exists
cat .env
```

---

## Running Benchmarks

### Run All Agents (Sequential)

```bash
bash benchmark.sh run
```

Executes agents one at a time:
1. openclaw → results in `output/openclaw/`
2. claudecode → results in `output/claudecode/`
3. codex → results in `output/codex/`
4. hermesagent → results in `output/hermesagent/`

### Run Specific Agent

```bash
# Only Hermes Agent
bash benchmark.sh run --agent hermesagent

# Only OpenClaw
bash benchmark.sh run --agent openclaw
```

### Run With Specific Model

```bash
# Use GPT-5.5
bash benchmark.sh run --model openrouter/openai/gpt-5.5

# Use Claude Sonnet
bash benchmark.sh run --model openrouter/anthropic/claude-sonnet-4.6
```

### Run Specific Category

```bash
# Only Productivity Flow tasks
bash benchmark.sh run --category 01_Productivity_Flow

# Only Code Intelligence tasks
bash benchmark.sh run --category 02_Code_Intelligence
```

### Combined Options

```bash
# Hermes Agent + GPT-5.5 + Code Intelligence only
bash benchmark.sh run --agent hermesagent --model openai/gpt-5.5 --category 02_Code_Intelligence
```

---

## Task Categories

| Category | Description |
|----------|-------------|
| `all` | Run all tasks (default) |
| `01_Productivity_Flow` | Task automation and workflow |
| `02_Code_Intelligence` | Code understanding and generation |
| `03_Search_Retrieval` | Information retrieval tasks |
| `04_Data_Processing` | Data manipulation and analysis |
| `05_Safety_Alignment` | Safety and alignment tasks |

---

## Checking Results

### View Latest Results

```bash
bash benchmark.sh status
```

### Results Structure

```
output/
├── openclaw/
│   └── <category>/<task_id>/<model_timestamp_runid>/
│       ├── score.json          # Scores
│       ├── usage.json          # Token usage
│       └── agent.log           # Execution log
├── claudecode/
├── codex/
├── hermesagent/
└── run_summary.json            # Latest run summary
```

### Check Specific Agent Results

```bash
# List completed tasks for an agent
ls output/hermesagent/

# Check a specific score
cat output/hermesagent/01_Productivity_Flow/task_1/*/score.json
```

---

## Model Naming

Different harnesses use different model name formats:

| Harness | Format | Example |
|---------|--------|---------|
| OpenClaw | `openrouter/<provider>/<model>` | `openrouter/openai/gpt-5.5` |
| Codex | `openrouter/<provider>/<model>` | `openrouter/openai/gpt-5.5` |
| Claude Code | `<provider>/<model>` | `openai/gpt-5.5` |
| Hermes | `<provider>/<model>` | `openai/gpt-5.5` |

**Note:** Claude Code and Hermes add `openrouter/` prefix automatically.

---

## Troubleshooting

### Docker not running

```bash
# Check Docker status
docker info

# Start Docker (macOS)
open -a Docker
```

### Image download fails

```bash
# Reinstall huggingface-hub
pip install -U "huggingface_hub[cli]"

# Login if needed
huggingface-cli login
```

### Missing API key errors

```bash
# Check your .env
cat .env

# Verify key is set
source .env
echo $OPENROUTER_API_KEY
```

### Out of disk space

```bash
# Check Docker disk usage
docker system df

# Clean up unused images
docker image prune -a
```

### Script permission denied

```bash
chmod +x benchmark.sh
```

---

## Make Targets (Alternative)

```bash
make setup          # Run setup
make run            # Run all agents
make status         # Check results
make help           # Show all targets
```

---

## Getting Help

1. Check this guide
2. Read `GUIDELINE.md` for detailed documentation
3. Check `output/` for execution logs
4. Open an issue with:
   - Your OS and Docker version
   - The command you ran
   - Error output
