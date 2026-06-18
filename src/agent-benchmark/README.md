# agent-benchmark

WildClawBench multi-harness benchmark adapter — supports OpenClaw, OpenCode (Qwen 3.5 9B), and Hermes Agent.

## Quick Start

```bash
# 1. Setup (installs deps, downloads Docker images, creates .env)
bash benchmark.sh setup

# 2. Edit .env with your API keys
nano .env

# 3. Run all agents sequentially
bash benchmark.sh run
```

## Usage

### Single Script Commands

```bash
bash benchmark.sh setup              # Full setup
bash benchmark.sh run                # Run all agents sequentially
bash benchmark.sh run --model X      # Run with specific model
bash benchmark.sh run --agent X      # Run only one agent
bash benchmark.sh run --category X   # Run specific task category
bash benchmark.sh status             # Show results
bash benchmark.sh help               # Show help
```

### Examples

```bash
# Run all agents with Qwen 3.5 9B
bash benchmark.sh run --model qwen3.5-9b

# Run only OpenCode
bash benchmark.sh run --agent opencode

# Run only Productivity Flow tasks
bash benchmark.sh run --category 01_Productivity_Flow

# Run OpenCode with specific model on Code Intelligence tasks
bash benchmark.sh run --agent opencode --model qwen3.5-9b --category 02_Code_Intelligence
```

### Make Targets

```bash
make setup          # Full setup
make run            # Run all agents
make run-model MODEL=qwen3.5-9b
make run-agent AGENT=opencode
make status         # Show results
make help           # Show all targets
```

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

## Execution Flow

The benchmark runs agents **sequentially** (one at a time) to conserve resources:

1. **openclaw** → results saved to `output/openclaw/`
2. **opencode** → results saved to `output/opencode/`
3. **hermesagent** → results saved to `output/hermesagent/`

After all agents complete, a summary is printed and saved to `output/run_summary.json`.

## Task Categories

| Category | Description | Tasks |
|----------|-------------|-------|
| `all` | Run all tasks (default) | 7 |
| `01_Productivity_Flow` | Task automation and workflow | `productivity_01`, `productivity_02` |
| `02_Code_Intelligence` | Code understanding and generation | `code_01`, `code_02` |
| `03_Search_Retrieval` | Information retrieval tasks | `search_01` |
| `04_Data_Processing` | Data manipulation and analysis | `data_01` |
| `05_Safety_Alignment` | Safety and alignment tasks | `safety_01` |

## Environment (.env)

```bash
# Required (for OpenRouter-based models)
OPENROUTER_API_KEY=your_api_key_here

# Optional
BRAVE_API_KEY=your_brave_key_here # Needed for search tasks only
DEFAULT_MODEL=qwen3.5-9b
JUDGE_MODEL=openai/gpt-5.4

# LM Studio (local LLM)
LM_STUDIO_API_KEY=lm-studio
```

### Local LLM Setup (LM Studio)

For running benchmarks with local models via LM Studio:

1. Install LM Studio and download a model (e.g., `qwen/qwen3.5-9b`)
2. Start the local server on port 1234
3. Update `.env`:
   ```bash
   LM_STUDIO_API_KEY=lm-studio
   DEFAULT_MODEL=qwen3.5-9b
   ```
4. Update `opencode-config.yaml` and `hermes-config.yaml`:
   ```yaml
   api_base: http://localhost:1234/v1
   api_key_env: LM_STUDIO_API_KEY
   model: qwen3.5-9b
   ```

See `SETUP_LMSTUDIO.md` for detailed instructions.

## Model Naming

| Harness | Format | Example |
|---------|--------|---------|
| OpenClaw | `openrouter/<provider>/<model>` | `openrouter/openai/gpt-5.5` |
| OpenCode / Hermes | `<provider>/<model>` | `qwen3.5-9b` |

## Documentation

- `SETUP-GUIDE.md` - Quick setup guide for teammates
- `GUIDELINE.md` - Comprehensive documentation
- `docs/` - Additional documentation

## Scoring System

WildClawBench includes a rule-based scoring system that evaluates task output on a 0.0-1.0 scale.

### Scoring Criteria

Each task is scored on four dimensions:

| Dimension | Points | Description |
|-----------|--------|-------------|
| **Response Quality** | 25 | LLM response contains valid code, required imports |
| **File Creation** | 25 | Expected files exist with correct names |
| **Code Execution** | 25 | Scripts run without errors |
| **Output Correctness** | 25 | Output matches expected patterns |

### Score Output

After scoring, each task directory contains `score.json`:
```json
{
  "task_id": "productivity_01",
  "score": 0.75,
  "raw_score": 75.0,
  "max_score": 100.0,
  "criteria": [
    {"name": "llm_response_exists", "points": 5.0, "max_points": 5.0, "passed": true},
    {"name": "code_block_valid", "points": 10.0, "max_points": 10.0, "passed": true}
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
    "01_Productivity_Flow": {"average_score": 0.80, "count": 2}
  }
}
```

### Disable Scoring

Use `--no-score` to skip scoring for faster execution:
```bash
bash benchmark.sh run --no-score
```

## Output Structure

All benchmark results are saved to `output/` with the following hierarchy:

```
output/
├── run_summary.json              # Global run summary
├── openclaw/                     # OpenClaw agent results
│   ├── summary_all.json          # Agent-level summary
│   └── <category>/
│       └── <task_id>/
│           └── <model>_<timestamp>_<run_id>/
│               ├── usage.json        # Task execution stats
│               ├── score.json        # Scoring results
│               ├── transcript.jsonl  # LLM interaction log
│               ├── llm_response.txt  # Raw LLM output
│               └── error.txt         # Error message (if failed)
├── opencode/                     # OpenCode agent results
│   └── ...
└── hermesagent/                  # HermesAgent results
    └── ...
```

### Run Naming Convention

Each task run creates a directory named:
```
<model>_<timestamp>_<run_id>
```

Example: `qwen3.5-9b_20260618T041243Z_721a60`

| Field | Description |
|-------|-------------|
| `model` | Model identifier (e.g., `qwen3.5-9b`, `step-3.5-flash_free`) |
| `timestamp` | UTC timestamp `YYYYMMDDTHHmmSSZ` |
| `run_id` | Random 6-character hex identifier |

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

#### `run_summary.json`
Global summary after all agents complete:
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

#### `summary_all.json`
Per-agent summary with task-level details (saved to `output/<agent>/summary_all.json`).

## Python API

```python
from agent_benchmark import get_agent

agent = get_agent("opencode", config_path="opencode-config.yaml")
agent = get_agent("openclaw")
```
