# agent-benchmark

WildClawBench multi-harness benchmark adapter — supports OpenClaw, Claude Code, Codex CLI, and Hermes Agent.

## Install

```bash
uv pip install -e ".[dev]"
```

## Usage

```python
from agent_benchmark import get_agent

# Create any agent by name
agent = get_agent("hermesagent", config_path="hermes-config.yaml")
agent = get_agent("openclaw")
agent = get_agent("claudecode")
agent = get_agent("codex")

# List available agents
from agent_benchmark.agents import list_agents
print(list_agents())  # ['claudecode', 'codex', 'hermesagent', 'openclaw']
```

## Compare Results

```bash
uv run python -m agent_benchmark.compare_results \
    output/openclaw/summary_all.json \
    output/hermesagent/summary_all.json \
    --name-a openclaw --name-b hermesagent \
    --output comparison.json
```

## Setup

See `docs/SETUP.md` for full Ubuntu setup instructions (Docker, images, task data, running).
