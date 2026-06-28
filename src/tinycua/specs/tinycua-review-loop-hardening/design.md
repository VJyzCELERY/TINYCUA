# Design Document: TINYCUA Review-Loop Hardening

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-25

---

## Overview

Four small, mostly-independent changes to tinycua's worker-mode runtime that
together cut the executor↔reviewer loop count on hard tasks and the turns the
reviewer wastes mis-guessing file paths. No new nodes, no new tools, no new
mixins. Two changes are one-liners (threshold default, list_files formatter);
one is a small new validator (single-decision); one is a not-found suggestion
path. All preserve the existing replan/force-approve cap machinery and the
zero-exit guarantee.

---

## Architecture

### Component Overview

```
                        ┌─────────────────────────────┐
                        │  WorkerRuntimeController     │
                        │  replan_threshold: 5 → 3     │  FR-1
                        │  (control flow unchanged)   │
                        └──────────────┬──────────────┘
                                       │ schedule_after_review
                                       ▼
   ┌──────────────┐    tool_results    ┌──────────────────────┐
   │ TaskExecutor │ ◄─────────────────► │   ResultReviewer     │
   └──────────────┘                    │  ─ validation chain ─│
                                       │  ─ single-decision ──│  FR-2
                                       │    validator (new)   │
                                       └──────────┬───────────┘
                                                  │ uses
                                  ┌───────────────┴───────────────┐
                                  ▼                               ▼
                          ┌───────────────┐               ┌───────────────┐
                          │  list_files   │               │   read_file   │
                          │ tree format   │               │ fuzzy suggest │
                          │ (formatter)   │               │ (not-found)   │
                          └───────────────┘               └───────────────┘
                                          FR-3                     FR-4
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops.worker_runtime.WorkerRuntimeController` | Modified | `replan_threshold` default `5` → `3`. Control flow untouched. |
| `tinycua.loops.validation_retry_mixin` | Modified | New `_validate_result_reviewer_single_decision` validator added to the chain. |
| `tinycua.agent.tools.native.files.list_files` | Modified | Render result as a grouped/tree string instead of a flat list. |
| `tinycua.agent.tools.native.files.read_file` | Modified | Not-found path computes and returns a closest-match suggestion. |
| `tinycua.agent.tools.native.context` | Unchanged | `resolve_workspace_path` already handles doubled-prefix/re-rooting; no change. |
| `tinycua.models.task.TaskStateStore.record_reviewer_decision` | Modified | FR-5a: raise `ValueError` on `approved` for PENDING leaf with no result/no children. |
| `tinycua.models.task.TaskStateStore.record_result` | Modified | FR-5b: only auto-transition the active task PENDING/FAILED → IN_PROGRESS; non-active tasks keep their status. |
| `tinycua.loops.orchestration_mixin._stream_llm_node_events` | Modified | FR-6: restructure except block to catch provider errors, force-compact, clear partial state, and retry. |
| `tinycua.cli.run._handle_run_exception` | Modified | FR-6: log `repr(exc)` and `exc.__cause__` instead of just `str(exc)`. |

---

## Data Model

### New Entities _(if applicable)_

None. No new data shapes.

### Schema Changes _(if applicable)_

None. `reviewer_decisions` stays a list of `{decision, rationale, metadata}`
dicts; `consecutive_failures` stays a derived property. FR-2 prevents
duplicate *in-session* entries by rejecting the response before any decision
is recorded — no schema change needed.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
# FR-1 — worker_runtime.py
@dataclass
class WorkerRuntimeController:
    replan_threshold: int = 3   # was 5
    # all other fields and methods unchanged
```

```python
# FR-2 — validation_retry_mixin.py (new validator, added to the chain)
def _validate_result_reviewer_single_decision(
    self,
    node: Node,
    llm_result: LLMResult,
) -> ValidationResult:
    """Reject a reviewer session that emits more than one task_review_decision.

    The decision sticks once a single-decision response passes; to overturn
    a prior decision the reviewer must terminate and open a new session
    (the new decision appends later in reviewer_decisions, superseding by
    order). No supersession metadata.
    """
    # count successful task_review_decision calls in tool_results;
    # if >1, return invalid with the named error
```

```python
# FR-3 — files.py list_files (return shape changes)
# Before: returns list[str]  (flat list of relative paths)
# After:  returns list[str]  (still a list, but entries grouped/indented
#         by directory when rendered as a single string block)
#
# Contract: callers that expect a list still get one; the grouping is in
# the *rendering* (newline-joined tree string) so the model sees structure.
```

```python
# FR-4 — files.py read_file not-found path
# Before: {"error": f"File not found: {path}"}
# After:  {"error": f"File not found: {path}",
#          "suggestion": "backend/django_notion_app/channels/routing.py"}
#         (suggestion key omitted when no close match)
```

```python
# FR-5a — task.py record_reviewer_decision (APPROVED branch, before the
#         final FR-079 fallback)
# Guard: if task.result is None and task.status == PENDING:
#            raise ValueError("Cannot approve a task that was never executed ...")
# The ValueError propagates to TaskReviewDecisionTool.__call__, which
# catches it and returns {"success": False, "error": "..."} to the model.
# IN_PROGRESS-no-result (FR-079 case) and parent-all-children-done are
# unaffected — the guard fires only when result is None AND status is PENDING.
```

```python
# FR-5b — task.py record_result (auto-transition guard)
# Before: if task.status in {PENDING, FAILED}: self.transition(IN_PROGRESS)
# After:  if task.status in {PENDING, FAILED}:
#             if task_id == self.active_task_id:
#                 self.transition(IN_PROGRESS)
#             # else: result recorded, status stays PENDING/FAILED
# Only the active task auto-transitions. Non-active tasks (executor
# sibling-propagation) keep their status — they become active later.
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Reviewer emits 2 decisions in one session | `ValidationResult(is_valid=False, errors=["ResultReviewer may emit at most one task_review_decision per session. To overturn a prior decision, terminate and start a new review session."])` | Node retried; no decision recorded. |
| `read_file` no close match | `{"error": "File not found: {path}"}` (no `suggestion` key) | Same as today. |
| `read_file` close match found | `{"error": "...", "suggestion": "<rel>"}` | Extra key; consumers ignoring unknown keys are unaffected. |
| `list_files` empty workspace | `[]` or empty tree string | No crash. |
| Reviewer approves PENDING leaf (no result, no children) | `ValueError("Cannot approve a task that was never executed ...")` → `TaskReviewDecisionTool` returns `{"success": False, "error": "..."}` | Task stays PENDING; no fake result. |
| `record_result` on non-active PENDING task | Result attached, status stays PENDING | New legal state: PENDING + has_result. `schedule_next` checks `result is not None`, not `status == IN_PROGRESS`. |
| Stream-path `ProviderApiError` (SSE dropped) | Catch → force-compact → clear partial state → retry (up to `_MAX_PROVIDER_RETRIES=3`) | After exhaustion: emit error event + re-raise (same crash behavior as today). `CancelledError` re-raised immediately. |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] FR-1: change `replan_threshold` default to `3` in `worker_runtime.py`.
- [ ] FR-2: add `_validate_result_reviewer_single_decision` and wire it into
  the result_reviewer validation chain.
- [ ] FR-3: change `list_files` rendering to grouped tree with full relative
  paths.
- [ ] FR-4: add closest-match suggestion to `read_file` not-found path.
- [ ] FR-5a: add PENDING-leaf approval guard in `record_reviewer_decision`.
- [ ] FR-5b: gate `record_result` auto-transition to the active task only.
- [ ] FR-6: restructure except block in `_stream_llm_node_events` + improve error logging in `_handle_run_exception`.
- [ ] Unit tests for all (per spec Testing Plan).
- [ ] Integration tests: loop-convergence and no-flip-flop.

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

None. All deferred items (task-type-aware thresholds, Exp2 quality) are
explicitly out of scope and belong to a separate future spec.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Lower `replan_threshold` default rather than add a hard total
   review-call cap.
   - **Reason**: The hard cap was rejected during planning (over-specifies
     the budget). The existing replan-budget cap (`max_replans`, default 3)
     already bounds the total; lowering the consecutive-failure threshold
     just makes it converge faster. Simpler, fewer moving parts.
   - **Alternatives Considered**: Hard total cap on
     `task_review_decision` calls per task — rejected as redundant with the
     existing `max_replans` cap and more brittle.

2. **Decision**: Enforce single-decision *per session* via a validator, with
   no supersession metadata across sessions.
   - **Reason**: Cross-session supersession is handled by append-order in
     `reviewer_decisions` already (later decision wins by virtue of being
     last). The only disease is *in-session* flip-flopping, which a validator
     kills without new schema fields.
   - **Alternatives Considered**: Explicit `supersedes` field on decisions —
     rejected as too much machinery for the observed gain.

3. **Decision**: `list_files` keeps returning a `list[str]` but renders the
   tree as a grouped string.
   - **Reason**: Callers expecting a list still get one; the model sees
     structure in the rendered tool result. Avoids a return-type break.
   - **Alternatives Considered**: Return a nested dict — rejected as a
     serialization/format change with no model benefit.

4. **Decision**: Fuzzy suggestion via path-segment edit distance over the
   existing `list_files` result set, not a fuzzy-string library.
   - **Reason**: The observed failures are missing/extra directory segments,
     not typos. Segment-level matching catches exactly those; Levenshtein on
   raw strings would over-suggest on long basenames.
    - **Alternatives Considered**: `difflib.get_close_matches` on full paths —
      rejected as likely to suggest unrelated files with similar basenames.

5. **Decision**: Guard `record_reviewer_decision` (reject APPROVED on
   PENDING leaf with no result) and gate `record_result` auto-transition
   to the active task only.
   - **Reason**: Exp2 task 14 was completed by a reviewer approving a
     never-dispatched PENDING sibling. The FR-079 fallback (meant for
     IN_PROGRESS tasks whose executor forgot `task_result_update`) created
     a fake result. The consistency principle: PENDING is not advanced
     unless the task went through IN_PROGRESS, and only the active task
     is auto-transitioned. The analyzer can still modify any non-completed
     task via `task_update` (planning); the executor's sibling-propagation
     (`task_result_update` on a non-active sibling) still records a result
     but the sibling stays PENDING until it becomes active.
   - **Alternatives Considered**: Guard `TaskUpdateTool` to block status
     changes on non-active tasks — rejected as out of scope (the analyzer
     legitimately modifies non-active tasks during planning; the reviewer's
     `task_update` status-flip abuse is a separate, lesser concern that
     didn't cause the task-skipping bug). Guard at the `_ALLOWED_TRANSITIONS`
     level — rejected as too broad (PENDING → IN_PROGRESS is a valid
      transition that the executor needs).

6. **Decision**: Restructure the except block in `_stream_llm_node_events`
   to catch provider errors, force-compact, clear partial stream state,
   and retry (up to `_MAX_PROVIDER_RETRIES`).
   - **Reason**: the stream path (which tinycua always uses — even
     `stream=False` internally drains a stream) calls `_call_agent_llm`
     directly in `_collect_stream_events` with no retry wrapper. The sync
     path has `_call_llm_with_provider_retry` (FR-086); the stream path
     does not. A single SSE stream drop from LM Studio crashes the whole
     experiment. Restructuring the except block at the `_stream_llm_node_events`
     level (rather than inside `_collect_stream_events`) lets us clear the
     partial `content_parts`/`collected_tool_calls` and rebuild
     `attempt_messages` after compaction before retrying the stream.
   - **Alternatives Considered**: Wrap `_call_agent_llm` inside
     `_collect_stream_events` — rejected because partial events may have
     already been yielded to the consumer before the error; the retry
     needs to clear stale state at the caller level. Move retry into the
     SDK — rejected because tinycua owns the task-loop retry semantics
     (compaction, attempt messages).

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Lower threshold increases force-approves of imperfect tasks (same trade-off as Exp2 4.6→3.0 sourcing regression) | Med | Med | Accept for hard code tasks; deferred task-type-aware spec can raise the threshold for research/doc tasks. Watch Exp2 pattern on re-run. |
| Single-decision validator costs one extra session in rare legit overturn cases | Low | Low | Acceptable — one extra cheap reviewer session is far cheaper than the in-session flip-flops it prevents. |
| Tree format confuses a model trained on flat lists | Low | Low | Full relative paths are still present; grouping is additive context. Verify on re-run. |
| Fuzzy suggestion misleads when the closest match is wrong | Low | Med | Only suggest when ≤2 segment differences; omit suggestion otherwise (plain not-found). Never auto-redirect reads. |
| Existing tests assert `replan_threshold=5` | Med | Low | Update those tests in the same PR; the default change is intentional, not a silent break. |
| FR-5b introduces PENDING+result state for non-active tasks | Low | Low | `schedule_next` checks `result is not None`, not `status == IN_PROGRESS`; the rollback path handles PENDING explicitly. `test_executor_reports_sibling_result_skips_executor` is the regression guard. |
| FR-5a guard breaks a test that approves a never-dispatched PENDING leaf | Med | Low | `test_experiment_bugfixes.py::test_leaf_task_auto_generates_result` encoded the bug as desired behavior; update it to transition IN_PROGRESS first (simulating executor pickup). |
| FR-6 stream retry clears partial events already yielded to consumer | Low | Low | The partial data is garbage (stream was incomplete); clearing prevents stale content. Consumer sees a brief pause in events, then stream restarts. |
| FR-6 retry with compaction is unnecessary for pure network drops | Low | Low | Compaction is cheap (no-op when no strategy or too few entries); consistent with sync path. Skip-compact-on-first-retry adds complexity for marginal gain. |

---

## Open Questions _(optional)_

1. **Exact "close match" metric for FR-4**: segment-edit-distance ≤2 vs. a
   simpler "shares the basename and ≥1 ancestor dir" heuristic. Decide
   during implementation against the Exp4 sample paths.
   - **Current thinking**: segment edit distance — general and tunable.

2. **Whether to also surface the workspace root in the reviewer's system
   prompt once (to stop `/workspace/experiment-4/...` prefix guessing).**
   Not strictly required if FR-3's tree output makes paths obvious, but
   cheap and complementary.
   - **Current thinking**: defer unless re-run still shows prefix guessing.

---

## References

- Spec: `./spec.md`
- Evidence source: `src/experiment/results/tinycua/` (new run, standard
  recovery strategy)
- Earlier related spec (different scope, tool-output truncation + prompt
  cache): `../tinycua-runtime-performance-hardening/spec.md`
- Earlier related spec (markdown-synthesis lazy retry, already merged):
  `../tinycua-finalize-prototype-runtime/spec.md`
- Key code: `src/tinycua/tinycua/loops/worker_runtime.py` (FR-1),
  `src/tinycua/tinycua/loops/validation_retry_mixin.py` (FR-2),
  `src/tinycua/tinycua/agent/tools/native/files.py` (FR-3, FR-4),
  `src/tinycua/tinycua/models/task.py` (FR-5a, FR-5b),
  `src/tinycua/tinycua/loops/orchestration_mixin.py` (FR-6),
  `src/tinycua/tinycua/cli/run.py` (FR-6),
  `src/tinycua/tinycua/agent/tools/native/context.py` (unchanged,
  referenced for path resolution)