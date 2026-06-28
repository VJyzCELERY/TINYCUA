# Feature Specification: TinyCUA Actionable Runtime Traceability

**Status**: In Progress
**Created**: 2026-06-15
**Last Updated**: 2026-06-15
**Subproject(s) Affected**: `src/tinycua`

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a functional TinyCUA prototype runtime so users can watch
  node-scoped reasoning/action streams, see task-tree progress, and have the
  agent actually use workspace/web/shell tools to complete action requests.
- **Gaps**: The finalized prototype can route and maintain task state, but live
  notebook behavior still looks like plan-only scaffolding. Streaming does not
  present a readable node transcript, worker execution may stop at textual
  planning, task tree display is JSON-heavy, and reusable in-memory sessions are
  not explicitly validated.
- **Non-Goals**: Persistent session storage, SDK changes, unrestricted file
  system access, browser automation, deployment of generated apps, and remote
  credential management are out of scope.
- **Constraints**: Do not modify `src/tinycua-sdk/`. All filesystem/shell/python
  side effects MUST remain inside `SessionConfig.workspace_dir`. Web search MUST
  use the configured public SearXNG endpoint without auth.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A user asks TinyCUA to create an app. The runtime routes to worker mode, builds
a task tree, streams node-prefixed transcript output, uses file/shell/python/web
tools inside the workspace, updates task state with real tool results, and
returns a final answer summarizing created artifacts and verification status.

### Acceptance Scenarios

1. **Given** a TinyCUA agent with a workspace, **When** the user asks it to
   create a simple app, **Then** it writes files, runs verification commands,
   records tool results, and exposes artifacts in task state.
2. **Given** streaming mode, **When** multiple nodes run, **Then** stream events
   can be rendered as `[USER]`, `[QueryAnalyst]`, `[TaskExecutor]`, and
   `[TaskExecutor][write_file]` transcript lines without duplicate downstream
   spam.
3. **Given** an existing `Session`, **When** two `agent.run(...)` calls reuse it,
   **Then** task state, todo state, chat history, and compacted context remain
   available for continuation.
4. **Given** a task tree, **When** notebook/CLI displays state, **Then** users see
   a readable hierarchy like `Task []` and nested subtasks, not only raw JSON.

### Edge Cases

- Tool paths outside the workspace are rejected and traced.
- Shell commands that fail or time out are recorded as failed tool results.
- Web search endpoint failures produce structured tool errors, not synthetic
  success.
- Empty streamed chunks do not create duplicate transcript lines.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Streaming MUST expose node-prefixed transcript events for user
  input, node text deltas, tool calls, and tool results.
- **FR-002**: Streaming MUST avoid repeated downstream copies of prior node
  output in user-facing transcript events.
- **FR-003**: Worker execution MUST have access by default to workspace-confined
  file, shell, python, and web search tools.
- **FR-004**: Action-oriented tasks MUST be able to create directories/files,
  run commands/tests, and record resulting artifacts/tool outputs in task state.
- **FR-005**: SearXNG web search MUST be available to TinyCUA agents by default
  via `https://searxng.salmon-crested.ts.net`.
- **FR-006**: Notebook/CLI MUST expose a readable task-tree text view in addition
  to JSON snapshots.
- **FR-007**: Reusing an in-memory `Session` across agents/runs MUST preserve
  task state, todo state, chat history, and compaction inputs.
- **FR-008**: Runtime trace entries MUST include actual LLM-visible tools,
  forced tool-choice metadata, and tool-result evidence.
- **FR-009**: No implementation may modify `src/tinycua-sdk/`.

### Key Entities _(include if feature involves data)_

- **Transcript Event**: Node/user/tool-scoped event suitable for rendering as a
  readable stream line.
- **Task Tree Text View**: Bounded text rendering of task hierarchy with statuses
  and active-task markers.
- **Action Tool Result**: Structured result from file/shell/python/web tool use,
  attached to traces and task results.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Readable stream**: Streaming a worker run emits node-prefixed text and
  tool events with no duplicate downstream spam.
- [ ] **Actual action**: A deterministic app-creation test writes files and runs
  a verification command in the configured workspace.
- [ ] **Task tree visible**: Notebook/CLI can display `Task []` hierarchy text.
- [ ] **Web search available**: Default TinyCUA agents expose SearXNG search to
  worker execution without SDK changes.
- [ ] **Session continuation**: Two runs sharing one `Session` continue the same
  in-memory task/chat/todo context.
- [ ] **Safety**: Workspace confinement remains enforced for file/shell/python
  tools.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Transcript event rendering and node/tool labels.
- Task tree text rendering for nested tasks.
- Default action tool exposure and SearXNG tool schema.
- Session reuse preserves runtime state.

### Integration Tests

- Deterministic worker app-creation flow writes files and runs shell tests.
- Streaming worker flow emits readable node/tool events and final response.
- Notebook contract validates readable task tree and action artifacts.

### Manual Tests _(if applicable)_

- Live local LLM: ask TinyCUA to create a small app and inspect streamed trace,
  task tree, workspace files, and test command output.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Spec/design | In Progress | Same worktree/branch as PR #141 finalization |
| SDK changes | Done | Explicitly prohibited |

---

## Open Questions _(optional)_

None.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
