# Feature Specification: TinyCUA Prompt Quality

**Status**: In Progress
**Created**: 2026-06-19
**Last Updated**: 2026-06-19
**Subproject(s) Affected**: src/tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Improve TinyCUA internal node instructions and prompt construction so that:
  1. Coherency is maintained across nodes without exposing full context directly (a canonical "mission" carries the goal).
  2. Tool usage is consistent despite the number of tools available (per-node behavioral guidance, not prose tool lists).
  3. Internal communication (retry/handoff) is not framed as a "user" instruction (use `[System: ...]` prefix on user-role messages).
  4. The architecture still follows the flow documented in `docs/design/` (no routing, node, or permission changes).
  5. Only relevant context is exposed to each LLM and its role is clear (scope-boundary lines).
  6. Tool usage is clear so the LLM does not mistake tool calls (proactive required-tool line + `tool_choice` forcing).
  7. Task result quality improves: the reviewer substantively reviews (soft nudge, no crashes), and original user constraints survive task decomposition (stored on the task tree and rendered into every worker-internal node continuation).
- **Gaps**: Experiment 3 showed TinyCUA decomposed a single-file HTML request into multi-file Flask-style artifacts (constraints lost during decomposition), and ResultReviewer looped on repeated rejection instead of terminating. Retry messages framed as "user" corrections shift the LLM into answer-the-user mode mid-task. No canonical goal object travels with the task tree.
- **Non-Goals**:
  - No new nodes, no routing changes, no node permission changes.
  - No new tools, no dependency changes, no benchmark runner changes.
  - No three-tier prompt cache rewrite, no progressive tool disclosure / `tool_search` bridge.
  - No new `system` role mid-turn, no custom `internal` message role.
  - No hard "crashing" validation failures for reviewer verification (soft nudge only).
  - No `docs/design/` modifications (those are the source of truth).
  - No `Task` dataclass schema change (new fields live in the existing `metadata` dict).
- **Constraints**:
  - `terminate` remains required for lifecycle nodes to proceed to the next node.
  - ResultReviewer stays read-only except task-state curation tools.
  - Internal handoffs/retries keep `role:"user"` (provider alternation requirement) but use a `[System: ...]` prefix to distinguish origin.
  - `mission` is immutable after Task Creation except when `replan` restructures the tree.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A user asks TinyCUA to complete a task with explicit constraints (e.g. "single HTML file"). TinyCUA decomposes and executes the task while preserving the original request and constraints in every worker-internal node continuation (TaskAnalyzer, TaskAssessor, TaskExecutor, ResultReviewer, ResultAggregation) via a compact `## Mission` block. When review work is complete, ResultReviewer substantively verifies with read-only tools (or states why verification was skipped) and terminates so the runtime continues.

### Acceptance Scenarios

1. **Given** a task with original user constraints, **When** TaskCreate initializes the root task, **Then** `root.metadata["mission"]` and `root.metadata["inherited_constraints"]` are populated from `DigestedInformation` (or raw user query).
2. **Given** a parent task with `inherited_constraints`, **When** TaskAnalyzer calls `task_decompose`, **Then** each child task inherits `metadata["inherited_constraints"]` from the parent.
3. **Given** any worker-internal node (Analyzer/Assessor/Executor/Reviewer/Aggregation), **When** it builds its continuation, **Then** a compact `## Mission` block (original request + hard constraints) is rendered.
4. **Given** a validation retry, **When** the retry prompt is built, **Then** it is prefixed `[System: ...]` and uses imperative directive voice (no "Correction for the previous response:" / "I need to" first-person framing).
5. **Given** a node with a single required tool, **When** its system message is built, **Then** a proactive "Your final action MUST call `<tool>`" line is present alongside behavioral tool guidance.
6. **Given** ResultReviewer approves a task with file artifacts, **When** no read-only verification tool was called in the batch, **Then** a soft transcript note is recorded (never a validation crash).
7. **Given** any node, **When** its instruction is built, **Then** a one-line scope boundary ("You only <verb>; you do not <forbidden>") is present.

### Edge Cases

- Reviewer rejects a result: it must not try to edit files directly; it records feedback and terminates.
- A future task needs context from review: reviewer may call `task_update` before terminating.
- A prompt asks for a single deliverable file: executor AND analyzer context must keep that constraint visible on child tasks (via inherited_constraints).
- No `DigestedInformation` exists (passthrough/no-digest path): `mission` falls back to the raw user query from `input_context`.
- `replan` restructures the tree: the new root/parent may re-derive `mission` from the existing session digest; old constraints remain valid unless explicitly revised by the replan.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST store a `mission` (original request) and `inherited_constraints` on the root task's `metadata` at Task Creation time, derived from `DigestedInformation` when available or the raw user query otherwise.
- **FR-002**: System MUST propagate `inherited_constraints` from a parent task to each child task on `task_decompose`.
- **FR-003**: System MUST render a compact `## Mission` block (original request + hard constraints) into the continuation of every worker-internal node: TaskAnalyzer, TaskAssessor, TaskExecutor, ResultReviewer, ResultAggregation.
- **FR-004**: System MUST frame retry prompts as `[System: ...]` directive messages in `role:"user"`, using imperative voice, without first-person "I need to" → second-person "You need to" conversion.
- **FR-005**: System MUST inject per-node behavioral tool guidance (keyed on tool names present, not a prose tool list) via the existing `build_tool_system_prompt` hook.
- **FR-006**: System MUST add a proactive "Your final action MUST call `<tool>`" line to the initial instruction of nodes with a single required tool, complementing the existing `tool_choice="required"` forcing.
- **FR-007**: System MUST add a one-line scope boundary to each node instruction ("You only <verb>; you do not <forbidden>").
- **FR-008**: System MUST strengthen the ResultReviewer instruction to require read-only verification evidence before approving tasks with file artifacts (or state why skipped).
- **FR-009**: System MUST record a soft transcript note (never a validation crash) when ResultReviewer approves a task with file artifacts but called no read-only verification tool in the batch.
- **FR-010**: System MUST keep `terminate` mandatory for lifecycle nodes to advance.
- **FR-011**: System MUST keep prompts concise and generic across coding, research, and mixed tasks.
- **FR-012**: System MUST NOT add new nodes, change routing, or change node tool permissions.
- **FR-013**: System MUST NOT modify `docs/design/` files.
- **FR-014**: System MUST NOT change the `Task` dataclass schema (new fields live in the existing `metadata` dict).

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Mission populated**: root task has `metadata["mission"]` after Task Creation with a digest present.
- [ ] **Constraints propagate**: child tasks inherit `inherited_constraints` after `task_decompose`.
- [ ] **Mission rendered**: each worker-internal node continuation contains `## Mission`.
- [ ] **Retry framed**: retry prompts start with `[System:` and contain no "Correction for the previous response" / "I need to".
- [ ] **Tool guidance present**: each node's system message contains behavioral guidance keyed on its tools.
- [ ] **Required-tool line proactive**: single-required-tool nodes have the "MUST call" line in the initial instruction.
- [ ] **Scope boundary present**: each node instruction has a "You only ...; you do not ..." line.
- [ ] **Reviewer verifies**: reviewer instruction requires read-only verification evidence for file artifacts.
- [ ] **Soft nudge, no crash**: approval-without-verification produces a transcript note, not a validation error.
- [ ] **No architecture change**: no new nodes, no routing changes, no node permission changes.
- [ ] **No design doc edits**: `docs/design/` untouched.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_task_create_mission.py`: root task `metadata["mission"]` populated from digest / raw query.
- `test_task_decompose_constraints.py`: child tasks inherit `inherited_constraints` on `task_decompose`.
- `test_mission_rendering.py`: each worker-internal node continuation contains `## Mission` when root has mission metadata.
- `test_retry_prompt_framing.py`: retry message starts with `[System:`, no "Correction for the previous response" / "I need to".
- `test_tool_guidance_prompt.py`: each node's system message contains expected behavioral guidance when its tools are present; empty when absent.
- `test_reviewer_verification_nudge.py`: transcript note appears on approval-without-verification; no validation error; no nudge when read-only tool was called.
- Update existing tests asserting old retry text (`test_retry_validation.py`, `test_result_reviewer_inspect_protocol.py`, `test_actionable_traceability.py`).

### Integration Tests

- Not required for this prompt-quality change; covered by smoke test below.

### Manual Tests _(if applicable)_

- Rerun experiment 3 ("Make me a simple analog clock app with animation in a single HTML file") against the local LLM server (`qwen3.5-9b` at `localhost:1234`) and confirm constraints survive decomposition and reviewer terminates cleanly.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable