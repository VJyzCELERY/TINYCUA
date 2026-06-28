# Feature Specification: TINYCUA Review-Loop Hardening

**Status**: Draft
**Created**: 2026-06-25
**Last Updated**: 2026-06-25
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Cut the executor↔reviewer loop count on hard tasks (where the
  reviewer churns on a single task many times) and cut the turns the
  reviewer wastes re-locating files it mis-guessed. Preserve the existing
  replan/force-approve cap machinery; only tighten its trigger and the
  in-session decision discipline.
- **Gaps** (evidence from `src/experiment/results/tinycua/`):
  - **Review-decision churn.** Experiment-4 task `69de662b` (REST API
    endpoints) was reviewed **14 times** — 11 `needs_revision`, 3
    `rejected`, then `replan` — before the replan budget exhausted and
    force-approved. The replan mechanism fires (`replan_triggered` logged
    at `consecutive_failures=5`, `replan_budget_exhausted` at
    `replan_count=3/3`), but the default `replan_threshold=5` lets a stuck
    task burn ~15 review calls across 3 replan cycles before giving up.
    There is also no enforcement that a reviewer emits at most one
    `task_review_decision` per session — the model can flip-flop
    (`needs_revision` → `approved` → `needs_revision`) inside one session,
    and each decision is just appended to `reviewer_decisions`.
  - **Path-guessing by the model.** Experiment-4 reviewer logged 10
    `read_file` "not found" failures and spent 3-5 extra turns per
    failure re-listing, re-reading, and re-reasoning because it guessed
    wrong paths (e.g. `backend/routing.py` when the file lives at
    `backend/django_notion_app/channels/routing.py`). The existing
    `resolve_workspace_path` (FR-035) strips doubled workspace prefixes
    and re-roots absolute paths — that works (only 1 doubled-path write
    slipped through) — but it cannot fix the model just *guessing wrong*.
    The reviewer gets no help locating files: `list_files` returns a flat
    list, and `read_file` not-found gives no suggestion.
  - **Premature task completion (task skipping).** Experiment-2 task 14
    ("Review and finalize report.md") was marked `[completed]` while
    tasks 5-13 were still `[pending]`. The reviewer ignored guidance
    ("Do NOT call task_review_decision for siblings") and approved
    task 14 — a PENDING leaf never dispatched. The FR-079
    synthetic-result fallback silently created a fake "Approved by
    reviewer" result and completed it. No guard exists against approving
    a task that was never executed, and `record_result` auto-transitions
    any task PENDING → IN_PROGRESS (even non-active ones), so the
    prerequisite status is silently advanced for out-of-order tasks too.
  - **Stream-path provider errors kill the process.** Experiments 2, 3,
    and 5 all failed with `Agent error: [0] OpenAI Chat Completions API
    stream error:` — LM Studio dropped the SSE stream mid-response.
    The sync path has FR-086 catch-and-retry (`_call_llm_with_provider_retry`),
    but the stream path (`_stream_llm_node_events` → `_collect_stream_events`)
    calls `_call_agent_llm` directly with no retry wrapper. A single
    stream drop crashes the whole experiment. The error message was
    empty (`str(exc)` was `""`), giving no diagnostic signal.
  - **Trade-off to watch (deferred).** Experiment-2 sourcing regressed
    (20 → 4 source links in `report.md`) as reviewer pressure dropped
    (old: 11 `needs_revision` + 1 `rejected`; new: 2 `needs_revision`).
    Lowering `replan_threshold` further reduces review pressure and may
    worsen this on research tasks. This spec does **not** address it —
    flagged as a known trade-off and deferred to a separate future spec.
- **Non-Goals**:
  - Hard total cap on review calls per task (rejected during planning —
    the existing replan budget cap is sufficient once the threshold is
    lowered).
  - Deterministic verifier helpers like `file_exists`/`python_import`/
    `command_ok` (rejected as too domain-specific).
  - Supersession metadata for overturning prior review decisions across
    sessions (rejected — too much machinery for the gain).
  - Task-type-aware review depth / Exp2 research-task quality regression
    (deferred to a separate future spec).
  - Changing the node-graph architecture (no new nodes, no new tools).
  - Token-budget / tool-output truncation work (covered by the earlier
    `tinycua-runtime-performance-hardening` spec, different scope).
- **Constraints**:
  - Must preserve the zero-exit guarantee (force-approve at replan
    budget exhaustion stays).
  - Must not change `schedule_after_review` / `schedule_replan` /
    `_force_approve_at_cap` control flow — only the threshold default and
    a new in-session validator.
  - `recovery_strategy == "standard"` behavior must remain bit-for-bit
    unchanged except for the threshold default and the new single-decision
    validator (which applies in both strategies).
  - Backward-compatible: existing tests that assert `replan_threshold=5`
    must be updated, not broken silently.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A worker-mode run hits a task the small LLM cannot complete correctly
(e.g. "create REST API endpoints for CRUD on documents/pages/blocks").
The reviewer rejects it. Today the runtime retries the executor up to 5
consecutive times before replanning, and the reviewer may emit multiple
conflicting decisions in one session. After this spec, the runtime
retries up to 3 consecutive times before replanning, and the reviewer
can emit at most one decision per session — so the loop converges faster
and cannot flip-flop internally.

### Acceptance Scenarios

1. **Given** a `WorkerRuntimeController` with no explicit `replan_threshold`,
   **When** it is constructed, **Then** its `replan_threshold` defaults to
   `3` (not `5`).
2. **Given** a reviewer session whose LLM response contains two
   `task_review_decision` tool calls, **When** the validation chain runs,
   **Then** the response is rejected with an error naming the single-decision
   rule, and the node is retried (no decision is recorded until a
   single-decision response passes).
3. **Given** a reviewer that calls `list_files`, **When** the result is
   rendered, **Then** the output groups entries by directory and shows full
   workspace-relative paths (not a flat bare-name list).
4. **Given** a reviewer that calls `read_file` with a path that does not
   exist under the workspace, **When** a close match exists in the workspace
   (≤2 path-segment differences), **Then** the not-found result includes a
   "Did you mean `X`?" suggestion with the closest existing relative path.
5. **Given** a reviewer that calls `read_file` with a non-existent path and
   no close match exists, **When** the result is rendered, **Then** it
   returns a plain not-found with no suggestion (no misleading guesses).
6. **Given** a task that fails 3 consecutive reviews, **When** the 3rd
   `needs_revision`/`rejected` decision is recorded, **Then**
   `schedule_after_review` routes to TaskAnalyzer for replan (not another
   executor retry).
7. **Given** a PENDING leaf task with no result and no children, **When**
   `record_reviewer_decision` is called with `approved`, **Then** it
   raises `ValueError` and the task remains PENDING (no fake result, no
   status change).
8. **Given** a non-active task in PENDING status, **When** `record_result`
   is called on it, **Then** the result is attached but the task stays
   PENDING (not auto-transitioned to IN_PROGRESS).
9. **Given** a stream path LLM call that raises `ProviderApiError` on the
   first attempt, **When** `_stream_llm_node_events` catches it, **Then**
   it force-compacts, clears partial stream state, and retries; on the
   second attempt the stream succeeds and the node completes.

### Edge Cases

- What if the reviewer emits one `task_review_decision` and one
  `task_update` in the same session? Allowed — the single-decision rule
  counts only `task_review_decision` calls, not other task-state tools.
- What if `list_files` is called on an empty workspace? Returns an empty
  tree with the workspace root noted, no crash.
- What if the closest-match path is the workspace root itself? Do not
  suggest the root as a file — only suggest actual files.
- What if `replan_threshold` is set explicitly by session config
  (`worker_effort` → `max_replans`)? The explicit value wins; only the
  *default* changes to 3.
- What if a reviewer session legitimately wants to overturn its own
  earlier decision? It must terminate and start a new reviewer session;
  the new session's decision supersedes by virtue of being later in the
  `reviewer_decisions` audit trail. No explicit supersession field.
- What if the executor records a result on a non-active sibling (the
  sibling-propagation feature)? The result is attached but the sibling
  stays PENDING. Once the current task is approved and the sibling
  becomes active, `schedule_next` sees the result and skips the
  executor (review-only). This is the intended behavior — the
  sibling's status does not advance until the runtime dispatches it.
- What if the analyzer uses `task_update` on a non-active task? Allowed
  — the analyzer can modify any non-completed task (title, description,
  planning status). FR-5b only guards `record_result`, not `task_update`.
- What if a non-active task already has a result and is later approved
  by mistake? The FR-5a guard only fires when `task.result is None`;
  a task with a recorded result can still be approved (the sibling-
  propagation case). This is intentional — the result exists because
  work was done, even if out of order.
- What if a stream error occurs after some events were already yielded?
  The partial `content_parts` and `collected_tool_calls` are cleared on
  retry — the consumer sees a brief pause in events, then the stream
  restarts. The partial data is garbage (the stream was incomplete).
- What if `asyncio.CancelledError` is raised during streaming? It is
  re-raised immediately without retry — cancellation is intentional, not
  a recoverable provider error.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-1**: `WorkerRuntimeController.replan_threshold` MUST default to `3`.
  The existing `replan_threshold` constructor argument and session-config
  override path remain unchanged; only the default value changes from `5`
  to `3`.

- **FR-2**: The validation chain MUST reject any `result_reviewer` node
  response whose tool_results contain more than one successful
  `task_review_decision` call. The rejection error MUST name the
  single-decision rule and instruct the reviewer to terminate and start a
  new session to overturn a prior decision. No decision is recorded for a
  rejected multi-decision response; the node is retried. This validator
  runs in both `recovery_strategy="standard"` and `"markdown_synthesis"`.

- **FR-3**: `list_files` output MUST render as a tree grouped by directory,
  showing full workspace-relative paths for each entry (e.g.
  `backend/django_notion_app/views.py`, not just `views.py`). The
  underlying walk behavior (recursive vs scoped) is unchanged; only the
  rendered format changes.

- **FR-4**: `read_file` not-found result MUST include a "Did you mean `X`?"
   suggestion when a close match exists in the workspace, where "close" is
   defined as ≤2 path-segment differences from the requested path among the
   set of existing workspace files. When no close match exists, return the
   existing plain not-found message unchanged. The suggestion MUST be a
   workspace-relative path string.

- **FR-5a**: `record_reviewer_decision` MUST raise `ValueError` when
  `approved` is recorded on a task that is PENDING (never dispatched) and
  has no result and no children. The error message MUST name the task and
  instruct the reviewer to review the active task only. The existing
  FR-079 fallback (auto-generate result for IN_PROGRESS tasks with no
  recorded result) remains unchanged. Parent tasks with all children
  completed remain unaffected (the aggregated-result path fires first).
  The `ValueError` propagates to `TaskReviewDecisionTool`, which returns
  `{"success": False, "error": "..."}` to the model — no decision is
  recorded and the task stays PENDING.

- **FR-5b**: `record_result` MUST NOT auto-transition a non-active task
  from PENDING/FAILED to IN_PROGRESS. When the executor records a result
  on a task that is not the current `active_task_id`, the result is
  attached but the status stays PENDING/FAILED — the task must become
  active first. Only the active task is auto-transitioned. This prevents
  out-of-order tasks from being silently advanced to IN_PROGRESS (the
  prerequisite for being skipped to COMPLETED). The executor's
  sibling-propagation feature still works: a result recorded on a
  non-active sibling keeps the sibling PENDING with a result; once the
  sibling becomes active (after the current task is approved),
  `schedule_next` sees the result and skips the executor (review-only).

- **FR-6**: The stream path (`_stream_llm_node_events`) MUST catch provider
  errors (any non-cancel `Exception` raised during `_collect_stream_events`),
  force-compact `session_context`, clear partial stream state
  (`content_parts`, `collected_tool_calls`), and retry the stream up to
  `_MAX_PROVIDER_RETRIES` times. `asyncio.CancelledError` and
  `KeyboardInterrupt` MUST be re-raised immediately without retry. After
  exhaustion, the error event MUST be emitted and the exception re-raised
  (same crash behavior as today, but only after retry attempts). The error
  handler (`_handle_run_exception`) MUST log `repr(exc)` and `exc.__cause__`
  to stderr and the structured log — not just `str(exc)`, which can be
  empty for stream errors.

### Key Entities _(include if feature involves data)_

- **`reviewer_decisions` audit trail** (existing, on `Task`): unchanged in
  shape — still a list of `{decision, rationale, metadata}` dicts. FR-2
  prevents duplicate *in-session* entries; cross-session entries remain
  append-only and ordered.
- **`consecutive_failures` derived property** (existing, on `Task`):
  unchanged — still counts backward until an `approved` or
  `replan_boundary` entry. FR-1 only changes the threshold at which
  `schedule_after_review` routes to replan.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **`replan_threshold` defaults to 3**: constructing
  `WorkerRuntimeController` with no explicit threshold yields `3`.
- [ ] **Single-decision enforced**: a reviewer response with 2
  `task_review_decision` calls is rejected and retried; a response with 1
  call is accepted.
- [ ] **`list_files` renders tree**: output shows grouped directories with
  full relative paths.
- [ ] **`read_file` suggests on not-found**: a wrong-path read with a close
  existing match returns a suggestion; a wrong-path read with no close
  match returns plain not-found.
- [ ] **PENDING tasks cannot be approved**: a PENDING leaf with no result
  rejects `approved` (ValueError); IN_PROGRESS-no-result and
  parent-all-children-done still get the FR-079 fallback.
- [ ] **Non-active tasks don't auto-transition**: `record_result` on a
  non-active PENDING task keeps it PENDING (result attached, status
  unchanged); the active task still auto-transitions to IN_PROGRESS.
- [ ] **Stream errors retry**: a `ProviderApiError` during streaming
  force-compacts and retries up to `_MAX_PROVIDER_RETRIES` times; only
  after exhaustion does the process crash. `CancelledError` is re-raised
  immediately. The error log includes `repr(exc)` and `exc.__cause__`.
- [ ] **No regression on simple tasks**: Experiment-3 and Experiment-5
  patterns (reviewer approves cleanly, 6/6 and 11/11) still pass with the
  new threshold and validator.
- [ ] **Loop count drops on hard tasks**: a re-run of the Experiment-4
  pattern produces fewer review calls per stuck task than the observed 14
  on task `69de662b` (target: ≤6 per stuck task before force-approve).

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_worker_runtime_threshold_default`: assert `replan_threshold == 3`
  on default construction; assert explicit override still wins.
- `test_validate_result_reviewer_single_decision`: two-decision response
  rejected with the named error; one-decision response accepted;
  one-decision + one-`task_update` accepted.
- `test_list_files_tree_format`: assert grouped-by-directory rendering with
  full relative paths; assert empty-workspace case.
- `test_read_file_fuzzy_suggestion`: close-match returns suggestion; no-
  match returns plain not-found; root-not-suggested-as-file case.
- `test_review_pending_guard`: PENDING leaf rejects `approved`; IN_PROGRESS
  no-result still gets FR-079 fallback; parent-all-children-done unaffected;
  `record_result` on non-active task keeps it PENDING; sibling-propagation
  still skips executor when the sibling becomes active.

### Integration Tests

- `test_review_loop_converges_faster`: simulate a stuck task (executor
  always returns a result the reviewer rejects) and assert the runtime
  routes to replan after 3 consecutive failures (not 5), then force-
  approves at the replan cap.
- `test_reviewer_cannot_flip_flop_in_session`: simulate a reviewer response
  with `needs_revision` then `approved` in one session and assert the
  response is rejected, no decision recorded.

### Manual Tests _(if applicable)_

- Re-run Experiment-4 pattern live and confirm the stuck-task review count
  drops from the observed 14 toward the ≤6 target.
- Spot-check Experiment-2 `report.md` sourcing to confirm whether the
  trade-off noted in the Problem Statement is acceptable or needs the
  deferred task-type-aware spec.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| FR-1 threshold default | TODO | one-line change in `worker_runtime.py` |
| FR-2 single-decision validator | TODO | new validator in `validation_retry_mixin.py` |
| FR-3 list_files tree format | TODO | formatter change in `files.py` |
| FR-4 read_file fuzzy suggestion | TODO | not-found path in `files.py` |
| FR-5 prevent task skipping | TODO | guards in `task.py` |
| FR-6 stream-path provider retry | TODO | except block in `orchestration_mixin.py` + logging in `run.py` |

---

## Open Questions _(optional)_

1. **Is ≤2 path-segment differences the right "close match" threshold for
   FR-4?**
   - **Owner**: @VJyzCELERY
   - **Status**: Proposed
   - **Proposed Answer**: Yes — matches the observed Exp4 cases (one
     missing/extra directory segment). Tune during implementation if it
     over- or under-suggests.

2. **Should FR-3's tree format include file sizes or just paths?**
   - **Owner**: @VJyzCELERY
   - **Status**: Proposed
   - **Proposed Answer**: Just paths — sizes were not in the original
     output and adding them widens the model's attention without clear
     benefit.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable

---

## Evidence Appendix

Data from `src/experiment/results/tinycua/` (new run, post-markdown-synthesis
lazy retry was *not* enabled in these runs — `recovery_strategy="standard"`):

- **Exp4 task `69de662b` 14× review**: 11 `needs_revision` + 3 `rejected` +
  1 `replan`, then `replan_budget_exhausted` force-approve. Source:
  `experiment-4/logs/stderr.log` lines 1209, 2357, 2461.
- **10 `read_file` not-found failures** in Exp4 reviewer, each costing 3-5
  extra turns. Sample: reviewer guessed `backend/routing.py` when file was
  at `backend/django_notion_app/channels/routing.py`. Source:
  `experiment-4/logs/stdout.log`.
- **Exp2 task 14 premature completion**: task 14 ("Review and finalize
  report.md") was `[pending]` (stderr.log:637), never dispatched. Reviewer
  called `task_review_decision(approved)` resolving to task 14, not the
  active task 4 (stdout.log:1527). `record_reviewer_decision` FR-079
  fallback created a fake result → COMPLETED (stderr.log:642). Tasks 5-13
  were still pending. Source: `experiment-2/logs/stderr.log` lines 637-657,
  `experiment-2/logs/stdout.log` line 1527.
- **Exp2 sourcing regression**: old run 20 source links in `report.md`
  (cross-judge 4.6), new run 4 source links (single-judge 3.0). Reviewer
  pressure dropped from 11 `needs_revision` + 1 `rejected` to 2
  `needs_revision`. Source: `experiment-2/workdir/report.md` (both runs) +
  `experiment-2/logs/stdout.log` decision counts.
- **Token shape unchanged**: reviewer + executor = 98.4% of tokens in Exp4
  (6.89M + 5.36M of 12.25M). Input:output ≈ 37:1. The loop is input-bound;
  reducing loop count is the lever.
- **What already works (do not re-fix)**: executor contract gap closed
  (49 starts vs 47 `task_result_update` in Exp4, vs old 77 vs 75). FR-035
  doubled-path stripping works (only 1 slipped through in Exp4). Replan
  cap machinery fires correctly. Exp3 (584→283s) and Exp5 (3004→2409s)
  improved because they don't hit the churn pathology.
- **Exp2/3/5 stream-error crashes**: all three failed with
  `Agent error: [0] OpenAI Chat Completions API stream error:` (empty
  message). Each had exactly 1 stream error that killed the process.
  Zero `provider_error_retry` warnings — the stream path bypasses FR-086
  retry. The error always happened when the reviewer was about to emit a
  `task_review_decision` tool call (heavy generation step). Source:
  `experiment-{2,3,5}/logs/stderr.log` last line,
  `experiment-{2,3,5}/logs/stdout.log` `node-error` line.