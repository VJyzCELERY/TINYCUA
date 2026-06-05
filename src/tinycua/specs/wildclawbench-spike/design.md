# Design Document: WildClawBench Compatibility Research

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-06-05

---

## Overview

This milestone documents the adapter contract required for TINYCUA to run as a 5th harness in WildClawBench. The research inspects the upstream WildClawBench repository (InternLM/WildClawBench) and produces a comprehensive adapter contract document at `specs/wildclawbench-adapter/adapter-contract.md`. This design references that contract as the primary deliverable.

---

## Architecture

### Component Overview

```
WildClawBench run_batch.py
    │
    ├── Parses task markdown → AgentTaskSpec
    ├── Creates backend (BaseAgent subclass)
    ├── Calls backend.run_task(spec)
    │       │
    │       ├── Starts Docker container
    │       ├── Copies workspace to /tmp_workspace
    │       ├── Executes warmup commands (task["warmup"])
    │       ├── Runs TINYCUA agent inside container
    │       └── Returns AgentExecution
    │
    ├── Calls backend.prepare_grading_transcript(task_id)
    │       │
    │       ├── Converts native transcript → OpenClaw JSONL
    │       └── Returns path to compatible transcript
    │
    ├── Copies ground truth (gt/) into container
    ├── Executes grading script inside container
    │       │
    │       ├── Loads transcript via transcript_loader.py
    │       ├── Runs automated_checks from task metadata
    │       └── Outputs JSON scores
    │
    └── Collects scores, usage, and task output
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `specs/wildclawbench-adapter/adapter-contract.md` | New | Primary deliverable — comprehensive adapter contract |
| `src/tinycua/specs/wildclawbench-spike/spec.md` | New | Research goal and acceptance criteria |
| `src/tinycua/specs/wildclawbench-spike/design.md` | New | This document |

---

## Data Model

### AgentTaskSpec (Input)

```python
@dataclass(frozen=True)
class AgentTaskSpec:
    task_id: str                    # Unique task identifier
    task: dict[str, Any]            # Parsed task metadata
    workspace_path: str             # Host path to workspace (read-only in container)
    prompt: str                     # Full task prompt with system prefix
    timeout_seconds: int            # Maximum execution time
    output_dir: Path                # Host directory for output files
    model: str                      # Model identifier (e.g., "openrouter/openai/gpt-5.5")
    thinking: str | None = None     # Optional reasoning mode
    models_config: dict | None = None  # Optional provider configuration
    lobster: dict | None = None     # Optional lobster workspace config
```

### AgentExecution (Output)

```python
@dataclass
class AgentExecution:
    elapsed_time: float             # Actual execution time in seconds
    error: str | None = None        # Error message if execution failed
    gateway_proc: subprocess.Popen | None = None  # Gateway process (None for TINYCUA)
    agent_proc: subprocess.Popen | None = None    # Agent process handle
```

### Transcript (OpenClaw-compatible JSONL)

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
            "cost": {"total": 0.0023}
        }
    }
}
```

---

## API / Interface Contracts

### BaseAgent Interface (Required)

```python
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

    @abstractmethod
    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """Execute a task and return process handles, timing and error state."""

    @abstractmethod
    def collect_usage(self, task_id: str, output_dir: Path, elapsed_time: float) -> dict[str, Any]:
        """Collect token usage and cost for one task."""
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Container startup failure | `RuntimeError` in `run_task()` | Returned as `AgentExecution.error` |
| Agent timeout | `subprocess.TimeoutExpired` | Caught, process killed, returned with `error=None` (keeps grading enabled — upstream only grades errored executions for Codex/ClaudeCode) |
| Transcript conversion failure | `logger.warning()` | Fallback to raw transcript path |
| Grading script failure | `{"error": message}` | Written to `score.json` |
| Usage parsing failure | Zero-filled usage dict | Never return `{}` — upstream `save_usage()` indexes required fields immediately |

**Usage fallback contract**: When usage parsing fails, `collect_usage()` must return a zero-filled dict matching the upstream schema. Upstream `eval/run_batch.py` calls `save_usage()` which immediately indexes `usage["request_count"]`, `usage["input_tokens"]`, `usage["output_tokens"]`, `usage["cache_read_tokens"]`, `usage["total_tokens"]`, and `usage["cost_usd"]` — returning `{}` raises `KeyError` and crashes the benchmark run. Required zero-filled fallback:

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

Fallback parsing (e.g., from `agent.log`) may update these fields, but the method must never return an empty dict.

---

## Implementation Phases

### Phase 1 — Research & Documentation (Complete)

- [x] Inspect WildClawBench `BaseAgent` interface
- [x] Inspect `AgentTaskSpec` dataclass
- [x] Inspect `run_batch.py` execution flow
- [x] Inspect transcript loading (`transcript_loader.py`)
- [x] Inspect grading flow (`grading.py`)
- [x] Inspect HermesAgent adapter as reference implementation
- [x] Document adapter contract at `specs/wildclawbench-adapter/adapter-contract.md`
- [x] Create spec and design documents

### Phase 2 — Implementation (Future Milestone)

- [ ] Implement `TinyCUAAgent` adapter class
- [ ] Implement transcript converter (TINYCUA trace → OpenClaw JSONL)
- [ ] Build Docker image with TINYCUA
- [ ] Test with single WildClawBench task
- [ ] Run full 60-task benchmark

---

## Technical Decisions

1. **Decision**: Research milestone is documentation-only, not implementation.
   - **Reason**: Need to understand the full contract before building. Prevents rework.
   - **Alternatives Considered**: Implement adapter directly — rejected because it would require multiple iterations as we discover requirements.

2. **Decision**: Use HermesAgent as the reference implementation.
   - **Reason**: HermesAgent is the closest existing harness to TINYCUA (both are Python-based agents with custom loops).
   - **Alternatives Considered**: OpenClaw adapter — too different (gateway-based architecture). Claude Code adapter — different paradigm (CLI-based).

3. **Decision**: Document transcript format as OpenClaw-compatible JSONL.
   - **Reason**: The grading system's `transcript_loader.py` expects this format. All harnesses must produce it.
   - **Alternatives Considered**: Native TINYCUA format — rejected because grading would fail.

4. **Decision**: Document Docker requirements including container lifecycle.
   - **Reason**: TINYCUA adapter must manage Docker containers. Understanding the full lifecycle is essential.
   - **Alternatives Considered**: Skip Docker details — rejected because it's critical for implementation.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Transcript format mismatch | Medium | High | Test with sample transcripts before implementation |
| Docker image too large | Medium | Medium | Use multi-stage build, minimize layers |
| Tool schema incompatibility | Low | High | Verify OpenAI-compatible format matches upstream |
| Timeout handling gaps | Medium | Medium | Implement graceful shutdown with signal handling |
| Usage tracking incomplete | Medium | Low | Provide multiple collection methods as fallback |

---

## Open Questions

1. **Transcript conversion implementation**
   - The conversion strategy is documented in the adapter contract (Strategy B: BaseLoop instrumentation recommended). Implementation and testing effort TBD.
   - See `specs/wildclawbench-adapter/adapter-contract.md` lines 472-635 for the full pseudocode and tradeoff analysis.

2. **Docker image size**
   - Target < 2GB for reasonable CI times.
   - Use multi-stage build with minimal base image.

3. **Native tools coverage**
   - WildClawBench tasks require shell, file, web, email, calendar, image, video tools.
   - TINYCUA currently has shell, file, web, python tools.
   - Gap: email, calendar, image, video tools.

---

## References

- **Adapter Contract**: `specs/wildclawbench-adapter/adapter-contract.md` — comprehensive adapter contract document
- **Spec**: `./spec.md` — research goal and acceptance criteria
- **Upstream Source**: [InternLM/WildClawBench](https://github.com/InternLM/WildClawBench) — commit [`86d7144`](https://github.com/InternLM/WildClawBench/tree/86d71447413d38f38740a021cb776f64eb396ee0)
- **HermesAgent Adapter**: [src/agents/hermesagent/runner.py](https://github.com/InternLM/WildClawBench/blob/86d71447413d38f38740a021cb776f64eb396ee0/src/agents/hermesagent/runner.py) — reference implementation
- **BaseAgent Interface**: [src/agents/base.py](https://github.com/InternLM/WildClawBench/blob/86d71447413d38f38740a021cb776f64eb396ee0/src/agents/base.py) — abstract class definition
- **Transcript Loader**: [src/utils/transcript_loader.py](https://github.com/InternLM/WildClawBench/blob/86d71447413d38f38740a021cb776f64eb396ee0/src/utils/transcript_loader.py) — transcript parsing logic
- **Grading Flow**: [src/utils/grading.py](https://github.com/InternLM/WildClawBench/blob/86d71447413d38f38740a021cb776f64eb396ee0/src/utils/grading.py) — grading execution logic
