# Feature Specification: TinyCUA Benchmark Docker Image

**Status**: Draft
**Created**: 2026-06-14
**Last Updated**: 2026-06-14
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Provide a Docker image that packages the TinyCUA prototype for WildClawBench benchmark evaluation, enabling TinyCUA to run as a comparable agent harness alongside OpenClaw, Claude Code, Codex CLI, and Hermes Agent.
- **Gaps**: Currently, TinyCUA has no standardized Docker runtime for benchmark execution. The prototype requires manual setup of dependencies, local model endpoints, and environment configuration to run within WildClawBench's containerized task environment.
- **Non-Goals**: Production-grade container orchestration, CI/CD pipeline integration, hosted model serving, judge LLM subscription management, or modifications to WildClawBench tasks.
- **Constraints**: Must work with WildClawBench's existing container lifecycle (workspace mounting at `/tmp_workspace`), must support local OpenAI-compatible model endpoints, must preserve benchmark artifacts (transcripts, logs, task outputs) for grading.

---

## User Scenarios & Testing

### Primary Scenario

A benchmark researcher wants to evaluate TinyCUA against other agent harnesses using WildClawBench. They build the TinyCUA Docker image, configure their local model endpoint, and run the benchmark suite. The container starts, mounts the task workspace, executes the TinyCUA agent with the task prompt, writes results to `/tmp_workspace/results`, and produces a transcript compatible with WildClawBench's grading system.

### Acceptance Scenarios

1. **Given** the Docker image is built, **When** a researcher runs `docker build -t tinycua-benchmark .`, **Then** the image builds successfully with all TinyCUA dependencies installed.
2. **Given** the Docker image is built, **When** the container starts with a local model endpoint configured, **Then** the container can reach the endpoint via the configured URL.
3. **Given** the container is running, **When** a trivial TinyCUA task is executed, **Then** the agent produces output in `/tmp_workspace/results` and generates a transcript compatible with WildClawBench grading.
4. **Given** the container is running, **When** environment variables are injected (e.g., `BRAVE_API_KEY`), **Then** the TinyCUA agent can use them for tool execution.
5. **Given** the container is running, **When** the task workspace is mounted at `/tmp_workspace`, **Then** the agent can read task files and write results to the expected location.

### Edge Cases

- What happens when the local model endpoint is unreachable? The container should start but the agent should fail gracefully with a clear error message about endpoint connectivity.
- What happens when required environment variables (e.g., `BRAVE_API_KEY`) are missing? The container should start but tool-dependent tasks may fail with appropriate warnings.
- What happens when the container runs out of resources? The agent should handle timeout/cancellation gracefully and preserve any partial results.
- What happens when the task workspace is read-only? The agent should detect write failures and report them without crashing.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a Dockerfile that builds a runnable container image for TinyCUA benchmark execution.
- **FR-002**: System MUST install the TinyCUA prototype and its dependencies within the container.
- **FR-003**: System MUST include required shell, file, browser, and search dependencies as documented in the WildClawBench adapter contract.
- **FR-004**: System MUST support configuration of a local OpenAI-compatible model endpoint via environment variables (e.g., `TINYCUA_MODEL_ENDPOINT`).
- **FR-005**: System MUST mount the task workspace at `/tmp_workspace` as per WildClawBench conventions.
- **FR-006**: System MUST allow injection of additional environment variables (e.g., `BRAVE_API_KEY`) for benchmark tools.
- **FR-007**: System MUST preserve benchmark artifacts (transcripts, logs, task outputs) within the container for later extraction.
- **FR-008**: System MUST support running a trivial TinyCUA task as a smoke test to verify the container works.
- **FR-009**: System MUST document all required and optional environment variables, volume mounts, and runtime configuration.
- **FR-010**: System MUST target a container image size under 2GB for reasonable CI/build times.

### Key Entities

- **Dockerfile**: Build instructions that produce a runnable container image with TinyCUA and all dependencies.
- **Container Runtime**: The executing container environment with access to local model endpoint, task workspace, and environment variables.
- **Task Workspace**: Directory mounted at `/tmp_workspace` containing task files and receiving results.
- **Local Model Endpoint**: OpenAI-compatible API endpoint (e.g., vLLM, Ollama, LM Studio) accessible from within the container.
- **Benchmark Artifacts**: Transcripts, logs, and task outputs produced during execution for grading and analysis.

---

## Success Criteria

- [ ] **Dockerfile exists and builds**: `docker build -t tinycua-benchmark .` completes successfully.
- [ ] **Container starts and runs**: `docker run tinycua-benchmark` starts without errors.
- [ ] **Local model connectivity**: Container can reach configured local model endpoint.
- [ ] **Task workspace mounting**: `/tmp_workspace` is accessible and writable within the container.
- [ ] **Environment variable injection**: `BRAVE_API_KEY` and other env vars are accessible to the agent.
- [ ] **Trivial task execution**: Container runs a simple test task and produces output in `/tmp_workspace/results`.
- [ ] **Transcript generation**: Container produces a transcript compatible with WildClawBench grading.
- [ ] **Artifact preservation**: Transcripts, logs, and outputs are preserved for extraction.
- [ ] **Documentation complete**: All configuration options, environment variables, and usage instructions are documented.
- [ ] **Image size target**: Final image size is under 2GB.

---

## Testing Plan

### Unit Tests

- Not applicable — this milestone is infrastructure/packaging, not code logic.

### Integration Tests

- **Build test**: Verify Dockerfile builds successfully on target platform.
- **Startup test**: Verify container starts and reaches a ready state.
- **Connectivity test**: Verify container can reach a mock local model endpoint.
- **Workspace test**: Verify `/tmp_workspace` mounting and read/write operations.
- **Environment test**: Verify environment variable injection and accessibility.
- **Smoke test**: Run a trivial TinyCUA task end-to-end within the container.
- **Artifact test**: Verify transcript, log, and output files are generated and preserved.

### Manual Tests

- Build the image on a development machine and verify it runs.
- Test with a real local model endpoint (e.g., Ollama, LM Studio).
- Run a single WildClawBench task manually to verify compatibility.
- Check container logs for any missing dependencies or configuration issues.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Dockerfile creation | TODO | |
| Dependency documentation | TODO | |
| Environment variable configuration | TODO | |
| Local model endpoint support | TODO | |
| Task workspace mounting | TODO | |
| Smoke test task | TODO | |
| Documentation | TODO | |
| Image size optimization | TODO | |

---

## Open Questions

1. **Base image selection**
   - **Owner**: @tinycua-team
   - **Target**: 2026-06-15
   - **Status**: Proposed
   - **Proposed Answer**: Use `python:3.11-slim` as base for minimal footprint, with additional layers for system dependencies.

2. **Dependency scope**
   - **Owner**: @tinycua-team
   - **Target**: 2026-06-15
   - **Status**: Proposed
   - **Proposed Answer**: Include only dependencies required for TinyCUA core functionality and WildClawBench compatibility. Browser/multimedia tools may be optional for initial benchmark runs.

3. **Local model endpoint configuration**
   - **Owner**: @tinycua-team
   - **Target**: 2026-06-15
   - **Status**: Proposed
   - **Proposed Answer**: Use environment variables `TINYCUA_MODEL_ENDPOINT` and `TINYCUA_MODEL_API_KEY` for OpenAI-compatible endpoint configuration.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices) — Dockerfile specification is configuration, not implementation code
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable