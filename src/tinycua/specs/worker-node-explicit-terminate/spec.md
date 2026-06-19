# Feature Specification: Worker Node Explicit Terminate

**Status**: In Progress
**Created**: 2026-06-19
**Last Updated**: 2026-06-19
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Provide explicit worker-lifecycle node termination so models can continue optional post-condition work, such as reviewer context curation, before ending a node.
- **Gaps**: Today a worker lifecycle node terminates as soon as validation conditions pass. ResultReviewer can decide and inspect, then terminate before seeing inspect results or curating unfinished task context.
- **Non-Goals**: No user-facing “plan mode”; no route/final-response node changes.
- **Constraints**: Existing node required conditions remain runtime-owned. `terminate()` is only a completion signal, not authority to bypass validation.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A worker lifecycle node performs required tool calls. The runtime then exposes `terminate()` and keeps the node alive so the model may do optional node-specific work before explicitly terminating.

### Acceptance Scenarios

1. **Given** ResultReviewer has called `task_review_decision` and `task_inspect`, **When** it has not called `terminate`, **Then** the runtime keeps the node alive and exposes `terminate` on retry.
2. **Given** ResultReviewer calls `task_update` and `terminate` after review requirements are met, **When** validation runs, **Then** the reviewer completes.
3. **Given** a worker lifecycle node calls `terminate` before required conditions, **When** validation runs, **Then** termination is rejected.

### Edge Cases

- Terminate is not exposed to route/final nodes.
- Terminate cannot complete a node with missing required tool calls.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Worker lifecycle nodes MUST require successful `terminate()` before completion.
- **FR-002**: Runtime MUST expose `terminate()` only after node-specific required conditions are satisfied.
- **FR-003**: Runtime MUST reject `terminate()` when required conditions are still missing.

### Key Entities _(include if feature involves data)_

- **TerminateTool**: Runtime tool that records an explicit node completion request.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Reviewer can curate before ending**: ResultReviewer gets a post-inspect turn before completion.
- [ ] **Runtime remains authoritative**: `terminate()` cannot bypass missing required state changes.
- [ ] **Existing flows still work**: Worker lifecycle tests pass with one explicit termination step.

---

## Testing Plan _(mandatory)_

### Unit Tests

- ResultReviewer missing `terminate` after decision+inspect retries instead of completing.
- Retry tool set exposes `terminate` only after requirements are met.
- `terminate` before requirements remains invalid.

### Integration Tests

- Existing worker lifecycle tests should still complete.

### Manual Tests _(if applicable)_

- Run `tinycua run` against local qwen model for a multi-task prompt.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Spec | Done | Minimal scope |
| Tests | TODO | Add before code |
| Implementation | TODO | Terminate tool + validation |

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
