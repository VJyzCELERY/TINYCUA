# WildClawBench Adapter Contract

**Status**: Research Complete
**Created**: 2026-06-05
**Last Updated**: 2026-06-05
**Source**: [InternLM/WildClawBench](https://github.com/InternLM/WildClawBench)
**Upstream Commit Reviewed**: `86d71447413d38f38740a021cb776f64eb396ee0` (2026-05-19)

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
        """Prepare and return the transcript path used for grading (optional/default hook).

        By default, returns `self.transcript_container_path` unchanged.
        Override this method if TinyCUA cannot write OpenClaw-compatible JSONL
        directly to `transcript_container_path` and needs to convert a native
        transcript instead.
        """
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
| `workspace_path` | `str` | Host path to the task workspace root — contains `exec/` (task files), `gt/` (ground truth for grading), and optionally `tmp/`. Only `exec/` is visible to the agent; `gt/` is injected during grading only. |
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
    "file_path": "/absolute/path/to/task.md",  # upstream file path (adapter-relevant for debugging/provenance)
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

Each line should be a JSON object with this structure. The `content` field supports two shapes: a plain string for simple text responses, and a list of content blocks for responses that include tool use.

**String content (simple text response):**

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

**List content (response with tool-use blocks):**

```json
{
    "type": "message",
    "message": {
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": "I'll create that file for you."
            },
            {
                "type": "tool_use",
                "id": "call_abc123",
                "name": "write_file",
                "input": {
                    "command": "write_file",
                    "path": "/tmp_workspace/output.txt",
                    "content": "file contents here"
                }
            }
        ],
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

> **Important**: Upstream safety graders (e.g., `06_Safety_Alignment_task_8_malicious_comments.md`) parse `content` as a list and extract blocks with `type in ("tool_use", "toolCall")` to detect harmful tool writes. If TinyCUA drops tool-use blocks from the transcript, safety grading will produce false negatives. The transcript converter **must** preserve all tool calls and their inputs as content blocks rather than converting them to plain text.

**User message record:**

```json
{
    "type": "message",
    "message": {
        "role": "user",
        "content": "User prompt or instruction text"
    }
}
```

**Tool result record (top-level) — OpenClaw/HermesAgent style:**

```json
{
    "type": "toolResult",
    "toolResult": {
        "callId": "call_abc123",
        "tool_call_id": "call_abc123",
        "content": "Tool execution output or result string"
    }
}
```

> **Upstream variants**: The adapter must handle multiple tool-result representations from different upstream harnesses:
>
> - **HermesAgent `compat_transcript.py`** emits top-level `toolResult` records with `tool_call_id` (snake_case).
> - **OpenClaw native format** uses `callId` (camelCase) for the same purpose.
> - **Codex/Anthropic-style transcripts** encode tool results as user-message content blocks: `{"type": "message", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_abc123", "content": "..."}]}}`.
>
> For maximum compatibility, the adapter **should** emit top-level `toolResult` records that include **both** `callId` and `tool_call_id` fields (both pointing to the same call ID). When receiving upstream transcripts for merging or comparison, the adapter should accept any of these three shapes.

**User message with Codex/Anthropic-style tool-result content blocks:**

```json
{
    "type": "message",
    "message": {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "call_abc123",
                "content": "Tool execution output or result string"
            }
        ]
    }
}
```

> **Full compatibility rule**: The adapter **must** preserve user messages, tool-use inputs, tool results, call IDs, and decoded arguments in the transcript — even if current safety graders primarily inspect assistant tool-use inputs. Dropping user prompts or tool results breaks upstream compatibility shims (HermesAgent `compat_transcript.py` emits user entries and top-level `toolResult` records with `tool_call_id`; Codex emits `tool_result` content blocks inside user messages with `tool_use_id`) and may cause future graders to fail.

### Content Block Types

| Block Type | Shape | Description |
|------------|-------|-------------|
| `text` | `{"type": "text", "text": "..."}` | Plain text content |
| `tool_use` | `{"type": "tool_use", "id": "...", "name": "...", "input": {...}}` | Agent-initiated tool call (OpenAI-style) |
| `toolCall` | `{"type": "toolCall", "name": "...", "arguments": {...}}` | Agent-initiated tool call (alternate format) |
| `tool_result` | `{"type": "tool_result", "tool_use_id": "...", "content": "..."}` | Tool execution result inside user-message content (Codex/Anthropic-style) |

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | `str` | `"message"` for message records, `"toolResult"` for tool result records |
| `message.role` | `str` | `"assistant"` for tool calls and responses, `"user"` for user prompts |
| `message.content` | `str \| list` | Plain string text **or** list of content blocks (text, tool_use, toolCall, tool_result) |
| `message.usage` | `dict` | Token counts and cost information (assistant records only) |
| `message.usage.input` | `int` | Input/prompt tokens |
| `message.usage.output` | `int` | Output/completion tokens |
| `message.usage.cacheRead` | `int` | Cache read tokens |
| `message.usage.cacheWrite` | `int` | Cache write tokens |
| `message.usage.totalTokens` | `int` | Total tokens |
| `message.usage.cost.total` | `float` | Total cost in USD |
| `tool_use.id` | `str` | Call ID matching the originating toolResult record |
| `tool_use.name` | `str` | Tool/function name (e.g., `"write_file"`) |
| `toolResult.callId` | `str` | ID matching the originating tool_use/toolCall block (OpenClaw camelCase) |
| `toolResult.tool_call_id` | `str` | ID matching the originating tool_use/toolCall block (HermesAgent snake_case) |
| `toolResult.content` | `str \| list` | Tool execution output |
| `tool_result.tool_use_id` | `str` | ID matching the originating tool_use block (Codex/Anthropic content-block variant) |

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
   - Host `<workspace_path>/gt/` is copied into container at `/tmp_workspace/gt/` (only at grading time — never during agent execution)
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
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    git ffmpeg curl wget chromium \
    python3-pip uv

# TINYCUA installation
COPY src/tinycua-sdk /build/tinycua-sdk
COPY src/tinycua /build/tinycua
RUN cd /build/tinycua && uv sync

# Tool environment binaries
# Image/video tool dependencies (illustrative — review at implementation time)
# Pillow: image manipulation (§ Native Tool Coverage option 4)
# pyautogui: screenshot capture
# yt-dlp: video download
RUN uv pip install --system Pillow pyautogui yt-dlp

# Working directory
WORKDIR /tmp_workspace

ENTRYPOINT ["/bin/bash", "-c", "tail -f /dev/null"]
```

### Container Lifecycle

1. **Start**: Container runs with `tail -f /dev/null` (stays alive)
2. **Setup**: Mount `<spec.workspace_path>/exec` read-only at `/app`, then copy `/app` to `/tmp_workspace` for the agent. If `<spec.workspace_path>/tmp` exists, copy it to `/tmp_workspace/tmp`. Skills are copied into the configured in-container skills root.
3. **Warmup**: Execute `task["warmup"]` inside the container after setup and before agent launch. If the warmup string is non-empty and non-comment, split it into lines and execute each line via `docker exec`. Fail fast on non-zero exit. Warmup prepares task services, fixtures, or other runtime state that the agent expects to be available. Reference: upstream `src/utils/docker_utils.py::run_warmup`.
4. **Execution**: Agent runs inside container, operating on `/tmp_workspace`
5. **Grading**: Copy `<workspace_path>/gt` into `/tmp_workspace/gt/` (only at grading time), then convert transcript and execute grading script
6. **Cleanup**: Container removed after grading

### Workspace Structure

The `workspace_path` points to a directory with this layout:

```
<workspace_path>/
├── exec/          # Task files — mounted read-only at /app, then copied to /tmp_workspace for the agent
├── gt/            # Ground truth — copied into /tmp_workspace/gt/ ONLY during grading (must be hidden from the agent)
└── tmp/           # Optional warmup artifacts — copied to /tmp_workspace/tmp/ if present
```

The adapter **must** derive `exec_path = os.path.join(spec.workspace_path, "exec")` before starting the container. Mounting the entire `workspace_path` to `/app` would leak `gt/` into the agent environment and invalidate benchmark scores.

### Volume Mounts

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `<workspace_path>/exec` | `/app` | Read-only | Task files (agent-visible only) |
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
   - `run_task()`: Start container, copy workspace, execute warmup, run TINYCUA agent, wait for completion
   - `collect_usage()`: Parse transcript for token counts
   - `prepare_grading_transcript()`: Convert TINYCUA trace to OpenClaw JSONL

2. **Transcript Converter**
   - Capture TinyCUA SDK events via `Agent.run(stream=True)` or instrument `BaseLoop` to persist the internal `working` message list
   - Convert captured events/messages to OpenClaw JSONL format
   - Map assistant messages with `tool_calls[*].function.name` and JSON-decoded `arguments` to content blocks
   - Track per-response usage from `response.usage` stream events (Strategy A) and pass as `per_message_usage` to the converter; if using Strategy B, pass `None` and populate usage via `collect_usage()` instead
   - **Do not embed cumulative usage totals in every assistant message** — WildClawBench sums `message.usage` across assistant records, so cumulative values will over-count

3. **Docker Image**
   - Build `wildclawbench-tinycua:v1` image
   - Include TINYCUA SDK + CLI + native tools
   - Install system dependencies (git, ffmpeg, chromium, etc.)

4. **CLI Integration**
   - Register `tinycua` case in `run.sh`
   - Accept `--model`, `--category`, `--parallel` flags
   - Pass through to `run_batch.py`

   > **Required upstream changes**: The CLI registration is not limited to `run.sh`. Three files must be updated for `tinycua` to be selectable and executable:

   | File | Change |
   |------|--------|
   | `script/run.sh` | Add `tinycua` case in the usage string and case statement, forwarding flags to `run_batch.py` |
   | `src/utils/cli_args.py` | Add `"tinycua"` to the `--agent-backend` choices list (currently `["openclaw", "claudecode", "codex", "hermesagent"]`) |
   | `eval/run_batch.py` | Add `elif args.agent_backend == "tinycua"` branch that imports and constructs `TinyCUAAgent` |

   Without the `cli_args.py` change, argparse will reject `--agent-backend tinycua` with an invalid choice error. Without the `run_batch.py` change, the backend will not be instantiated even if the parser accepts it.

### Key Mapping: TINYCUA → WildClawBench

| TINYCUA Concept | WildClawBench Equivalent | Notes |
|-----------------|-------------------------|-------|
| `Agent.run(query)` | `backend.run_task(spec)` | Single entry point |
| `Agent.run(stream=True)` event stream | `chat.jsonl` transcript | Capture stream events and convert to JSONL |
| `BaseLoop` internal `working` messages | `chat.jsonl` transcript | Alternative: instrument loop to persist message list |
| `Tool.to_config()` | Tool schemas in prompt | OpenAI-compatible format |
| `LanguageModel` | `model` + `models_config` | Provider config |
| `Skill` | `task["skills"]` + `task["skills_path"]` | Copied as task skill directories into the container before execution (see Skills Setup below) |
| `AgentConfig` | `hermes.yaml` equivalent | TINYCUA config file |

### Skills Setup

Skills in WildClawBench are **not** injected via prompt text. The task parser returns:

- `task["skills"]`: Newline-separated relative skill-directory paths (e.g., `"skill1\nskill2"`)
- `task["skills_path"]`: Host root directory containing those skill directories

The adapter **must** call `setup_skills(...)` (or equivalent) to copy each listed skill directory from `task["skills_path"]` into TinyCUA's configured in-container skills root **before** the agent starts execution. Prompt text alone is not sufficient — the agent needs the actual skill files and resources on disk to load them.

> **Implementation note**: `setup_skills` is **not** an upstream WildClawBench utility — no such function exists in the pinned upstream commit (`86d7144`). The adapter must implement this itself. The function should accept a list of skill directory names, a host source path (`task["skills_path"]`), and a container-internal destination path, then copy each skill directory into the container via `docker cp` or volume mount. A minimal implementation is: split `task["skills"]` on newlines to get skill names, then for each non-empty name, copy `<skills_path>/<name>` to `<skills_root>/<name>` inside the running container.

### Transcript Conversion Strategy

The adapter must capture the TinyCUA conversation history and convert it to OpenClaw JSONL. There are two viable capture strategies:

**Strategy B — Instrument `BaseLoop` (recommended)**:
Subclass `BaseLoop` or wrap `Agent` to persist the internal `working` message list after execution. The `working` list already contains properly shaped assistant messages (`role: "assistant"`, `content: str`, `tool_calls: list[{id, type: "function", function: {name, arguments: str}}]`) and tool-result messages (`role: "tool_result"`, `call_id: str`, `content: str | list[ContentPart]`). This is the only strategy that can produce a contract-complete transcript (preserving user messages, tool-use inputs, tool results, call IDs, and decoded arguments) with the current TinyCUA SDK event stream.

**Strategy A — Stream capture (not recommended until tool-result events exist)**:
Run `Agent.run(query, stream=True)` and record every SDK-normalized event. The event stream includes `response.output_text.delta` (text content), `response.output_item.added` (new item including function calls), `response.function_call_arguments.delta` (incremental argument chunks), `response.function_call_arguments.done` (final arguments for a call), `tool_call.ready` (tool call finalized and ready to dispatch), `response.tool_call.delta` (legacy tool-call delta — an alternate shape emitted by some providers and compatibility layers that must be normalized into the same `tool_use` content blocks as `response.output_item.added` plus `response.function_call_arguments.*` / `tool_call.ready`), `response.usage` (token counts), and `response.completed` (finish reason). The converter assembles these into assistant messages by collecting argument deltas into complete arguments, then mapping each finalized function call to a `tool_use` content block.

> **⚠ Strategy A cannot preserve tool results**: The current SDK `LLMEvent` union (`src/tinycua-sdk/tinycua_sdk/agent/events.py`) emits assistant tool-call events but does **not** emit tool-result events. Tool results are appended only to the internal `working_messages` list after tool execution (`src/tinycua-sdk/tinycua_sdk/agent/loop.py`). As written, an implementer following Strategy A can preserve assistant `tool_use` blocks but **cannot** preserve `toolResult` records — which violates the full compatibility rule above. Strategy A is only viable if paired with loop instrumentation to capture tool results, or after a dedicated `tool_result.completed` stream event is added to the SDK.
>
> **SDK version**: Based on TINYCUA SDK as of commit `79d3fbe` (2026-06-05). If the SDK later adds tool-result stream events (e.g., `tool_result.completed`), re-evaluate Strategy A viability.

**Reasoning-event policy**: `response.reasoning.delta` and `response.reasoning.done` may be emitted by reasoning-capable models. The adapter should **not** serialize hidden reasoning into OpenClaw-visible assistant content unless explicitly required by the task, but it should account for these events deliberately — either by discarding them or by storing them in a non-graded side channel — and document the chosen behavior so that transcript consumers can predict what is present.

### Transcript Conversion Pseudocode

See [Implementation Guidance](#implementation-guidance) below for the full conversion function. The key contract requirements are:
- Input: `BaseLoop` working message list (roles: system, user, assistant, tool_result)
- Output: OpenClaw-compatible JSONL records
- Must preserve tool-use content blocks for safety grading
- Must coerce nullable token counts to non-negative integers

> **Note on usage**: The `BaseLoop` working message list does not carry per-message usage. When using Strategy B, the caller must collect usage separately (e.g., from `response.usage` stream events) and pass per-assistant-message usage via the `per_message_usage` parameter. If per-message usage is unavailable, pass `None` and let `collect_usage()` populate the upstream `usage.json` schema with separately accumulated totals — do **not** embed a cumulative total in every assistant message record, as WildClawBench sums `message.usage` across all assistant records and will over-count tokens and cost. When cost data is unavailable, the adapter should set `usage.cost.total` to `0.0` and omit `cacheRead`/`cacheWrite` fields rather than emitting `None` values.

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

### Usage Fallback Contract

`collect_usage()` **must never return `{}`**. Upstream `eval/run_batch.py` calls `save_usage()` which immediately indexes required fields — returning an empty dict raises `KeyError` and crashes the benchmark run after grading.

When transcript parsing fails, the container/transcript is unavailable, or any collection method cannot populate all required fields, the adapter **must** return a zero-filled dict with all required keys:

```json
{
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_read_tokens": 0,
    "cache_write_tokens": 0,
    "total_tokens": 0,
    "cost_usd": 0.0,
    "request_count": 0,
    "elapsed_time": 0.0
}
```

The `elapsed_time` field should reflect the actual execution duration when available (passed from `AgentExecution.elapsed_time`), but defaults to `0.0` if uncollectable. This fallback ensures downstream usage aggregation never encounters a missing key.

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Transcript format mismatch | Grading fails | Test with sample transcripts early |
| Docker image too large | Slow CI | Multi-stage build, minimize layers |
| Tool schema incompatibility | Agent can't call tools | Verify OpenAI-compatible format |
| Timeout handling | Incomplete tasks | Kill agent process on timeout, return `error=None` so WildClawBench still grades partial workspace state (see [Timeout Handling Contract](#timeout-handling-contract) below) |
| Usage tracking gaps | Cost reporting incomplete | Multiple collection methods |
| Native tool coverage gaps | Cannot complete email/calendar/image/video tasks | See [Native Tool Coverage](#native-tool-coverage) — implement missing tools or scope categories out |

---

## Timeout Handling Contract

When the agent exceeds `spec.timeout_seconds`, the adapter **must** follow this contract:

1. **Kill the agent process** — Send `SIGTERM`, wait briefly, then `SIGKILL` if necessary.
2. **Preserve elapsed time** — Record the actual execution duration up to the kill point.
3. **Return `AgentExecution(error=None, ...)`** — Do **not** set the `error` field on timeout.

**Why `error=None` on timeout**: Upstream `eval/run_batch.py` only grades errored executions for `CodexAgent` and `ClaudeCodeAgent` (hard-coded tuple in `run_batch.py`). A `TinyCUAAgent` would not match that tuple, so returning `AgentExecution.error` on timeout would cause `run_grading()` to be skipped entirely — leaving benchmark results without scores instead of grading the partial workspace/transcript state. Existing OpenClaw and HermesAgent runners kill timed-out processes but return `error=None`, which keeps grading enabled.

This means the adapter kills the agent but still returns a successful execution, allowing WildClawBench to grade whatever partial work the agent completed before the timeout. The graded result reflects the agent's performance within the time limit.

---

## Native Tool Coverage

WildClawBench tasks span six categories, each requiring different tool capabilities. The table below maps WildClawBench's required tool categories to TINYCUA's current native tool coverage and identifies gaps that must be resolved (or explicitly scoped out) before the adapter can complete full benchmark tasks.

| WildClawBench Capability | Required For | TINYCUA Coverage | Status |
|--------------------------|-------------|-------------------|--------|
| **Shell execution** | Most categories — system commands, scripting | `run_shell` | Covered |
| **File operations** | Read/write/edit files, directory traversal | `read_file`, `write_file`, `edit_file`, `list_files` | Covered |
| **Web access** | Search, page fetching, API calls | `fetch_url` | Covered |
| **Python execution** | Data processing, computation tasks | `run_python` | Covered |
| **Email** | Email-aware tasks (compose, read, parse) | — | **Gap** |
| **Calendar** | Calendar-aware tasks (schedule, query events) | — | **Gap** |
| **Image processing** | Image generation, manipulation, analysis | — | **Gap** |
| **Video processing** | Video generation, editing, analysis | — | **Gap** |

### Gap Analysis

- **email**: No email tool exists. Tasks in categories that reference email interactions will fail or produce incomplete results.
- **calendar**: No calendar tool exists. Tasks requiring schedule awareness or event management cannot be completed.
- **image**: No image generation or manipulation tool exists. Tasks requiring image creation or editing will fail. (Note: TINYCUA SDK supports image *attachment* via `FileAttachment`, but this is read-only input, not tool-driven generation.)
- **video**: No video tool exists. Tasks requiring video generation, editing, or frame extraction cannot be completed.

### Mitigation Options

1. **Implement missing tools** — Add native tools for email (IMAP/SMTP), calendar (CalDAV/Google Calendar API), image (Pillow/ImageMagick integration), and video (ffmpeg wrapper). This is the most complete solution but increases adapter scope.
2. **Scope categories out** — Exclude task categories that require missing tools from the initial benchmark run. Document the exclusion and report partial-category scores.
3. **Delegate to upstream tools** — If the Docker container provides system-level tools (e.g., `ffmpeg` for video, `python3` with `Pillow` for image), implement thin wrapper tools that shell out to these binaries. This works for image/video but not for email/calendar which require API credentials and auth flows.
4. **Hybrid approach** — Implement thin wrappers for tools that have system-level equivalents (image, video) and scope out categories that require API-based tools (email, calendar) in the initial milestone.

> **Recommendation**: Start with option 4 — implement image and video wrappers using existing container dependencies (`ffmpeg`, `Pillow`), and scope out email/calendar tasks for the initial 60-task benchmark run. This maximizes category coverage while keeping the initial adapter scope manageable.

---

## Next Steps

See `src/tinycua/specs/wildclawbench-spike/design.md` § Implementation Phases for the implementation roadmap and milestone status.

---

## Implementation Guidance

### Transcript Conversion Pseudocode

```python
# Pseudocode for transcript conversion from BaseLoop working messages
import json
from pathlib import Path


def _usage_int(value: object) -> int:
    """Coerce a nullable token count to a non-negative int.

    TinyCUA's ``TokenUsage`` type permits ``None`` for all three token
    fields, and provider events may surface partial usage.  WildClawBench's
    ``extract_usage_from_jsonl()`` adds these values into integer totals,
    so a JSON ``null`` (Python ``None``) would cause ``TypeError``.  This
    helper ensures every value written to the transcript is a valid int.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def convert_working_messages_to_openclaw(
    working: list[dict],
    per_message_usage: list[dict[str, int]] | None = None,
) -> list[dict]:
    """Convert TinyCUA BaseLoop working messages to OpenClaw-compatible JSONL.

    The working message list contains:
      - role: "system" (skip — not in OpenClaw format)
      - role: "user" (map to user message records)
      - role: "assistant" with optional tool_calls (map to assistant message records)
      - role: "tool_result" with call_id and content (map to toolResult records)

    ``per_message_usage`` is an optional list of usage dicts (one per assistant
    message), where each dict has keys ``input_tokens``, ``output_tokens``,
    ``total_tokens``.  If provided, each assistant message record receives the
    corresponding usage entry.  If ``None``, all assistant messages receive
    zeroed usage (usage is tracked separately via ``collect_usage()``).

    WildClawBench's ``extract_usage_from_jsonl()`` **sums** the ``usage``
    fields across assistant records.  Embedding a cumulative total in every
    assistant message will over-count tokens and cost.  The caller must
    therefore supply per-response usage (Strategy A: from ``response.usage``
    stream events) or omit usage from the transcript and populate it via
    ``collect_usage()``.

    Preserves tool-use content blocks so upstream safety graders can
    inspect tool inputs (e.g., file writes, shell commands).

    **Transcript usage fields must be numeric and must never be ``null``.**
    Token counts from the SDK are coerced through ``_usage_int()`` so that
    JSON serialisation never emits ``null`` for ``input``, ``output``, or
    ``totalTokens``.
    """
    messages: list[dict] = []
    usage_iter = iter(per_message_usage) if per_message_usage else None

    for entry in working:
        role = entry.get("role")

        if role == "system":
            continue

        if role == "user":
            messages.append({
                "type": "message",
                "message": {
                    "role": "user",
                    "content": entry.get("content", ""),
                },
            })

        elif role == "assistant":
            tool_calls = entry.get("tool_calls", [])
            content = _build_content_blocks(entry, tool_calls)

            # Each assistant message gets its own per-response usage entry.
            # When per_message_usage is None, zero-fill so the record is
            # present but does not inflate totals.
            msg_usage = next(usage_iter, None) if usage_iter else None
            raw_usage = msg_usage or {}

            messages.append({
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "usage": {
                        "input": _usage_int(raw_usage.get("input_tokens")),
                        "output": _usage_int(raw_usage.get("output_tokens")),
                        "cacheRead": 0,
                        "cacheWrite": 0,
                        "totalTokens": _usage_int(raw_usage.get("total_tokens")),
                        "cost": {"total": 0.0},
                    },
                },
            })

        elif role == "tool_result":
            call_id = entry.get("call_id", "")
            messages.append({
                "type": "toolResult",
                "toolResult": {
                    "callId": call_id,
                    "tool_call_id": call_id,
                    "content": entry.get("content", ""),
                },
            })

    return messages


def _build_content_blocks(
    entry: dict, tool_calls: list[dict] | None = None,
) -> str | list[dict]:
    """Build content field from an assistant message.

    If the entry has tool_calls (OpenAI-style with function.name and
    function.arguments as a JSON string), return a list of content
    blocks (text block + tool_use blocks) so safety graders can inspect
    tool inputs. Otherwise return plain string content.
    """
    if not tool_calls:
        return entry.get("content") or ""

    blocks: list[dict] = []
    text = entry.get("content") or ""
    if text:
        blocks.append({"type": "text", "text": text})

    for tc in tool_calls:
        func = tc.get("function", {})
        # arguments is a JSON string — decode it for the content block
        try:
            args = json.loads(func.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            raw = func.get("arguments", "{}")
            args = raw if raw is not None else {}

        blocks.append({
            "type": "tool_use",
            "id": tc.get("id") or tc.get("call_id", ""),
            "name": func.get("name", ""),
            "input": args,
        })
    return blocks


def write_openclaw_jsonl(records: list[dict], path: Path) -> None:
    """Write converted records to an OpenClaw-compatible JSONL file."""
    with path.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
```

---

## References

- [WildClawBench GitHub](https://github.com/InternLM/WildClawBench)
- [WildClawBench Technical Report](https://arxiv.org/abs/2605.10912)
- [HermesAgent Adapter](https://github.com/InternLM/WildClawBench/tree/86d71447413d38f38740a021cb776f64eb396ee0/src/agents/hermesagent) (reference implementation)
- [TINYCUA SDK Agent](../../src/tinycua-sdk/tinycua_sdk/agent/agent.py)
