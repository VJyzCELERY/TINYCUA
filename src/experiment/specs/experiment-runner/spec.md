# Feature Specification: Experiment Runner

**Status**: Complete
**Created**: 2026-06-19
**Last Updated**: 2026-06-19
**Subproject(s) Affected**: experiment

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a batch runner so experiment prompts can be listed once, run sequentially, judged by the existing LLM judge, and archived. Prevent known Hermes background-process polling hangs from consuming the full experiment timeout. Share SearXNG web search configuration across harnesses that support it.
- **Gaps**: Today prompts are stored as repeated shell commands in `tmp/experiment_command.txt`, and results must be judged/cleaned up manually.
- **Non-Goals**: New judging logic, parallel execution, dashboards, or a new results schema.
- **Constraints**: Use existing `run_experiment.py` and `judge.py`; experiments must run sequentially.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A user writes `Experiment_1: <prompt>` lines in a text file, runs one script, waits while each experiment runs one after another, then receives a timestamped archive containing results and judge verdicts.

### Acceptance Scenarios

1. **Given** a prompt list, **When** the runner is executed, **Then** each experiment runs in manifest order.
2. **Given** completed experiments, **When** judging finishes, **Then** the requested experiment result folders are moved out of `results/` into an archive.

### Edge Cases

- Empty prompt files fail before running anything.
- Existing results are overwritten only when requested by the batch runner.
- Failed experiment/judge commands are recorded; `--fail-fast` stops early.
- Hermes background process polling is capped separately from the full experiment timeout.
- Harnesses with native SearXNG web search support receive the SearXNG URL.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST parse prompt lines shaped as `Experiment_<number>: <prompt>`.
- **FR-002**: System MUST run each parsed experiment sequentially through `run_experiment.py`.
- **FR-003**: System MUST run `judge.py` for each attempted experiment, including failed or timed-out agent results.
- **FR-004**: System MUST archive the requested experiment outputs after judging.
- **FR-005**: System MUST stop Hermes when its process-poll tool stays unresolved beyond the configured poll timeout.
- **FR-006**: System MUST expose SearXNG configuration to TinyCUA, Hermes, OpenClaw, and other harnesses that recognize it.

### Key Entities _(include if feature involves data)_

- **Prompt manifest**: Text file mapping experiment number to prompt.
- **Experiment archive**: Timestamped directory containing manifest and judged result folders.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [x] **User can run a batch**: one script consumes a prompt list and runs experiments sequentially.
- [x] **System judges outputs**: existing LLM judge writes verdicts before archiving.
- [x] **Results are cleaned up**: archived experiment folders are removed from active `results/`.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Manifest parsing accepts valid lines and rejects empty files.
- Archiving moves only requested experiment directories.
- Hermes poll timeout detects stuck `process poll` output.
- Static checks cover SearXNG env/config wiring for harness containers.

### Integration Tests

- Manual dry run with small prompts when Docker/LLM services are available.

### Manual Tests _(if applicable)_

- `uv run python run_batch_experiments.py --manifest tmp/experiment_prompts.txt --dry-run`

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
