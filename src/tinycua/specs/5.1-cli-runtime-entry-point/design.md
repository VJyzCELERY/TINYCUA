# Design Document: TinyCUA CLI / Runtime Entry Point

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-13

---

## Overview

This design adds a CLI entry point (`tinycua run`) to the `tinycua` subproject that accepts a task prompt and timeout, configures a local model endpoint, executes the TinyCUA agent via `create_tinycua_agent()`, and produces transcript/log artifacts in a format compatible with WildClawBench grading. The CLI replaces the current no-op placeholder and provides the stable invocation interface that WildClawBench containers will use in Milestone 5.2.

---

## Architecture

### Component Overview

```
CLI (tinycua run)
    │
    ├── Argument Parser (argparse)
    │       ├── prompt (positional, required)
    │       ├── --timeout (default: 600)
    │       ├── --output-dir (default: /tmp_workspace/results)
    │       ├── --workspace (default: /tmp_workspace)
    │       ├── --base-url (override TINYCUA_BASE_URL)
    │       ├── --api-key (override TINYCUA_API_KEY)
    │       ├── --model (override TINYCUA_MODEL)
    │       └── --verbose
    │
    ├── Config Loader
    │       ├── Reads env vars: TINYCUA_BASE_URL, TINYCUA_API_KEY, TINYCUA_MODEL
    │       ├── Applies CLI overrides
    │       └── Validates required config (base_url, api_key)
    │
    ├── Agent Runner
    │       ├── create_tinycua_agent(session_config=...)
    │       ├── Sets workspace directory on session
    │       ├── agent.run(prompt, stream=False)
    │       └── Timeout watchdog (thread-based)
    │
    ├── Transcript Writer
    │       ├── Captures BaseLoop working messages
    │       ├── Converts to OpenClaw-compatible JSONL
    │       └── Writes to output_dir/transcript.jsonl
    │
    └── Log Writer
            ├── Structured JSON lines
            ├── Events: start, config, agent_run, complete, error, timeout
            └── Writes to output_dir/agent.log
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/cli/main.py` | Modified | Replace no-op with `tinycua run` subcommand |
| `tinycua/cli/run.py` | New | `run` subcommand implementation |
| `tinycua/cli/config.py` | New | Environment variable and CLI config loading |
| `tinycua/cli/transcript.py` | New | Transcript capture and JSONL writing |
| `tinycua/cli/logging.py` | New | Structured agent log writing |
| `tinycua/factory.py` | Unchanged | Already provides `create_tinycua_agent()` |
| `pyproject.toml` | Modified | Update `[project.scripts]` entry if needed |

### Requirements Traceability

| FR | Design Component(s) | Notes |
|----|---------------------|-------|
| FR-001 | Argument Parser | Positional argument for task prompt |
| FR-002 | Argument Parser | `--timeout` flag, default 600 |
| FR-003 | Argument Parser | `--output-dir` flag, default `/tmp_workspace/results` |
| FR-004 | Argument Parser | `--workspace` flag, default `/tmp_workspace` |
| FR-005 | Config Loader | Reads `TINYCUA_BASE_URL`, `TINYCUA_API_KEY` env vars; CLI overrides via `--base-url`, `--api-key` |
| FR-006 | Config Loader | Reads `TINYCUA_MODEL` env var; CLI override via `--model` |
| FR-007 | Agent Runner | Calls `create_tinycua_agent(session_config=...)` |
| FR-008 | Agent Runner | Calls `agent.run(prompt, stream=False)` |
| FR-009 | Transcript Writer | Writes `transcript.jsonl` to output directory |
| FR-010 | Log Writer | Writes `agent.log` to output directory |
| FR-011 | Agent Runner | Sets workspace directory on session |
| FR-012 | Agent Runner | Exit code 0 on successful completion |
| FR-013 | Agent Runner | Exit code 1 on general errors |
| FR-014 | Agent Runner + Timeout Watchdog | Exit code 124 on timeout |
| FR-015 | Timeout Watchdog | `threading.Timer` with cooperative cancellation via `asyncio.Event`; SIGTERM/SIGKILL deferred to Milestone 5.2 |
| FR-016 | Argument Parser | `--verbose` flag for debug logging |

---

## Data Model

### CLI Arguments

```python
@dataclass
class RunConfig:
    """Configuration for a single tinycua run invocation."""
    prompt: str                          # Required task prompt
    timeout: int = 600                   # Max execution seconds
    output_dir: Path = Path("/tmp_workspace/results")
    workspace: Path = Path("/tmp_workspace")
    base_url: str                        # OpenAI-compatible endpoint (required)
    api_key: str                         # API key (required)
    model: str | None = None             # Model identifier (required via CLI or TINYCUA_MODEL)
    verbose: bool = False                # Debug logging
```

### Transcript Record (OpenClaw-compatible JSONL)

```python
# Each line is a JSON object
TranscriptRecord = dict  # {"type": "message"|"toolResult", "message"|"toolResult": {...}}
```

See `specs/wildclawbench-adapter/adapter-contract.md` for the full schema.

### Agent Log Entry

```python
@dataclass
class LogEntry:
    timestamp: str       # ISO 8601
    event: str           # "start" | "config" | "agent_run" | "complete" | "error" | "timeout"
    level: str           # "info" | "warning" | "error"
    data: dict           # Event-specific payload
```

---

## API / Interface Contracts

### CLI Entry Point

```bash
# Basic usage
tinycua run "Create a file called hello.txt with content 'Hello, World!'"

# With options
tinycua run \
  --timeout 120 \
  --output-dir ./results \
  --workspace /tmp_workspace \
  --base-url http://localhost:8080/v1 \
  --api-key sk-local \
  --model llama-3-8b \
  --verbose \
  "Summarize the files in the current directory"
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Successful completion |
| 1 | General error (invalid args, agent crash, endpoint unreachable) |
| 124 | Timeout (agent killed after exceeding timeout) |

### Error Handling

| Error Case | Exit Code | Log Event | Notes |
|------------|-----------|-----------|-------|
| Missing prompt | 1 | N/A | argparse validation error |
| Invalid timeout (non-integer) | 1 | N/A | argparse validation error |
| Missing base_url | 1 | N/A | Config validation error |
| Missing api_key | 1 | N/A | Config validation error |
| Output dir not writable | 1 | N/A | Pre-flight check before agent execution |
| Endpoint unreachable | 1 | error | Agent fails to connect to LLM |
| Agent crashes | 1 | error | Unhandled exception in agent execution |
| Timeout exceeded | 124 | timeout | Cooperative cancellation via asyncio.Event; SIGTERM/SIGKILL deferred to 5.2 |
| Successful completion | 0 | complete | Transcript and log written |

---

## Implementation Phases

### Phase 1 — MVP (Required for initial release)

- [ ] Implement `RunConfig` dataclass and config loading from env vars + CLI flags
- [ ] Implement `tinycua run` subcommand with argparse
- [ ] Implement agent runner with `create_tinycua_agent()` integration
- [ ] Implement timeout watchdog using `threading.Timer` with cooperative cancellation (SIGTERM/SIGKILL deferred to Milestone 5.2 per spec FR-015)
- [ ] Implement transcript writer (capture BaseLoop working messages → OpenClaw JSONL)
- [ ] Implement structured agent log writer
- [ ] Update `pyproject.toml` entry point if needed
- [ ] Write unit tests for argument parsing, config loading, exit codes
- [ ] Write integration test with mock LLM endpoint

### Phase 2 — Enhancements (Post-MVP, if needed)

- [ ] Streaming output support (`--stream` flag for real-time progress)
- [ ] Verbose output formatting with Rich library
- [ ] Signal handling for graceful shutdown on SIGINT/SIGTERM from external processes
- [ ] Support reading prompt from stdin or file (`--prompt-file`)

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use `argparse` with subcommands rather than a standalone script.
   - **Reason**: The CLI may grow additional subcommands (e.g., `tinycua serve`, `tinycua benchmark`). Subcommands provide a clean extension point without breaking backward compatibility.
   - **Alternatives Considered**: Standalone script with `fire` or `click` — rejected because `argparse` is stdlib and the project already depends on minimal external packages.

2. **Decision**: Use `threading.Timer` for timeout enforcement rather than `subprocess.run(timeout=...)`.
   - **Reason**: The agent runs in-process (not as a subprocess). A background thread can set an `asyncio.Event` after the timeout, allowing the agent run to be interrupted cooperatively. SIGTERM/SIGKILL enforcement is deferred to Milestone 5.2 per spec FR-015.
   - **Alternatives Considered**: `signal.alarm()` — rejected because it only works in the main thread and doesn't support graceful cleanup.

3. **Decision**: Write transcript using Strategy B (BaseLoop working message list) rather than Strategy A (stream capture).
   - **Reason**: Strategy B is recommended by the adapter contract research (`specs/wildclawbench-adapter/adapter-contract.md`) because it preserves tool-use content blocks and tool results, which are required for WildClawBench safety grading.
   - **Alternatives Considered**: Strategy A (stream capture) — rejected because the current SDK does not emit tool-result events, making it impossible to preserve the full transcript.

4. **Decision**: Use structured JSON lines for agent logs rather than free-form text.
   - **Reason**: Machine-parseable logs enable automated analysis and integration with WildClawBench artifact collection. JSON lines are append-only and don't require complex parsing.
   - **Alternatives Considered**: Python `logging` with text formatter — rejected because it's harder to parse programmatically.

5. **Decision**: Exit code 124 for timeout (matching Unix `timeout` convention).
   - **Reason**: Standard Unix convention makes timeout behavior predictable for benchmark runners and shell scripts. WildClawBench or other orchestration tools can distinguish timeout from other failures.
   - **Alternatives Considered**: Custom exit code (e.g., 2) — rejected because it violates conventional expectations.

6. **Decision**: Config loading from env vars with CLI overrides, rather than config files.
   - **Reason**: Benchmark containers inject configuration via environment variables. CLI overrides enable local testing without modifying the environment. Config files add unnecessary complexity for this use case.
   - **Alternatives Considered**: YAML/TOML config files — rejected because env vars are the standard mechanism for container configuration.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| BaseLoop working message list not accessible after run | Low likelihood | High | The `TinyCUALoop` stores `working` messages; access via loop instance or add a `get_working_messages()` method if needed |
| Timeout watchdog kills process before cleanup completes | Medium | Medium | Use `threading.Timer` with cooperative cancellation via `asyncio.Event`; write partial transcript on timeout; SIGTERM/SIGKILL deferred to Milestone 5.2 per spec FR-015 |
| Transcript format mismatch with WildClawBench | Low | High | Follow the exact schema from `adapter-contract.md`; test with WildClawBench transcript loader |
| Local model endpoint latency causes premature timeout | Medium | Medium | Default timeout of 600s is generous; document that users should adjust based on model speed |
| Output directory permissions in container | Low | Medium | Pre-flight check before agent execution; create directory if it doesn't exist |

---

## Open Questions

1. **Transcript writer integration with BaseLoop**
   - The `TinyCUALoop` extends `BaseLoop` which maintains a `working` message list. The transcript writer needs access to this list after agent execution. We need to verify that `TinyCUALoop` exposes `working` or add a getter method.
   - See `src/tinycua-sdk/tinycua_sdk/agent/loop.py` for the `BaseLoop` base class. `TinyCUALoop` extends it at `src/tinycua/tinycua/loops/tinycua_loop.py`.
   - **Status**: RESOLVED
   - **Resolution**: `BaseLoop.run()` uses `working` as a local variable (not an instance attribute). The transcript writer must either (a) override `run()` to store `working` as `self._working_messages` before returning, or (b) add a `get_working_messages()` method to `TinyCUALoop`. Option (b) is preferred as it avoids overriding the base class contract. Add a `self._working_messages: list[dict] = []` attribute to `TinyCUALoop.__init__()` and set it in `run()` before returning.

2. **Per-response usage tracking**
   - **Status**: RESOLVED
   - **Resolution**: Instrument `_call_llm()` in `TinyCUALoop` to capture `response.usage` per node and store alongside messages in `self._working_messages`. Each transcript record will include an optional `usage` field populated from the LLM response metadata. This requires adding a `usage: dict | None = None` field to each message dict stored in `_working_messages`, and setting it from the response object after each `_call_llm()` call.
   - See `specs/wildclawbench-adapter/adapter-contract.md` § Transcript Conversion Strategy.
   - **Task**: Added to task.md as item 21.

3. **Model name convention**
   - The `--model` flag needs a sensible default. For local models, the model name is often implementation-specific (e.g., `llama-3-8b`, `gpt-4o-mini`). We should document that this flag must match the model name expected by the local endpoint.
   - **Status**: RESOLVED
   - **Resolution**: The `--model` flag has no sensible universal default since local model names are endpoint-specific (e.g., llama-3-8b, qwen-72b). The CLI will NOT set a default for `--model` — it will be a required flag when `TINYCUA_MODEL` env var is not set. Document that the flag must match the model name expected by the local endpoint.

---

## References

- **Spec**: `./spec.md` — feature requirements and acceptance criteria
- **Adapter Contract**: `specs/wildclawbench-adapter/adapter-contract.md` — transcript format and grading compatibility
- **Factory**: `src/tinycua/tinycua/factory.py` — `create_tinycua_agent()` implementation
- **TinyCUALoop**: `src/tinycua/tinycua/loops/tinycua_loop.py` — loop implementation with working message list
- **BaseLoop SDK**: `src/tinycua-sdk/tinycua_sdk/agent/loop.py` — SDK base loop contract
- **WildClawBench Issue**: [VJyzCELERY/TINYCUA#87](https://github.com/VJyzCELERY/TINYCUA/issues/87) — milestone 5.1 definition
