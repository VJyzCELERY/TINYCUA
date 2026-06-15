# Feature Specification: Hermes-Agent Benchmark Integration

**Status**: Draft
**Created**: 2026-06-15
**Last Updated**: 2026-06-15
**Subproject(s) Affected**: tinycua, tinycua-benchmark

---

## Quick Guidelines

- Focus on **WHAT** users/callers need and **WHY** — not HOW to implement
- Avoid implementation details (no tech stack choices, class names, or code structure in this doc)
- Mark unclear requirements with `[NEEDS CLARIFICATION: specific question]`
- Every requirement must be independently testable
- Highlight anything that could violate KISS, YAGNI, or DRY for architecture review
- When done, requirements with `[NEEDS CLARIFICATION]` markers must be resolved before implementation begins

---

## Problem Statement _(mandatory)_

- **Goals**: Enable the Hermes agent (from InternLM/WildClawBench) to run as a benchmark target alongside TinyCUA using the WildClawBench harness, producing comparable evaluation results with the same grading criteria. Provide a setup procedure, configuration, and documentation so that Hermes agent can be benchmarked in the same evaluation pipeline.
- **Gaps**: TinyCUA currently has its own `TinyCUAAgent` adapter (`src/tinycua/tinycua/wildclawbench/agent.py`) but the Hermes agent from upstream WildClawBench is not wired into the TinyCUA benchmark pipeline. There is no documented procedure to configure, build, and run the Hermes agent against WildClawBench tasks.
- **Non-Goals**: This spec does NOT cover:
  - Modifying the Hermes agent itself (it runs as-is from upstream)
  - Building a new benchmark framework (uses existing WildClawBench harness)
  - Changing the WildClawBench grading/evaluation system
  - Performance optimization of either agent
- **Constraints**:
  - Hermes agent must run in Docker container isolation (per WildClawBench harness contract)
  - Must use existing WildClawBench adapter contract (`specs/wildclawbench-adapter/adapter-contract.md`)
  - Grading and evaluation must use the same criteria as TinyCUA runs for fair comparison
  - Configuration must be reproducible — documented steps, no manual setup

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer wants to compare TinyCUA vs Hermes agent on WildClawBench tasks. They follow the documented setup to configure and run the Hermes agent through the same benchmark pipeline, then compare scores side-by-side.

### Acceptance Scenarios

1. **Given** Hermes agent is configured, **When** the developer runs the benchmark pipeline with `--agent-backend hermesagent`, **Then** the agent executes tasks and produces WildClawBench-compatible transcripts
2. **Given** both TinyCUA and Hermes agent have completed benchmark runs, **When** the scores are collected, **Then** they are stored in a comparable format for side-by-side analysis
3. **Given** the setup documentation is followed step-by-step, **When** a new developer provisions the Hermes agent from scratch, **Then** they can run a benchmark within [NEEDS CLARIFICATION: acceptable time — e.g., 30 minutes]

### Edge Cases

- What happens when the Hermes agent Docker image fails to build? — Pipeline should log build error and skip Hermes tasks
- How does the system handle Hermes agent timeouts? — Same timeout handling as TinyCUA per adapter contract
- What if the Hermes agent produces malformed transcripts? — Grading should detect and report, not crash
- How are API keys managed for Hermes agent? — Must be provided via environment variables, never hardcoded

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST support running Hermes agent as a WildClawBench harness via `--agent-backend hermesagent` flag
- **FR-002**: System MUST provide a documented setup procedure for Hermes agent (Docker image build, config files, environment variables)
- **FR-003**: System MUST produce WildClawBench-compatible transcripts from Hermes agent runs
- **FR-004**: System MUST apply the same grading criteria to Hermes agent as to TinyCUAAgent
- **FR-005**: System MUST support side-by-side comparison of TinyCUA and Hermes agent results
- **FR-006**: System MUST log Hermes agent execution (start, end, errors, usage) at info level
- **FR-007**: System MUST handle Hermes agent failures gracefully (timeout, container crash, missing API key) without crashing the entire benchmark run
- **FR-008**: System MUST provide a Hermes agent configuration file (equivalent to `hermes.yaml` upstream) adapted for the TinyCUA benchmark pipeline

### Key Entities

- **HermesAgent**: The Hermes agent from upstream WildClawBench (`src/agents/hermesagent/`) — runs as a harness in the benchmark
- **Hermes Config**: Configuration file specifying model, API endpoint, parameters for the Hermes agent run
- **Benchmark Run**: A single execution of the full WildClawBench task suite against a specific agent
- **Benchmark Report**: Side-by-side comparison of scores across agents (TinyCUA vs Hermes)

---

## Success Criteria _(mandatory)_

- **Hermes agent runs**: Developer can run `python -m tinycua.benchmark --agent-backend hermesagent` and tasks execute
- **Transcripts produced**: Hermes agent generates OpenClaw-compatible JSONL transcripts in the output directory
- **Scores collected**: Grading runs successfully on Hermes agent transcripts
- **Side-by-side comparison**: Both TinyCUA and Hermes agent results are available in the same format for comparison
- **Setup is documented**: A new developer can follow README steps and run Hermes agent benchmark within [NEEDS CLARIFICATION: acceptable time]

---

## Testing Plan _(mandatory)_

### Unit Tests

- Hermes config validation (required fields, type checks)
- Hermes agent Docker command construction
- Transcript format validation

### Integration Tests

- Full Hermes agent benchmark run (smoke test with 1-3 tasks)
- Hermes agent timeout handling
- Hermes agent container build and cleanup

### Manual Tests

- Run Hermes agent against full WildClawBench task suite
- Compare results with TinyCUA baseline run
- Verify setup docs by following them on a clean machine

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Hermes agent Docker setup | TODO | Dockerfile, config, env vars |
| Agent backend wiring | TODO | Add `hermesagent` to `--agent-backend` choices |
| Transcript output | TODO | Ensure Hermes writes to correct path |
| Grading pipeline | TODO | Reuse existing grading, verify compatibility |
| Side-by-side reporting | TODO | Collect and compare scores |
| Setup documentation | TODO | Step-by-step guide |

---

## Open Questions _(optional)_

1. **Hermes agent API key management**
   - **Owner**: TBD
   - **Target**: 2026-06-20
   - **Status**: Discussion
   - **Proposed Answer**: Use `.env` file loaded at runtime, documented in setup guide

2. **Docker image caching strategy**
   - **Owner**: TBD
   - **Target**: 2026-06-20
   - **Status**: Discussion
   - **Proposed Answer**: Use Docker layer caching; document `docker build --cache-from`

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
