# Feature Specification: Agent Harness Experiment

**Status**: Draft  
**Created**: 2026-06-18  
**Last Updated**: 2026-06-18  
**Subproject(s) Affected**: experiment

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a small experiment environment so researchers can run the same prompt through Opencode, Hermes, Openclaw, and TINYCUA, then compare readable artifacts and elapsed time.
- **Gaps**: Today there is no shared harness for running these agent systems under the same prompt, model/provider settings, output layout, and timing measurement.
- **Non-Goals**: This does not provide a leaderboard, web UI, database, statistical benchmark suite, parallel execution scheduler, or hardened sandbox for untrusted prompts.
- **Constraints**: The environment should live under `src/experiment`, prefer plain files over services, and prioritize readable comparison output over comprehensive automation.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A researcher configures shared LLM settings once, provides a prompt, runs the experiment, and receives one result directory per agent containing the prompt, logs, metadata, and timing information.

### Acceptance Scenarios

1. **Given** a configured experiment environment and prompt, **When** the researcher starts experiment `1`, **Then** Opencode, Hermes, Openclaw, and TINYCUA run sequentially with the same prompt.
2. **Given** any agent run completes or fails, **When** the run finishes, **Then** that agent's result directory contains enough plain-text artifacts to compare behavior and diagnose failure.
3. **Given** shared LLM settings, **When** each agent starts, **Then** each agent receives normalized model/provider configuration from the same source.

### Edge Cases

- Empty prompts are rejected before any agent starts.
- If one agent fails, its failure is recorded and later agents still run unless the user requests fail-fast behavior.
- If an experiment number already exists, the user must explicitly choose whether to overwrite it or use a new number.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST run Opencode, Hermes, Openclaw, and TINYCUA in a fixed sequential order.
- **FR-002**: System MUST pass the same prompt to every agent in one experiment.
- **FR-003**: System MUST provide a shared configuration source for LLM provider, model, base URL, API key, and comparable runtime settings.
- **FR-004**: System MUST run each agent harness in its own separate container.
- **FR-005**: System MUST keep each agent's workspace and results isolated from the other agents.
- **FR-006**: System MUST write per-agent output artifacts under `experiment-{num}/` within that agent's persistent storage.
- **FR-007**: System MUST record start time, end time, duration, agent name, experiment number, and exit code for every agent run.
- **FR-008**: System MUST preserve stdout and stderr for every agent run.
- **FR-009**: System SHOULD continue running remaining agents after one agent fails, while clearly marking the failure.
- **FR-010**: System SHOULD favor readable files and simple commands over a comprehensive benchmarking platform.

### Key Entities _(include if feature involves data)_

- **Experiment**: One run of a single prompt across all configured agent harnesses. Key attributes: number, prompt, shared configuration snapshot, agent results.
- **Agent Result**: The output of one agent for one experiment. Key attributes: agent name, logs, duration, status, exit code, artifact paths.
- **Shared Configuration**: Normalized LLM and runtime settings consumed by all agents.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Researcher can run one prompt across all agents**: one command executes Opencode, Hermes, Openclaw, and TINYCUA sequentially.
- [ ] **Results are easy to compare**: each agent writes prompt, stdout, stderr, and metadata files in a consistent layout.
- [ ] **Timing is captured**: every agent result records elapsed seconds.
- [ ] **Configuration is shared**: one settings file controls provider/model settings for all four agents.
- [ ] **Failures are visible**: failed agent runs leave logs and non-zero exit codes without hiding later results.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Validate experiment number/path selection and overwrite protection.
- Validate prompt rejection for empty input.
- Validate metadata generation shape for success and failure cases.

### Integration Tests

- Run a dry-run or stub command path that simulates all four agents without requiring real LLM credentials.
- Verify result directories and logs are created for every agent in order.

### Manual Tests _(if applicable)_

- Build the experiment containers.
- Run one real prompt with local or hosted LLM credentials.
- Compare the four generated `metadata.json`, `stdout.log`, and `stderr.log` files.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Spec | Done | Initial lightweight scope. |
| Design | Done | Defines simple compose + runner layout. |
| Implementation | TODO | Test-first after design. |

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
