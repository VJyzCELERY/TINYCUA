# Hermes Agent Benchmark Setup

Step-by-step guide for setting up and running the Hermes agent benchmark
alongside TinyCUA in the WildClawBench harness.

## Prerequisites

- Python >=3.12 with `uv`
- Docker installed and running
- API key for an external LLM provider (OpenAI, Anthropic, etc.)

## 1. Environment Variables

Create a `.env` file or export the required variable:

```bash
export HERMES_API_KEY=sk-your-api-key-here
```

**Important**: Never commit API keys to version control. The config file
references the environment variable name, not the key itself.

## 2. Hermes Config File

Create a YAML config file (e.g., `hermes-config.yaml`):

```yaml
model: "gpt-4"
api_base: "https://api.openai.com/v1"
api_key_env: "HERMES_API_KEY"
temperature: 0.0
max_tokens: 4096
timeout: 120
```

| Field | Required | Description |
|-------|----------|-------------|
| `model` | Yes | Model name/path (e.g., `gpt-4`, `claude-3`) |
| `api_base` | Yes | API endpoint URL |
| `api_key_env` | Yes | Environment variable name containing the API key |
| `temperature` | No | Sampling temperature (default: 0.0) |
| `max_tokens` | No | Max tokens per response (default: 4096) |
| `timeout` | No | Request timeout in seconds (default: 120) |

## 3. Build Hermes Docker Image

Run from the project root:

```bash
cd src/hermes-benchmark
bash scripts/build_hermes_image.sh
```

This builds the `hermes-agent` Docker image using `docker/Dockerfile.hermes`.
The image is based on upstream WildClawBench (commit `86d7144`).
Expected size: ~5GB.

## 4. Run Hermes Benchmark

From the project root, run a subset of tasks to verify the setup:

```bash
cd src/hermes-benchmark
uv run python -m hermes_benchmark.hermes_agent \
    --config ./hermes-config.yaml \
    --tasks task_001,task_002,task_003
```

Or use the TinyCUA benchmark runner (with hermes-benchmark installed):

```bash
cd src/tinycua
uv run python -m tinycua.scripts.run_benchmark \
    --agent-backend hermesagent \
    --hermes-config ../hermes-benchmark/hermes-config.yaml \
    --output-dir ./benchmark_results/hermes \
    --tasks task_001,task_002,task_003
```

## 5. Compare Results

```bash
uv run python -m hermes_benchmark.compare_results \
    ../tinycua/benchmark_results/tinycua/summary_all.json \
    ../tinycua/benchmark_results/hermes/summary_all.json \
    --output ./comparison.json
```

The comparison JSON includes per-task score deltas and aggregate statistics.

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| `HERMES_API_KEY not set` | Missing env var | Export the env var or add to `.env` |
| `Docker image build failed` | Docker not running | Start Docker daemon |
| `Docker binary not found` | Docker not installed | Install Docker Desktop |
| Container timeout | Model too slow | Increase `timeout` in config |
| `--hermes-config is required` | Missing CLI arg | Add `--hermes-config <path>` |
