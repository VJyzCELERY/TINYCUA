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

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Reviewer emits 2 decisions in one session | `ValidationResult(is_valid=False, errors=["ResultReviewer may emit at most one task_review_decision per session. To overturn a prior decision, terminate and start a new review session."])` | Node retried; no decision recorded. |
| `read_file` no close match | `{"error": "File not found: {path}"}` (no `suggestion` key) | Same as today. |
| `read_file` close match found | `{"error": "...", "suggestion": "<rel>"}` | Extra key; consumers ignoring unknown keys are unaffected. |
| `list_files` empty workspace | `[]` or empty tree string | No crash. |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] FR-1: change `replan_threshold` default to `3` in `worker_runtime.py`.
- [ ] FR-2: add `_validate_result_reviewer_single_decision` and wire it into
  the result_reviewer validation chain.
- [ ] FR-3: change `list_files` rendering to grouped tree with full relative
  paths.
- [ ] FR-4: add closest-match suggestion to `read_file` not-found path.
- [ ] Unit tests for all four (per spec Testing Plan).
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

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Lower threshold increases force-approves of imperfect tasks (same trade-off as Exp2 4.6→3.0 sourcing regression) | Med | Med | Accept for hard code tasks; deferred task-type-aware spec can raise the threshold for research/doc tasks. Watch Exp2 pattern on re-run. |
| Single-decision validator costs one extra session in rare legit overturn cases | Low | Low | Acceptable — one extra cheap reviewer session is far cheaper than the in-session flip-flops it prevents. |
| Tree format confuses a model trained on flat lists | Low | Low | Full relative paths are still present; grouping is additive context. Verify on re-run. |
| Fuzzy suggestion misleads when the closest match is wrong | Low | Med | Only suggest when ≤2 segment differences; omit suggestion otherwise (plain not-found). Never auto-redirect reads. |
| Existing tests assert `replan_threshold=5` | Med | Low | Update those tests in the same PR; the default change is intentional, not a silent break. |

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
  `src/tinycua/tinycua/agent/tools/native/context.py` (unchanged,
  referenced for path resolution)