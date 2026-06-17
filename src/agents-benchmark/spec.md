# Feature Specification: agents-benchmark

**Status**: Draft
**Created**: 2026-06-17
**Last Updated**: 2026-06-17
**Subproject(s) Affected**: agents-benchmark (new, replaces hermes-benchmark)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a unified WildClawBench benchmark harness that runs all four supported agent types (Hermes Agent, Claude Code, Codex CLI, OpenClaw) through a single script, enabling side-by-side comparison of local LLM performance across agent scaffolds.
- **Gaps**: The current `hermes-benchmark` subproject only supports Hermes Agent. There is no single entry point to run all four WildClawBench harnesses, compare results across agents, or easily add new agent adapters.
- **Non-Goals**: This spec does NOT cover: model fine-tuning, custom task creation, production deployment of agents, or web-based dashboards.
- **Constraints**: Must follow WildClawBench conventions (Docker-based isolation, BaseAgent ABC, transcript-based grading). Must use `uv run` for all Python execution. Must be compatible with existing TinyCUA project structure.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer wants to benchmark a local LLM (e.g., MiMo, Qwen) across all four WildClawBench agent harnesses. They run a single command that:

1. Sequentially executes each agent (Hermes → Claude Code → Codex → OpenClaw) against the same 60-task suite
2. Collects per-task scores, timing, and token usage for each agent
3. Produces a unified comparison report showing which agent scaffold performs best for the given model

### Acceptance Scenarios

1. **Given** a configured local model endpoint, **When** the user runs `uv run python -m agents_benchmark --model my-model --agents all`, **Then** all four agents execute the full task suite and results are saved to `output/`.
2. **Given** partial results exist, **When** the user runs with `--agents hermes,claudecode`, **Then** only the specified agents run and existing results for other agents are preserved.
3. **Given** completed runs for all agents, **When** the user runs `uv run python -m agents_benchmark compare`, **Then** a `comparison.json` is produced with per-task deltas and aggregate statistics across all agents.
4. **Given** a Docker image is not built, **When** an agent requires it, **Then** the system automatically builds the image before execution.
5. **Given** an agent task times out, **When** the timeout is reached, **Then** the task is marked as failed with an error, and subsequent tasks continue.

### Edge Cases

- What happens when Docker is not installed? System must fail early with a clear error message.
- What happens when an API key env var is missing? Skip that agent with a warning, continue with others.
- What happens with empty task lists? Must produce valid empty results.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST support all four WildClawBench agent harnesses: Hermes Agent, Claude Code, Codex CLI, OpenClaw.
- **FR-002**: System MUST provide a single CLI entry point (`agents_benchmark`) that orchestrates sequential agent execution.
- **FR-003**: System MUST execute agents in a fixed pipeline order: Hermes → Claude Code → Codex → OpenClaw.
- **FR-004**: System MUST collect per-task results including: score, elapsed_time, token_usage, cost, status.
- **FR-005**: System MUST produce a unified `summary_all.json` combining results from all agents.
- **FR-006**: System MUST support a `compare` subcommand to generate cross-agent comparison reports.
- **FR-007**: System MUST auto-build Docker images when missing.
- **FR-008**: System MUST support filtering by agent name (`--agents hermes,claudecode`) and category (`--category all`).
- **FR-009**: System MUST support parallel task execution within an agent (`--parallel N`).
- **FR-010**: System MUST handle agent failures gracefully — skip failed agents, continue with remaining.
- **FR-011**: System MUST reuse the existing `BaseAgent` ABC and `AgentTaskSpec`/`AgentExecution` dataclasses from the WildClawBench interface.
- **FR-012**: System MUST support local LLM endpoints via OpenAI-compatible API (base URL configuration).

### Key Entities _(include if feature involves data)_

- **AgentAdapter**: Wraps a WildClawBench harness (Hermes, Claude Code, Codex, OpenClaw) behind a common interface. Each adapter implements `BaseAgent.run_task()` and `BaseAgent.collect_usage()`.
- **BenchmarkRun**: Represents a complete benchmark execution across one or more agents. Contains per-agent results, timing, and aggregate statistics.
- **AgentConfig**: Per-agent configuration (model, API endpoint, Docker image, env vars, timeouts).
- **ComparisonReport**: Cross-agent comparison with per-task deltas and category-level aggregates.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Single command runs all agents**: `uv run python -m agents_benchmark --model X --agents all` executes Hermes → Claude Code → Codex → OpenClaw sequentially.
- [ ] **Results are collected**: Each agent's per-task results (score, timing, tokens, cost) are saved to structured output files.
- [ ] **Comparison report**: `uv run python -m agents_benchmark compare` produces a JSON with per-task deltas and aggregate stats across all agents.
- [ ] **Agent filtering**: `--agents hermes,openclaw` runs only those two agents.
- [ ] **Docker auto-build**: Missing Docker images are built automatically before execution.
- [ ] **Graceful failure handling**: Failed agents are skipped; remaining agents continue; final report indicates which agents succeeded/failed.
- [ ] **Local LLM support**: System works with any OpenAI-compatible endpoint (e.g., local vLLM, LM Studio).
- [ ] **Unit tests pass**: All unit tests pass with `uv run pytest tests/`.
- [ ] **Lint passes**: `uv run ruff check` and `uv run ruff format --check` pass.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_agent_registry.py`: Test agent adapter registration and lookup by name.
- `test_agent_config.py`: Test AgentConfig loading from YAML/env vars.
- `test_benchmark_runner.py`: Test sequential agent pipeline, filtering, and error handling.
- `test_compare_results.py`: Test cross-agent comparison logic (migrated from hermes-benchmark, extended for 4 agents).
- `test_base_agent.py`: Test BaseAgent ABC contract compliance for all adapters.

### Integration Tests

- `test_hermes_agent_integration.py`: Test HermesAgent Docker execution end-to-end.
- `test_pipeline_integration.py`: Test full pipeline with mock agents.

### Manual Tests _(if applicable)_

- Verify Docker image build for each agent type.
- Verify full 60-task run produces valid `summary_all.json`.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| spec.md | TODO | This document |
| design.md | TODO | Architecture and implementation plan |
| Agent adapters (4) | TODO | Hermes, Claude Code, Codex, OpenClaw |
| Benchmark runner | TODO | Single CLI entry point |
| Compare module | TODO | Cross-agent comparison |
| Unit tests | TODO | Per module |
| Integration tests | TODO | Docker + pipeline |

---

## Open Questions _(optional)_

1. **Should we deprecate hermes-benchmark?**
   - **Owner**: @jonaja29
   - **Status**: Decided
   - **Proposed Answer**: Yes — agents-benchmark replaces it entirely. The hermes-benchmark code will be removed from `src/` after agents-benchmark is verified.

2. **Should the pipeline support parallel agent execution?**
   - **Owner**: @jonaja29
   - **Status**: Proposed
   - **Proposed Answer**: No — agents run sequentially to avoid resource contention (Docker, API rate limits). Tasks within an agent can be parallel via `--parallel`.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
