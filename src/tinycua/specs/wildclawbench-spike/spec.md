# Feature Specification: WildClawBench Compatibility Research

**Status**: Complete
**Created**: 2026-06-05
**Last Updated**: 2026-06-05
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Research WildClawBench benchmark compatibility and document the adapter contract required for TINYCUA to run as a 5th harness alongside OpenClaw, Claude Code, Codex, and Hermes Agent.
- **Gaps**: TINYCUA has no WildClawBench integration. The benchmark's adapter contract, transcript format, and grading flow are undocumented in our codebase.
- **Non-Goals**: Implementing the adapter, building Docker images, or running the benchmark. This milestone is research and documentation only.
- **Constraints**: Must document the contract based on the upstream WildClawBench repository (InternLM/WildClawBench) without modifying it.

---

## User Scenarios & Testing

### Primary Scenario

A developer working on TINYCUA needs to understand what interface to implement to make TINYCUA compatible with WildClawBench. They read the adapter contract document and understand:
1. What `BaseAgent` methods to implement
2. What transcript format the grading system expects
3. How Docker containers are used for task isolation
4. What the `AgentTaskSpec` data structure contains

### Acceptance Scenarios

1. **Given** a developer reads the adapter contract, **When** they examine the `BaseAgent` interface, **Then** they can identify the 4 abstract required members and the 1 optional/default hook (`prepare_grading_transcript`), with their signatures and return types.
2. **Given** a developer reads the adapter contract, **When** they examine the transcript format section, **Then** they understand the OpenClaw-compatible JSONL schema and the exact path where transcripts must be written.
3. **Given** a developer reads the adapter contract, **When** they examine the grading flow section, **Then** they understand the 5-step process from agent execution to score collection.
4. **Given** a developer reads the adapter contract, **When** they examine the Docker requirements section, **Then** they understand the container lifecycle, volume mounts, and environment variables.

### Edge Cases

- What if the transcript format is slightly different from OpenClaw's? The grading system uses `transcript_loader.py` which supports multiple formats (JSON array, JSON object, JSONL).
- What if the agent times out? The adapter must handle `subprocess.TimeoutExpired` and return an `AgentExecution` with the error set.
- What if usage tracking is incomplete? The adapter should provide fallback collection methods (parse agent.log, count requests).

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST document the `BaseAgent` abstract class interface with 4 abstract required members (`expects_gateway`, `transcript_container_path`, `run_task()`, `collect_usage()`) and the optional/default `prepare_grading_transcript()` hook.
- **FR-002**: System MUST document the `AgentTaskSpec` dataclass with all 10 fields and their types.
- **FR-003**: System MUST document the `AgentExecution` dataclass returned by `run_task()`.
- **FR-004**: System MUST document the OpenClaw-compatible transcript JSONL format with exact schema.
- **FR-005**: System MUST document the 5-step grading flow from execution to score collection.
- **FR-006**: System MUST document Docker container requirements including image structure, lifecycle, and volume mounts.
- **FR-007**: System MUST document the mapping between TINYCUA concepts and WildClawBench equivalents.
- **FR-008**: System MUST provide a transcript conversion strategy showing how TINYCUA traces map to OpenClaw JSONL.

### Key Entities

- **BaseAgent**: Abstract class that harnesses must implement. Defines the contract for task execution, transcript preparation, and usage collection.
- **AgentTaskSpec**: Frozen dataclass containing all inputs for a single task execution (task metadata, model config, workspace path, prompt, timeout).
- **AgentExecution**: Dataclass returned by `run_task()` containing timing, error state, and process handles.
- **Transcript**: OpenClaw-compatible JSONL file containing conversation history with token usage and cost information.
- **Grading Script**: Python code injected into the container that loads the transcript and executes task-specific grading logic.

---

## Success Criteria

- [x] **Adapter contract document exists**: `specs/wildclawbench-adapter/adapter-contract.md` is created and complete.
- [x] **BaseAgent interface documented**: All 5 methods with signatures, return types, and descriptions.
- [x] **AgentTaskSpec documented**: All 10 fields with types and descriptions.
- [x] **Transcript format documented**: OpenClaw-compatible JSONL schema with exact field definitions.
- [x] **Grading flow documented**: 5-step process with clear responsibilities for each step.
- [x] **Docker requirements documented**: Container lifecycle, volume mounts, environment variables.
- [x] **TINYCUA mapping documented**: How TINYCUA concepts map to WildClawBench equivalents.

---

## Testing Plan

### Unit Tests

- Not applicable — this milestone is documentation only.

### Integration Tests

- Not applicable — this milestone is documentation only.

### Manual Tests

- Verify adapter contract document is readable and complete.
- Verify all referenced WildClawBench source files exist in the upstream repository.
- Verify the `BaseAgent` interface matches the actual upstream implementation.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Adapter contract document | Done | `specs/wildclawbench-adapter/adapter-contract.md` |
| BaseAgent interface | Done | Documented from upstream source |
| AgentTaskSpec fields | Done | Documented from upstream source |
| Transcript format | Done | OpenClaw-compatible JSONL schema |
| Grading flow | Done | 5-step process documented |
| Docker requirements | Done | Container lifecycle documented |
| TINYCUA mapping | Done | Concept mapping documented |

---

## Open Questions

1. **Transcript conversion complexity**
   - **Owner**: @tinycua-team
   - **Target**: 2026-06-10
   - **Status**: Proposed
   - **Proposed Answer**: Need to implement and test the actual conversion before estimating effort.

2. **Docker image size**
   - **Owner**: @tinycua-team
   - **Target**: 2026-06-10
   - **Status**: Proposed
   - **Proposed Answer**: Use multi-stage build to minimize layers. Target < 2GB.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
