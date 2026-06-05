# WildClawBench Adapter Contract

**Status**: Research Complete
**Created**: 2026-06-05
**Last Updated**: 2026-06-05
**Source**: [InternLM/WildClawBench](https://github.com/InternLM/WildClawBench)

---

## Overview

This document defines the adapter contract that TINYCUA must implement to run as a 5th harness in WildClawBench. WildClawBench is an agent benchmark that tests real-world, end-to-end AI agent capabilities across 60 tasks in 6 categories.

**Key Insight**: WildClawBench uses Docker containers for task isolation. Each harness runs inside a container, and grading happens inside the same container after the agent finishes. The adapter must:
1. Implement `BaseAgent` interface
2. Run TINYCUA agent inside a Docker container
3. Produce transcripts in a format the grading system can consume
4. Handle usage collection and cost tracking

---

## BaseAgent Interface (Required)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any


@dataclass(frozen=True)
class AgentTaskSpec:
    task_id: str
    task: dict[str, Any]
    workspace_path: str
    prompt: str
    timeout_seconds: int
    output_dir: Path
    model: str
    thinking: str | None = None
    models_config: dict[str, Any] | None = None
    lobster: dict[str, Any] | None = None


@dataclass
class AgentExecution:
    elapsed_time: float
    error: str | None = None
    gateway_proc: subprocess.Popen[str] | None = None
    agent_proc: subprocess.Popen[str] | None = None


class BaseAgent(ABC):
    @property
    @abstractmethod
    def expects_gateway(self) -> bool:
        """Whether this backend starts a long-running gateway process."""

    @property
    @abstractmethod
    def transcript_container_path(self) -> str:
        """Path to chat transcript inside the runtime container."""

    def prepare_grading_transcript(self, task_id: str) -> str:
        """Prepare and return the transcript path used for grading."""
        _ = task_id
        return self.transcript_container_path

    @abstractmethod
    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """Execute a task and return process handles, timing and error state."""

    @abstractmethod
    def collect_usage(self, task_id: str, output_dir: Path, elapsed_time: float) -> dict[str, Any]:
        """Collect token usage and cost for one task."""
```

---

## AgentTaskSpec Fields

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `str` | Unique task identifier (format: `{category}_{task_num}_{model}_{timestamp}_{run_id}`) |
| `task` | `dict[str, Any]` | Parsed task metadata from markdown (includes `automated_checks`, `env`, `skills`, `warmup`) |
| `workspace_path` | `str` | Host path to mounted workspace (read-only in container at `/app`) |
| `prompt` | `str` | Full task prompt with system prefix (includes timeout warning) |
| `timeout_seconds` | `int` | Maximum execution time in seconds |
| `output_dir` | `Path` | Host directory for output files (score.json, usage.json, agent.log, etc.) |
| `model` | `str` | Model identifier (e.g., `openrouter/openai/gpt-5.5`) |
| `thinking` | `str \| None` | Optional thinking/reasoning mode (e.g., `"high"`, `"low"`, `"off"`) |
| `models_config` | `dict \| None` | Optional custom provider configuration (API keys, base URLs) |
| `lobster` | `dict \| None` | Optional lobster workspace config (name, workspace path, env keys) |

### Task Dict Structure

The `task` dict contains fields parsed from the task markdown file:

```python
{
    "task_id": "01_Productivity_Flow_task_1",
    "category": "01_Productivity_Flow",
    "workspace_path": "/path/to/workspace",
    "prompt": "Full task description...",
    "timeout_seconds": 600,
    "automated_checks": "def grade(transcript, workspace_path):\n    ...",
    "env": "API_KEY_1\nAPI_KEY_2",  # newline-separated env var names
    "skills": "skill1\nskill2",  # newline-separated skill names
    "skills_path": "/path/to/skills",
    "warmup": "warmup command",
}
```

---

## Transcript Format

WildClawBench grading expects transcripts in **OpenClaw-compatible JSONL format**. Each line is a JSON object representing a message in the conversation.

### Expected Path

```
/root/.openclaw/agents/main/sessions/chat.jsonl
```

### JSONL Schema

Each line should be a JSON object with this structure:

```json
{
    "type": "message",
    "message": {
        "role": "assistant",
        "content": "Assistant response text",
        "usage": {
            "input": 1234,
            "output": 567,
            "cacheRead": 0,
            "cacheWrite": 0,
            "totalTokens": 1801,
            "cost": {
                "total": 0.0023
            }
        }
    }
}
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | `str` | Must be `"message"` for grading to process |
| `message.role` | `str` | `"assistant"` for tool calls and responses |
| `message.content` | `str` | The assistant's response text |
| `message.usage` | `dict` | Token counts and cost information |
| `message.usage.input` | `int` | Input/prompt tokens |
| `message.usage.output` | `int` | Output/completion tokens |
| `message.usage.cacheRead` | `int` | Cache read tokens |
| `message.usage.cacheWrite` | `int` | Cache write tokens |
| `message.usage.totalTokens` | `int` | Total tokens |
| `message.usage.cost.total` | `float` | Total cost in USD |

### Transcript Loader Behavior

The `transcript_loader.py` module:

1. Accepts a path string (default: `/root/.openclaw/agents/main/sessions/chat.jsonl`)
2. Falls back to the OpenClaw default path if no path provided
3. Reads the file and parses JSON
4. Supports three formats:
   - **JSON array**: List of message objects
   - **JSON object**: With `transcript`, `messages`, or `chat` key containing a list
   - **JSONL**: One JSON object per line (fallback parser)

---

## Grading Flow

### Step-by-Step Process

1. **Agent Execution**
   - `run_batch.py` calls `backend.run_task(spec)`
   - Agent runs inside Docker container
   - Transcript is written to container path

2. **Transcript Preparation**
   - `run_batch.py` calls `backend.prepare_grading_transcript(task_id)`
   - Adapter converts native transcript to OpenClaw-compatible JSONL
   - Returns path to the compatible transcript

3. **Ground Truth Injection**
   - Host `gt/` directory is copied into container at `/tmp_workspace/gt/`
   - Contains expected outputs and grading scripts

4. **Grading Script Execution**
   - `run_grading()` creates a Python script that:
     - Loads transcript using `transcript_loader.py`
     - Executes the `automated_checks` code from task metadata
     - Calls `grade(transcript=..., workspace_path=...)`
     - Outputs JSON scores to stdout
   - Script is copied into container and executed via `docker exec`

5. **Score Collection**
   - Scores are parsed from stdout (JSON format)
   - Written to `output_dir/score.json`
   - Format: `{"metric_name": 0.0-1.0, ...}`

### Grading Script Template

```python
import json
from _transcript_loader import load_transcript

_transcript = load_transcript("/path/to/transcript.jsonl")

# [automated_checks code from task metadata]
def grade(transcript, workspace_path):
    # Task-specific grading logic
    return {"metric1": 0.85, "metric2": 1.0}

result = grade(transcript=_transcript, workspace_path="/tmp_workspace")
print(json.dumps(result))
```

---

## Docker Container Requirements

### Image Structure

```dockerfile
FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    git ffmpeg curl wget chromium \
    python3-pip uv

# TINYCUA installation
COPY src/tinycua-sdk /build/tinycua-sdk
COPY src/tinycua /build/tinycua
RUN cd /build/tinycua && uv sync

# Tool environment binaries
RUN pip install mss Pillow pyautogui opencv-python yt-dlp

# Working directory
WORKDIR /tmp_workspace

ENTRYPOINT ["/bin/bash", "-c", "tail -f /dev/null"]
```

### Container Lifecycle

1. **Start**: Container runs with `tail -f /dev/null` (stays alive)
2. **Setup**: Workspace copied to `/tmp_workspace`, skills configured
3. **Execution**: Agent runs inside container
4. **Grading**: Transcript converted, grading script executed
5. **Cleanup**: Container removed after grading

### Volume Mounts

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `workspace_path` | `/app` | Read-only | Task workspace files |
| `output_dir` | N/A | N/A | Output collected via `docker cp` |

### Environment Variables

| Variable | Source | Purpose |
|----------|--------|---------|
| `OPENROUTER_API_KEY` | `.env` | API key for LLM provider |
| `OPENROUTER_BASE_URL` | `.env` | API endpoint URL |
| `BRAVE_API_KEY` | `.env` | For search tasks |
| Task-specific env vars | `task["env"]` | Injected from `.env` |

---

## TINYCUA Adapter Implementation Plan

### Required Components

1. **`TinyCUAAgent` class** (implements `BaseAgent`)
   - `expects_gateway`: `False` (TINYCUA doesn't need a gateway)
   - `transcript_container_path`: `/root/.openclaw/agents/main/sessions/chat.jsonl`
   - `run_task()`: Start container, run TINYCUA agent, wait for completion
   - `collect_usage()`: Parse transcript for token counts
   - `prepare_grading_transcript()`: Convert TINYCUA trace to OpenClaw JSONL

2. **Transcript Converter**
   - Convert TINYCUA's `BaseLoop` trace to OpenClaw JSONL format
   - Map tool calls, results, and timing information
   - Include token usage in each assistant message

3. **Docker Image**
   - Build `wildclawbench-tinycua:v1` image
   - Include TINYCUA SDK + CLI + native tools
   - Install system dependencies (git, ffmpeg, chromium, etc.)

4. **CLI Integration**
   - Register `tinycua` case in `run.sh`
   - Accept `--model`, `--category`, `--parallel` flags
   - Pass through to `run_batch.py`

### Key Mapping: TINYCUA → WildClawBench

| TINYCUA Concept | WildClawBench Equivalent | Notes |
|-----------------|-------------------------|-------|
| `Agent.run(query)` | `backend.run_task(spec)` | Single entry point |
| `BaseLoop` trace | `chat.jsonl` transcript | Must convert format |
| `Tool.to_config()` | Tool schemas in prompt | OpenAI-compatible format |
| `LanguageModel` | `model` + `models_config` | Provider config |
| `Skill` | `task["skills"]` | Injected via system prompt |
| `AgentConfig` | `hermes.yaml` equivalent | TINYCUA config file |

### Transcript Conversion Strategy

```python
# Pseudocode for transcript conversion
def convert_tinycua_trace_to_openclaw(trace: list[dict]) -> list[dict]:
    """Convert TINYCUA trace to OpenClaw-compatible JSONL."""
    messages = []
    for entry in trace:
        if entry["type"] == "assistant_message":
            messages.append({
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": entry["content"],
                    "usage": {
                        "input": entry["input_tokens"],
                        "output": entry["output_tokens"],
                        "cacheRead": entry.get("cache_read_tokens", 0),
                        "cacheWrite": entry.get("cache_write_tokens", 0),
                        "totalTokens": entry["total_tokens"],
                        "cost": {"total": entry.get("cost_usd", 0.0)},
                    },
                },
            })
    return messages
```

---

## Usage Collection

### Expected Output

```json
{
    "input_tokens": 12345,
    "output_tokens": 6789,
    "cache_read_tokens": 0,
    "cache_write_tokens": 0,
    "total_tokens": 19134,
    "cost_usd": 0.0456,
    "request_count": 15,
    "elapsed_time": 123.45
}
```

### Collection Methods

1. **Primary**: Parse transcript JSONL for `usage` fields
2. **Fallback**: Parse agent.log for token usage patterns
3. **Manual**: Count requests and estimate from model pricing

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Transcript format mismatch | Grading fails | Test with sample transcripts early |
| Docker image too large | Slow CI | Multi-stage build, minimize layers |
| Tool schema incompatibility | Agent can't call tools | Verify OpenAI-compatible format |
| Timeout handling | Incomplete tasks | Implement graceful shutdown |
| Usage tracking gaps | Cost reporting incomplete | Multiple collection methods |

---

## Next Steps

1. **Phase 1**: Implement `TinyCUAAgent` adapter class
2. **Phase 2**: Build Docker image with TINYCUA
3. **Phase 3**: Implement transcript converter
4. **Phase 4**: Test with single task
5. **Phase 5**: Run full 60-task benchmark

---

## References

- [WildClawBench GitHub](https://github.com/InternLM/WildClawBench)
- [WildClawBench Technical Report](https://arxiv.org/abs/2605.10912)
- [HermesAgent Adapter](https://github.com/InternLM/WildClawBench/tree/main/src/agents/hermesagent) (reference implementation)
- [TINYCUA SDK Agent](../src/tinycua-sdk/tinycua_sdk/agent/agent.py)
