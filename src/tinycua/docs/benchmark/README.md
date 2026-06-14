# TinyCUA Benchmark Docker Image

Docker image for running TinyCUA as an agent harness within WildClawBench benchmark evaluation.

## Quick Start

### Build the Image

```bash
docker build -t tinycua-benchmark .
```

### Run with Docker Compose (Recommended)

```bash
# Start with default configuration
docker compose -f docker-compose.benchmark.yml up

# Or set environment variables
TINYCUA_BASE_URL=http://host.docker.internal:1234/v1 \
TASK_PROMPT="Your task prompt here" \
docker compose -f docker-compose.benchmark.yml up
```

### Run with Docker Directly

```bash
docker run --rm \
  -v ./workspace:/tmp_workspace \
  -e TINYCUA_BASE_URL=http://host.docker.internal:1234/v1 \
  -e TASK_PROMPT="Your task prompt here" \
  tinycua-benchmark
```

### Linux: Access Host Model Endpoint

On Linux, add `--add-host` to allow the container to reach your host machine:

```bash
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -v ./workspace:/tmp_workspace \
  -e TINYCUA_BASE_URL=http://host.docker.internal:1234/v1 \
  -e TASK_PROMPT="Your task prompt here" \
  tinycua-benchmark
```

## Configuration Reference

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `TINYCUA_BASE_URL` | OpenAI-compatible model endpoint URL | `http://host.docker.internal:1234/v1` |
| `TASK_PROMPT` | Task prompt for the agent (injected by WildClawBench) | `"Analyze the codebase..."` |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TINYCUA_API_KEY` | `""` | API key for model endpoint (empty for local) |
| `TINYCUA_MODEL` | `llama3` | Model name to use for inference |
| `BRAVE_API_KEY` | `""` | API key for Brave web search |
| `TINYCUA_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `TINYCUA_TIMEOUT` | `300` | Maximum execution time in seconds |

### Volume Mounts

| Container Path | Description |
|----------------|-------------|
| `/tmp_workspace` | Task workspace — mount your task files here |
| `/tmp_workspace/results` | Output directory for benchmark artifacts |
| `/tmp_workspace/transcript.jsonl` | Agent execution transcript |

## Container Lifecycle

1. **Validation**: Entry point validates `TINYCUA_BASE_URL` and `TASK_PROMPT`
2. **Configuration**: TinyCUA is configured with model endpoint and task parameters
3. **Execution**: Agent runs with the task prompt, writing results to `/tmp_workspace/results`
4. **Artifacts**: Transcript, logs, and task outputs are preserved for extraction

## Local Model Endpoints

TinyCUA requires an OpenAI-compatible model endpoint. Common options:

### Ollama

```bash
# Start Ollama with OpenAI-compatible API
ollama serve

# Default endpoint: http://localhost:11434/v1
```

### LM Studio

1. Download and install LM Studio
2. Load a model (e.g., Llama 3 8B)
3. Start the local server
4. Default endpoint: `http://localhost:1234/v1`

### vLLM

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3-8B-Instruct \
  --port 8000

# Endpoint: http://localhost:8000/v1
```

## WildClawBench Integration

The container is designed to work with WildClawBench's container lifecycle:

1. WildClawBench sets `TASK_PROMPT` environment variable before container start
2. Container reads `TASK_PROMPT` and passes it to `tinycua benchmark run`
3. Agent executes the task, writing results to `/tmp_workspace/results`
4. WildClawBench extracts artifacts for grading

### Adapter Contract

The entry point follows the WildClawBench adapter contract:
- Reads `TASK_PROMPT` from environment
- Writes transcript to `/tmp_workspace/transcript.jsonl`
- Writes results to `/tmp_workspace/results/`
- Exits with code 0 on success, non-zero on failure

## Troubleshooting

### Container fails to start

**Error**: `ERROR: TINYCUA_BASE_URL not set`

**Solution**: Set the `TINYCUA_BASE_URL` environment variable to your model endpoint.

### Container fails without task prompt

**Error**: `ERROR: TASK_PROMPT not set (injected by WildClawBench)`

**Solution**: Set the `TASK_PROMPT` environment variable or pass `--prompt` to the CLI.

### Cannot reach model endpoint

**Symptoms**: Agent fails with connection error

**Solutions**:
1. Verify model endpoint is running: `curl http://localhost:1234/v1/models`
2. On Linux, ensure `--add-host=host.docker.internal:host-gateway` is set
3. Check firewall rules blocking container network access

### Image build fails

**Symptoms**: Docker build errors

**Solutions**:
1. Ensure Docker daemon is running: `docker info`
2. Check available disk space: `docker system df`
3. Clean Docker cache: `docker system prune`

### Permission denied on /tmp_workspace

**Symptoms**: Container fails with permission error

**Solution**: Ensure the mounted directory is writable:
```bash
chmod -R 777 ./workspace
```

## CLI Reference

The `tinycua benchmark run` command accepts these arguments:

```bash
tinycua benchmark run \
  --prompt "Your task prompt" \
  --workspace /tmp_workspace \
  --output /tmp_workspace/results \
  --transcript /tmp_workspace/transcript.jsonl \
  --timeout 300 \
  --base-url http://localhost:1234/v1 \
  --api-key "" \
  --model llama3 \
  --verbose
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--prompt` | (from TASK_PROMPT env) | Task prompt for the agent |
| `--workspace` | `/tmp_workspace` | Working directory for the agent session |
| `--output` | `/tmp_workspace/results` | Output directory for benchmark artifacts |
| `--transcript` | `/tmp_workspace/transcript.jsonl` | Path for transcript output |
| `--timeout` | 300 | Maximum execution time in seconds |
| `--base-url` | (from env) | Override TINYCUA_BASE_URL |
| `--api-key` | (from env) | Override TINYCUA_API_KEY |
| `--model` | (from env) | Override TINYCUA_MODEL |
| `--verbose` | false | Enable debug logging |

## Image Size

Target image size is under 2GB. The current image uses:

- Base: `python:3.11-slim` (~150MB)
- System dependencies: ~50MB
- Python packages: ~500MB
- TinyCUA source: ~100MB

Check image size:
```bash
docker image inspect tinycua-benchmark --format '{{.Size}}'
# Or human-readable:
docker images tinycua-benchmark
```
