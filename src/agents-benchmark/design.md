# Design Document: agents-benchmark

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Last Updated**: 2026-06-17

---

## Overview

This design replaces the `hermes-benchmark` subproject with a unified `agents-benchmark` subproject that orchestrates all four WildClawBench agent harnesses (Hermes Agent, Claude Code, Codex CLI, OpenClaw) through a single pipeline. The key architectural decision is a **registry-based adapter pattern**: each agent is an adapter implementing the WildClawBench `BaseAgent` ABC, registered in a central registry and selected by name at runtime. Agents execute sequentially in a fixed pipeline (Hermes → Claude Code → Codex → OpenClaw) to avoid resource contention.

---

## Architecture

### Component Overview

```
CLI Entry Point (agents_benchmark/__main__.py)
        │
        ├── AgentRegistry (agent_registry.py)
        │   ├── HermesAgentAdapter
        │   ├── ClaudeCodeAdapter
        │   ├── CodexAdapter
        │   └── OpenClawAdapter
        │
        ├── BenchmarkRunner (runner.py)
        │   ├── run_pipeline()      # sequential agent execution
        │   ├── run_single_agent()  # single agent, all tasks
        │   └── run_single_task()   # single task, single agent
        │
        ├── CompareModule (compare.py)
        │   └── compare_agents()    # N-way comparison
        │
        └── ConfigLoader (config.py)
            └── load_config()       # YAML + env var resolution
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `agents_benchmark/__init__.py` | New | Package init, public API exports |
| `agents_benchmark/__main__.py` | New | CLI entry point (argparse) |
| `agents_benchmark/base_agent.py` | Modified | Migrated from hermes-benchmark, extended for 4 agents |
| `agents_benchmark/agent_registry.py` | New | Registry pattern for agent adapter lookup |
| `agents_benchmark/agents/` | New | Directory containing per-agent adapters |
| `agents_benchmark/agents/hermes.py` | New | HermesAgent adapter (migrated from hermes-benchmark) |
| `agents_benchmark/agents/claudecode.py` | New | Claude Code adapter |
| `agents_benchmark/agents/codex.py` | New | Codex CLI adapter |
| `agents_benchmark/agents/openclaw.py` | New | OpenClaw adapter |
| `agents_benchmark/runner.py` | New | Pipeline orchestrator |
| `agents_benchmark/compare.py` | Modified | Extended from hermes-benchmark for N agents |
| `agents_benchmark/config.py` | New | Per-agent configuration loader |
| `pyproject.toml` | New | Package metadata, dependencies, CLI scripts |
| `Makefile` | New | Dev commands (lint, test, clean) |
| `tests/` | New | Unit and integration tests |
| `src/hermes-benchmark/` | Deleted | Replaced by agents-benchmark |

---

## Data Model

### AgentConfig

```python
@dataclass
class AgentConfig:
    name: str                    # "hermes", "claudecode", "codex", "openclaw"
    model: str                   # model name/path
    api_base: str                # API endpoint URL
    api_key_env: str             # env var name for API key
    docker_image: str            # Docker image tag
    dockerfile_path: str         # path to Dockerfile
    timeout_seconds: int = 300   # per-task timeout
    extra_env: dict[str, str] = field(default_factory=dict)
```

### BenchmarkResult

```python
@dataclass
class BenchmarkResult:
    agent_name: str
    task_id: str
    score: float | None
    status: str                  # "success", "failed", "error", "timeout"
    elapsed_time: float
    token_usage: dict[str, Any]  # requests, total_tokens, cost
    output_dir: Path
```

### PipelineResult

```python
@dataclass
class PipelineResult:
    agent_results: dict[str, list[BenchmarkResult]]  # agent_name -> results
    summary: dict[str, Any]                           # aggregate stats per agent
    comparison: dict[str, Any] | None                 # N-way comparison if available
```

---

## API / Interface Contracts

### CLI Interface

```bash
# Run all agents sequentially
uv run python -m agents_benchmark --model my-model --agents all --category all

# Run specific agents
uv run python -m agents_benchmark --model my-model --agents hermes,openclaw

# Run with parallel tasks
uv run python -m agents_benchmark --model my-model --agents all --parallel 4

# Compare results
uv run python -m agents_benchmark compare --results-dir ./output
```

### Agent Adapter Interface

```python
class AgentAdapter(BaseAgent):
    """WildClawBench-compatible agent adapter."""

    @property
    def name(self) -> str:
        """Return the agent identifier (e.g., 'hermes', 'claudecode')."""

    @property
    def expects_gateway(self) -> bool:
        """Return True if this agent needs a long-running gateway process."""

    @property
    def transcript_container_path(self) -> str:
        """Return path to transcript file inside the container."""

    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """Execute a single benchmark task."""

    def collect_usage(self, task_id: str, output_dir: Path, elapsed_time: float) -> dict[str, Any]:
        """Collect usage statistics from completed task."""
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Docker not installed | `SystemExit("Docker is required...")` | Fail early at startup |
| API key missing | Skip agent with warning log | Continue pipeline |
| Docker build failure | Skip agent with error log | Continue pipeline |
| Task timeout | Mark task as "timeout", continue | Per-task recovery |
| Agent crash | Mark agent as "error", skip remaining tasks for that agent | Per-agent recovery |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create `pyproject.toml` with package metadata and dependencies
- [ ] Migrate `base_agent.py` from hermes-benchmark, extend for 4 agents
- [ ] Implement `agent_registry.py` with registration and lookup
- [ ] Implement `agents/hermes.py` adapter (migrate from hermes-benchmark)
- [ ] Implement `agents/claudecode.py` adapter
- [ ] Implement `agents/codex.py` adapter
- [ ] Implement `agents/openclaw.py` adapter
- [ ] Implement `config.py` for per-agent configuration loading
- [ ] Implement `runner.py` with sequential pipeline execution
- [ ] Implement `compare.py` with N-way comparison logic
- [ ] Implement `__main__.py` CLI entry point with argparse
- [ ] Create `Makefile` with dev commands
- [ ] Write unit tests for all modules
- [ ] Write integration tests for pipeline execution

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Add progress bar / rich output for long-running benchmarks
- [ ] Add HTML comparison dashboard generation
- [ ] Add cost estimation per agent based on token pricing

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use registry pattern for agent adapters instead of factory or strategy pattern.
   - **Reason**: Simple, explicit registration; easy to add new agents without modifying core logic.
   - **Alternatives Considered**: Factory pattern (rejected — overengineered for 4 agents); Strategy pattern (rejected — adapters are stateless, no runtime strategy switching needed).

2. **Decision**: Agents run sequentially, not in parallel.
   - **Reason**: Docker containers and API rate limits create resource contention. Sequential execution is simpler and more predictable.
   - **Alternatives Considered**: Parallel agent execution (rejected — complexity not justified for 4 agents).

3. **Decision**: Extend existing `BaseAgent` ABC rather than creating a new interface.
   - **Reason**: WildClawBench compatibility is a hard requirement. Reusing the ABC ensures drop-in compatibility with existing grading infrastructure.
   - **Alternatives Considered**: New interface (rejected — breaks WildClawBench compatibility).

4. **Decision**: Use argparse for CLI instead of click/typer.
   - **Reason**: No external dependency; stdlib is sufficient for the required subcommands.
   - **Alternatives Considered**: Click (rejected — adds dependency for minimal benefit); Typer (rejected — adds dependency).

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Docker image build failures across platforms | Medium | High | Test on macOS and Linux; provide clear error messages and fallback instructions |
| API rate limiting during long benchmark runs | Medium | Medium | Implement retry logic with exponential backoff; support `--parallel` to spread load |
| WildClawBench upstream changes break adapters | Low | High | Pin WildClawBench commit in Dockerfiles; monitor upstream for breaking changes |
| Local LLM endpoints may be slow/inconsistent | High | Low | Configurable timeouts per agent; graceful timeout handling |

---

## Open Questions _(optional)_

1. Should the compare module support more than 2 agents (N-way comparison)?
   - **Proposed Answer**: Yes — the existing `compare_results.py` is 2-agent only. The new `compare.py` should support N agents with pairwise deltas.

---

## References

- Spec: [./spec.md](./spec.md)
- WildClawBench: https://github.com/internlm/WildClawBench
- Existing hermes-benchmark: `src/hermes-benchmark/`
- Rules: `.agents/rules/002-code-standards.md`, `.agents/rules/005-project-structure.md`
