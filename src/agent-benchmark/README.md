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

## Execution Flow

The benchmark runs agents **sequentially** (one at a time) to conserve resources:

1. **openclaw** → results saved to `output/openclaw/`
2. **opencode** → results saved to `output/opencode/`
3. **hermesagent** → results saved to `output/hermesagent/`

After all agents complete, a summary is printed and saved to `output/run_summary.json`.

## Task Categories

| Category | Description |
|----------|-------------|
| `all` | Run all tasks (default) |
| `01_Productivity_Flow` | Task automation and workflow |
| `02_Code_Intelligence` | Code understanding and generation |
| `03_Search_Retrieval` | Information retrieval tasks |
| `04_Data_Processing` | Data manipulation and analysis |
| `05_Safety_Alignment` | Safety and alignment tasks |

## Environment (.env)

```bash
# Required
OPENROUTER_API_KEY=your_api_key_here
BRAVE_API_KEY=your_brave_key_here

# Optional
DEFAULT_MODEL=openrouter/stepfun/step-3.5-flash:free
JUDGE_MODEL=openai/gpt-5.4
```

## Model Naming

| Harness | Format | Example |
|---------|--------|---------|
| OpenClaw | `openrouter/<provider>/<model>` | `openrouter/openai/gpt-5.5` |
| OpenCode / Hermes | `<provider>/<model>` | `qwen3.5-9b` |

## Documentation

- `SETUP-GUIDE.md` - Quick setup guide for teammates
- `GUIDELINE.md` - Comprehensive documentation
- `docs/` - Additional documentation

## Python API

```python
from agent_benchmark import get_agent

agent = get_agent("opencode", config_path="opencode-config.yaml")
agent = get_agent("openclaw")
```
