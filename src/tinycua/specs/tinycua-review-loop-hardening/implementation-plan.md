# Implementation: TINYCUA Review-Loop Hardening

Four small changes that cut the executor↔reviewer loop count on hard tasks
and the turns the reviewer wastes mis-guessing file paths. Two one-liners
(FR-1, FR-3), one small validator (FR-2), one not-found suggestion path
(FR-4). No new nodes, tools, or mixins.

## Context

- **Spec Reference**: `src/tinycua/specs/tinycua-review-loop-hardening/spec.md`
- **Design Reference**: `src/tinycua/specs/tinycua-review-loop-hardening/design.md`
- **Priority**: P1
- **Estimated Effort**: S

## Environment Pre-requisites

### Configuration

- [ ] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
|- [ ] **None** — no external services needed | | | |

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [ ] **None** — no special access required

### Developer Tooling

- [ ] **Runtime**: Python 3.11, uv
- [ ] **Package manager**: uv
- [ ] **None** — no additional CLI tools required

---

## Success Criteria — Integration Tests (TDD First)

```python
# Test file: src/tinycua/tests/unit/test_worker_runtime_controller.py
# (extend existing file)

def test_replan_threshold_default_is_three():
    """FR-1: default replan_threshold is 3, not 5."""
    store = TaskStateStore()
    ctrl = WorkerRuntimeController(store)
    assert ctrl.replan_threshold == 3

def test_replan_threshold_explicit_override_wins():
    """FR-1: explicit replan_threshold still wins over default."""
    store = TaskStateStore()
    ctrl = WorkerRuntimeController(store, replan_threshold=7)
    assert ctrl.replan_threshold == 7
```

```python
# Test file: src/tinycua/tests/unit/test_review_single_decision.py
# (new file)

class TestSingleDecisionValidator:
    """FR-2: reviewer may emit at most one task_review_decision per session."""

    def test_two_decisions_rejected(self, loop_with_reviewer_node):
        # tool_results with two successful task_review_decision calls
        llm_result = make_llm_result(tool_results=[
            {"name": "task_review_decision", "output": {"success": True, "decision": "needs_revision", "task_id": "t1"}},
            {"name": "task_review_decision", "output": {"success": True, "decision": "approved", "task_id": "t1"}},
        ])
        result = loop._validate_result_reviewer_single_decision(reviewer_node, llm_result)
        assert not result.is_valid
        assert "at most one" in result.errors[0].lower()

    def test_one_decision_accepted(self, loop_with_reviewer_node):
        llm_result = make_llm_result(tool_results=[
            {"name": "task_review_decision", "output": {"success": True, "decision": "approved", "task_id": "t1"}},
        ])
        result = loop._validate_result_reviewer_single_decision(reviewer_node, llm_result)
        assert result.is_valid

    def test_one_decision_plus_task_update_accepted(self, loop_with_reviewer_node):
        # task_update is a different tool — does not count toward the limit
        llm_result = make_llm_result(tool_results=[
            {"name": "task_review_decision", "output": {"success": True, "decision": "approved", "task_id": "t1"}},
            {"name": "task_update", "output": {"success": True, "task_id": "t2"}},
        ])
        result = loop._validate_result_reviewer_single_decision(reviewer_node, llm_result)
        assert result.is_valid

    def test_non_reviewer_node_skipped(self, loop_with_executor_node):
        # validator only applies to result_reviewer
        llm_result = make_llm_result(tool_results=[
            {"name": "task_review_decision", "output": {"success": True}},
            {"name": "task_review_decision", "output": {"success": True}},
        ])
        result = loop._validate_result_reviewer_single_decision(executor_node, llm_result)
        assert result.is_valid

    def test_failed_decision_not_counted(self, loop_with_reviewer_node):
        # success=False decisions don't count — they didn't record state
        llm_result = make_llm_result(tool_results=[
            {"name": "task_review_decision", "output": {"success": False, "error": "bad"}},
            {"name": "task_review_decision", "output": {"success": True, "decision": "approved", "task_id": "t1"}},
        ])
        result = loop._validate_result_reviewer_single_decision(reviewer_node, llm_result)
        assert result.is_valid
```

```python
# Test file: src/tinycua/tests/integration/test_native_tools_files.py
# (extend existing file)

def test_list_files_tree_format_shows_directory_grouping():
    """FR-3: list_files renders grouped by directory with full relative paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "backend").mkdir()
        Path(tmpdir, "backend", "api.py").touch()
        Path(tmpdir, "backend", "views.py").touch()
        Path(tmpdir, "frontend").mkdir()
        Path(tmpdir, "frontend", "index.html").touch()
        from tinycua.agent.tools.native.files import list_files
        # bind workspace so relative paths resolve
        bind_workspace(tmpdir)
        result = list_files(".")
        # Result is a tree-formatted string with directory headers and full
        # relative paths, not a flat bare-name list.
        assert isinstance(result, str)
        assert "backend/" in result
        assert "backend/api.py" in result
        assert "frontend/index.html" in result

def test_list_files_tree_empty_workspace():
    """FR-3: empty workspace returns empty tree, no crash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        from tinycua.agent.tools.native.files import list_files
        result = list_files(".")
        assert isinstance(result, str)

def test_read_file_not_found_with_close_match_returns_suggestion():
    """FR-4: not-found with a close existing match includes a suggestion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "backend").mkdir()
        Path(tmpdir, "backend", "django_notion_app").mkdir()
        Path(tmpdir, "backend", "django_notion_app", "channels").mkdir()
        Path(tmpdir, "backend", "django_notion_app", "channels", "routing.py").touch()
        bind_workspace(tmpdir)
        from tinycua.agent.tools.native.files import read_file
        # Model guesses wrong path (missing the django_notion_app/channels part)
        result = read_file("backend/routing.py")
        assert isinstance(result, dict)
        assert "error" in result
        assert "suggestion" in result
        assert "routing.py" in result["suggestion"]

def test_read_file_not_found_no_close_match_plain_error():
    """FR-4: not-found with no close match returns plain error, no suggestion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "readme.md").touch()
        bind_workspace(tmpdir)
        from tinycua.agent.tools.native.files import read_file
        result = read_file("completely/unrelated/path.xyz")
        assert isinstance(result, dict)
        assert "error" in result
        assert "suggestion" not in result
```

```python
# Test file: src/tinycua/tests/unit/test_auto_replan.py
# (modify existing — update threshold assertions from 5 to 3)

def test_3_consecutive_rejections_trigger_replan():
    # was test_5_consecutive_rejections_trigger_replan
    # 3 rejections now trigger replan (was 5)
    ...

def test_2_consecutive_rejections_still_retry():
    # was test_4_consecutive_rejections_still_retry
    # 2 rejections still retry (was 4)
    ...
```

```python
# Test file: src/tinycua/tests/integration/test_replan_loop_regression.py
# (modify existing — update threshold=5 to threshold=3 where it uses default,
#  or keep explicit threshold=5 where testing explicit-override behavior)

# Where the test exercises DEFAULT threshold behavior:
#   ctrl = WorkerRuntimeController(store, replan_threshold=5, max_replans=3)
# → split into:
#   1. default-threshold test: WorkerRuntimeController(store, max_replans=3) → triggers at 3
#   2. explicit-threshold test: WorkerRuntimeController(store, replan_threshold=5, max_replans=3) → triggers at 5
```

```python
# Test file: src/tinycua/tests/unit/test_worker_runtime_controller.py
# (modify existing — line 31-41 test uses range(3) asserting "retry, not replan"
#  with comment "below the default replan_threshold of 5". At threshold=3, 3
#  rejections now TRIGGER replan, so this breaks. Fix: range(3) -> range(2),
#  update comment to "below the default replan_threshold of 3".)

def test_worker_runtime_repeated_revision_never_routes_to_response():
    ...
    # Use 2 rejections — below the default replan_threshold of 3, so this
    # still routes to executor+reviewer (retry), not replan.
    for _ in range(2):
        store.record_reviewer_decision(active.task_id, ReviewerDecision.NEEDS_REVISION)
    ...
```

```python
# Test file: src/tinycua/tests/unit/test_design_gap_contracts.py
# (modify existing — line 139-147 same pattern as above: range(3) -> range(2),
#  comment "below the default replan_threshold of 5" -> "of 3".)

def test_reviewer_revisions_do_not_escalate_to_response_before_completion() -> None:
    ...
    # Use 2 rejections — below the default replan_threshold of 3, so this
    # still routes to executor+reviewer (retry), not replan.
    for _ in range(2):
        store.record_reviewer_decision(active.task_id, ReviewerDecision.NEEDS_REVISION)
    ...
```

```python
# Test file: src/tinycua/tests/unit/test_result_reviewer_inspect_protocol.py
# (modify existing — line 236-247 uses range(5) + asserts "5 times" in the
#  continuation string. The soft-note trigger (task_nodes.py:818) drops to 3,
#  so this must use range(3) + assert "3 times".)

def test_reviewer_failure_note_at_threshold():
    ...
    # Simulate 3 send-backs (needs_revision) so failure_count == 3.
    for _ in range(3):
        store.record_reviewer_decision(first.task_id, ReviewerDecision.NEEDS_REVISION)
    ...
    assert "3 times" in continuation
```

```python
# Test file: src/tinycua/tests/unit/test_review_single_decision_integration.py
# (new file)

def test_reviewer_cannot_flip_flop_in_session():
    """FR-2 integration: a reviewer response with needs_revision then approved
    in one session is rejected; no decision recorded; node retried."""
    # Build a loop with a reviewer node, feed it a two-decision LLM result,
    # assert the validation fails and the node is retried (not advanced).
```

```python
# Test file: src/tinycua/tests/unit/test_review_pending_guard.py
# (new file — FR-5a + FR-5b)

class TestApprovePendingTaskGuard:
    """FR-5a: approving a never-dispatched task is rejected."""

    def test_approve_pending_leaf_rejected(self):
        # PENDING leaf, no result, no children → ValueError
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        with pytest.raises(ValueError, match="never executed"):
            store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)

    def test_approve_in_progress_no_result_still_works(self):
        # FR-079 case: IN_PROGRESS, no result → fallback fires (unchanged)
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
        assert child.result is not None
        assert child.result.metadata.get("auto_generated") is True
        assert child.status == TaskStatus.COMPLETED

    def test_approve_parent_all_children_done_still_works(self):
        # Parent PENDING, all children COMPLETED → aggregated result (unchanged)
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="done", success=True))
        store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
        store.record_reviewer_decision(root.task_id, ReviewerDecision.APPROVED)
        assert root.result.metadata.get("aggregated") is True
        assert root.status == TaskStatus.COMPLETED

    def test_tool_catches_error_and_returns_failure(self):
        # TaskReviewDecisionTool catches ValueError → success=False
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        tool = TaskReviewDecisionTool()
        tool.bind_task_store(store)
        result = tool(task_id=child.task_id, decision="approved", rationale="x")
        assert result["success"] is False
        assert "never executed" in result["error"]


class TestRecordResultNonActiveGuard:
    """FR-5b: record_result on a non-active task keeps it PENDING/FAILED."""

    def test_record_result_on_non_active_keeps_pending(self):
        # Two tasks; record_result on second (non-active) → stays PENDING, has result
        store = TaskStateStore()
        root = store.create_task("Root")
        first = store.create_task("First", parent_id=root.task_id)
        second = store.create_task("Second", parent_id=root.task_id)
        store.record_result(second.task_id, TaskResult(content="sibling work", success=True))
        assert second.result is not None
        assert second.status == TaskStatus.PENDING  # not auto-transitioned

    def test_record_result_on_active_auto_transitions(self):
        # Active task; record_result → IN_PROGRESS (unchanged)
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="done", success=True))
        assert child.status == TaskStatus.IN_PROGRESS

    def test_executor_sibling_propagation_still_works(self):
        # record_result on sibling (non-active) → PENDING + result;
        # after active approved, sibling becomes active;
        # schedule_next returns ["result_reviewer"] (skip executor)
        store = TaskStateStore()
        root = store.create_task("Root")
        first = store.create_task("First", parent_id=root.task_id)
        second = store.create_task("Second", parent_id=root.task_id)
        store.record_result(first.task_id, TaskResult(content="did both", success=True))
        store.record_result(second.task_id, TaskResult(content="part of task 1", success=True))
        store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)
        # second is now active, has result, PENDING
        queue = NodeQueue()
        WorkerRuntimeController(store).schedule_next(queue)
        ids = [n.node_id for n in queue.items]
        assert ids == ["result_reviewer"]  # no executor — work already done
```

### Key Test Scenarios

- [ ] **Scenario 1**: `replan_threshold` defaults to 3 (FR-1)
- [ ] **Scenario 2**: reviewer with 2 `task_review_decision` calls is rejected (FR-2)
- [ ] **Scenario 3**: `list_files` shows directory-grouped tree with full paths (FR-3)
- [ ] **Scenario 4**: `read_file` not-found with close match returns suggestion (FR-4)
- [ ] **Scenario 5**: `read_file` not-found with no close match returns plain error (FR-4)
- [ ] **Scenario 6**: PENDING leaf + approved → ValueError, stays PENDING (FR-5a)
- [ ] **Scenario 7**: `record_result` on non-active task → stays PENDING with result (FR-5b)
- [ ] **Edge case**: one decision + one `task_update` accepted (FR-2)
- [ ] **Edge case**: empty workspace `list_files` doesn't crash (FR-3)
- [ ] **Edge case**: IN_PROGRESS no-result still gets FR-079 fallback (FR-5a)
- [ ] **Edge case**: parent-all-children-done still gets aggregated result (FR-5a)
- [ ] **Edge case**: executor sibling-propagation still skips executor (FR-5b)

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for the single-decision validator — error message, non-reviewer skip, failed-decision exclusion
- [ ] Unit tests for FR-5 pending-guard — PENDING leaf rejected, IN_PROGRESS no-result works, parent works, tool catches error, non-active record_result keeps PENDING, sibling-propagation works
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`
- [ ] Updated auto_replan tests — threshold 3 behavior
- [ ] Updated list_files tests — tree format + existing pattern/path tests still pass

### Manual Verification

- [ ] Spot-check that the single-decision error message is actionable for the model
- [ ] Confirm `list_files` tree output is readable by a human (proxy for model readability)

### Performance Considerations

- [ ] None — these changes reduce LLM call volume; no throughput-sensitive code added

## Proposed Changes

### FR-1 — replan_threshold default (5 places, all 5→3)

The threshold `5` is hardcoded in **five** places. The runtime path is
`task_nodes.py:910` reads `SessionConfig.replan_threshold` → passes it
explicitly into `WorkerRuntimeController(replan_threshold=...)`, so changing
only the controller default (#1) is **silently ineffective in production** —
the session-config default (#2) overrides it. All five must agree.

#### MODIFY `src/tinycua/tinycua/loops/worker_runtime.py:55`
- **Change `replan_threshold: int = 5` → `3`** (dataclass default).

#### MODIFY `src/tinycua/tinycua/config/session_config.py:77`
- **Change `replan_threshold: int = 5` → `3`** (SessionConfig default; update the docstring comment "Default 5" → "Default 3").
- This is the value the live runtime actually reads via `task_nodes.py:910`.

#### MODIFY `src/tinycua/tinycua/loops/task_nodes.py:910`
- **Change `replan_threshold = sc.replan_threshold if sc is not None else 5` → `else 3`** (fallback when session_config is None).

#### MODIFY `src/tinycua/tinycua/loops/task_nodes.py:818`
- **Change `if failure_count >= 5:` → `>= 3`** (soft replan-hint note trigger).
- Aligns the reviewer's "consider replan" soft note with the actual trigger so the hint doesn't lag the action.

#### MODIFY `src/tinycua/tinycua/cli/run.py:215`
- **Change `replan_threshold=... if ... is not None else 5` → `else 3`** (CLI fallback).

**Rationale**: Exp4 task `69de662b` burned 14 review calls cycling through
5-consecutive-failure × 3 replan caps; the model rarely recovers by retry
4-5. Lowering to 3 cuts the worst-case review count per stuck task roughly in
half. **No control-flow change**: `schedule_after_review`, `schedule_replan`,
`_force_approve_at_cap` all unchanged — only the trigger threshold moves.

### FR-2 — single-decision validator

#### NEW validator in `src/tinycua/tinycua/loops/validation_retry_mixin.py`

- **Add `_validate_result_reviewer_single_decision`**: counts successful `task_review_decision` calls in `llm_result.metadata["tool_results"]`; if >1, returns `ValidationResult(is_valid=False)` with error `"ResultReviewer may emit at most one task_review_decision per session. To overturn a prior decision, terminate and start a new review session."`.
- **Wire into the chain**: add to the tuple in `_validate_node_result` (line ~415-428), after `_validate_result_reviewer_inspects_after_decision`.
- **Rationale**: kills in-session flip-flopping (`needs_revision` → `approved` → `needs_revision`) observed in the old Exp4 logs. Cross-session supersession is already handled by append-order in `reviewer_decisions`; no new schema field needed.

### FR-3 — list_files tree format

#### MODIFY `src/tinycua/tinycua/agent/tools/native/files.py`

- **Change `list_files` to return a tree-formatted string**: group entries by directory, show full workspace-relative paths, indent files under their directory headers. Example output:
  ```
  backend/
    backend/api.py
    backend/views.py
  frontend/
    frontend/index.html
  manage.py
  ```
- **Rationale**: a flat list of 41 paths (Exp4) gives the model no structural cue, so it guesses `backend/routing.py` when the file is at `backend/django_notion_app/channels/routing.py`. A grouped tree makes the nesting visible.
- **Return type change**: `list[str]` → `str`. This is a contract change; update affected tests in `test_native_tools_files.py` (the `isinstance(result, list)` assertions become `isinstance(result, str)`).
- **Design note**: the design doc said "keeps returning a list[str]" but that was contradictory with "renders the tree as a grouped string". Resolved here: return a single tree-formatted string. Simpler for the model to parse, one return type.

### FR-4 — read_file fuzzy suggestion

#### MODIFY `src/tinycua/tinycua/agent/tools/native/files.py`

- **Add closest-match computation in `_read_lines` not-found path**: when a file is not found, enumerate existing workspace files (via a recursive walk of the workspace root), compute path-segment edit distance against the requested path, and if the best match is within ≤2 segment differences, add a `"suggestion"` key to the error dict with the closest workspace-relative path.
- **Rationale**: the reviewer wasted 3-5 turns per wrong-path read in Exp4 re-listing, re-reading, re-reasoning. A "Did you mean `X`?" suggestion teaches the model the right path for the rest of the session in one turn.
- **Algorithm**: split both requested and candidate paths into segments; segment edit distance = number of segment insertions/deletions to transform one into the other. Only suggest when distance ≤2. Omit `suggestion` key when no close match (plain not-found unchanged).
- **Implementation helper**: add a small `_suggest_closest_path(requested_rel: str, workspace: Path) -> str | None` function in `files.py`.

### FR-5 — prevent completing/updating out-of-order tasks

#### MODIFY `src/tinycua/tinycua/models/task.py`

**FR-5a — `record_reviewer_decision` guard (APPROVED branch, ~line 534):**

Insert before the final FR-079 fallback (`if task.result is None:` that creates the auto-generated result), after the children-aggregated block:

```python
    # FR-5a: do not auto-generate a result for a leaf task that was never
    # dispatched (PENDING, no result, no children). The FR-079 fallback
    # below is for IN_PROGRESS tasks whose executor forgot
    # task_result_update — not for PENDING tasks the reviewer approved
    # by mistake (e.g. approving a sibling that was never executed).
    if task.result is None and task.status == TaskStatus.PENDING:
        raise ValueError(
            "Cannot approve a task that was never executed "
            f"(task_id={task_id}, status=pending, no result). Review the "
            "active task only; do not approve tasks that have not been "
            "dispatched."
        )
```

The `ValueError` propagates to `TaskReviewDecisionTool.__call__` (task_tools.py:608), which catches it and returns `{"success": False, "error": "..."}` to the model.

**FR-5b — `record_result` guard (line 479-480):**

Current:
```python
if task.status in {TaskStatus.PENDING, TaskStatus.FAILED}:
    self.transition(task_id, TaskStatus.IN_PROGRESS)
```

Change to:
```python
# FR-5b: only auto-transition the ACTIVE task to IN_PROGRESS. A non-active
# (out-of-order) task stays PENDING/FAILED even if a result is recorded —
# it must become active first. Prevents task skipping: the executor can
# record a result on a sibling ("completed as part of task N") but the
# sibling's status doesn't advance until the runtime dispatches it.
if task.status in {TaskStatus.PENDING, TaskStatus.FAILED}:
    if task_id == self.active_task_id:
        self.transition(task_id, TaskStatus.IN_PROGRESS)
```

- **Rationale**: Exp2 task 14 was completed by a reviewer approving a never-dispatched PENDING sibling. The consistency principle: PENDING is not advanced unless the task went through IN_PROGRESS, and only the active task auto-transitions.
- **No change to `TaskUpdateTool`**: the analyzer can modify any non-completed task (planning). FR-5b only gates `record_result`.
- **No change to `record_reviewer_decision`'s NEEDS_REVISION/REJECTED/REPLAN branch** (line 510-513): those set the task to IN_PROGRESS and make it active, which is correct (rework → task is active again).

#### MODIFY `src/tinycua/tests/unit/test_experiment_bugfixes.py`

**Update `test_leaf_task_auto_generates_result` (line 14-21):** add `store.transition(child.task_id, TaskStatus.IN_PROGRESS)` before the approve call. The test currently encodes the bug (approving a never-dispatched PENDING leaf); after the guard, it must simulate the executor having picked up the task.

#### NEW `src/tinycua/tests/unit/test_review_pending_guard.py`

7 test cases (see Testing Plan section for snippets).

### FR-6 — stream-path provider-error retry + error logging

#### MODIFY `src/tinycua/tinycua/loops/orchestration_mixin.py`

**Restructure the except block in `_stream_llm_node_events` (~line 877-904):**

Current (crash on first error):
```python
content_parts: list[str] = []
collected_tool_calls: list[dict[str, Any]] = []
try:
    async for event in self._collect_stream_events(...):
        yield event
except Exception:
    error_event = self._make_error_event(...)
    yield self._enrich_and_yield(error_event, ...)
    raise
```

Change to (retry with compaction):
```python
content_parts: list[str] = []
collected_tool_calls: list[dict[str, Any]] = []
provider_retries = 0  # FR-6: stream-path provider-error retry counter
while True:
    try:
        async for event in self._collect_stream_events(
            node, agent, attempt_messages, attempt_tools,
            content_parts, collected_tool_calls,
            include_meta, final_only, node_type, attempt_number,
        ):
            yield event
        break  # stream completed — exit retry loop
    except (asyncio.CancelledError, KeyboardInterrupt):
        raise
    except Exception as exc:
        provider_retries += 1
        if provider_retries > _MAX_PROVIDER_RETRIES:
            error_event = self._make_error_event(
                node.node_id, node_type, attempt_number,
            )
            yield self._enrich_and_yield(
                error_event, include_meta,
                node.node_id, node_type, attempt_number,
            )
            raise
        # FR-6: force-compact, clear partial stream state, retry.
        logger.warning(
            "stream_provider_error_retry node=%s attempt=%d retry=%d "
            "error=%s — forcing compaction",
            node.node_id, attempt_number, provider_retries,
            repr(exc)[:200],
        )
        await self._force_compact(node, agent)
        content_parts.clear()
        collected_tool_calls.clear()
        attempt_messages = self._messages_with_retry_prompt(
            base_messages, retry_feedback, retry_message,
        )
        # Loop back — retry the stream.
```

**Add imports** (top of file):
```python
import asyncio
from tinycua.loops._loop_constants import _MAX_PROVIDER_RETRIES
```

#### MODIFY `src/tinycua/tinycua/cli/run.py`

**Improve error logging in `_handle_run_exception` (~line 286-288):**

```python
# FR-6: log full exception detail (str(exc) can be empty for stream errors).
cause = exc.__cause__ or exc.__context__
cause_repr = repr(cause) if cause else "none"
if log_path:
    write_log_entry(log_path, "error", "error", {
        "error": str(exc), "error_type": type(exc).__name__,
        "error_repr": repr(exc)[:500],
        "cause": cause_repr[:500],
        "elapsed": elapsed,
    })
print(f"Agent error: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
if cause:
    print(f"  caused by: {cause_repr[:300]}", file=sys.stderr, flush=True)
```

#### NEW `src/tinycua/tests/unit/test_stream_provider_retry.py`

3 test cases (see Testing Plan section for snippets).

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `WorkerRuntimeController` | Modify | `replan_threshold` default 5 → 3 |
| `SessionConfig` | Modify | `replan_threshold` default 5 → 3 (the value the live runtime reads) |
| `task_nodes.py` | Modify | replan_threshold fallback `else 5` → `else 3`; soft-note trigger `>= 5` → `>= 3` |
| `cli/run.py` | Modify | CLI fallback `else 5` → `else 3` |
| `validation_retry_mixin` | Modify | New `_validate_result_reviewer_single_decision` validator added to chain |
| `files.list_files` | Modify | Return tree-formatted string instead of flat list |
| `files._read_lines` / `files._suggest_closest_path` | Modify/New | Fuzzy closest-match suggestion on not-found |
| `task.py record_reviewer_decision` | Modify | FR-5a: raise ValueError on APPROVED for PENDING leaf with no result |
| `task.py record_result` | Modify | FR-5b: only auto-transition active task PENDING/FAILED → IN_PROGRESS |
| `orchestration_mixin._stream_llm_node_events` | Modify | FR-6: restructure except block to retry on provider errors with compaction |
| `cli/run._handle_run_exception` | Modify | FR-6: log `repr(exc)` and `exc.__cause__` |

## Data Model Changes

```python
# No new types. One return-shape change:
# list_files: list[str] → str  (tree-formatted)
# read_file not-found: {"error": "..."} → {"error": "...", "suggestion": "<rel>"}  (suggestion optional)
```

## API Changes

### New Endpoints

None.

### Modified Endpoints

| Method | Path | Change |
|--------|------|--------|
| `list_files` | tool | Return type `list[str]` → `str` (tree-formatted) |
| `read_file` | tool | Not-found error dict gains optional `suggestion` key |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none — uses stdlib only: `difflib` or manual segment distance) | | |

### Internal Dependencies

- [ ] No dependencies on other implementations
- [ ] Blocks: the deferred task-type-aware threshold spec (separate future PR)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Lower threshold increases force-approves of imperfect tasks (Exp2 trade-off) | Medium | Accept for hard code tasks; watch Exp2 pattern on re-run; task-type-aware thresholds deferred to separate spec |
| Single-decision validator costs one extra session in rare legit overturn | Low | Acceptable — one cheap session << flip-flop churn it prevents |
| `list_files` return-type change breaks consumers expecting a list | Medium | Grep all call sites; update tests; the SDK serializes the tool result to the model as a string anyway |
| Fuzzy suggestion misleads when closest match is wrong | Low | Only suggest ≤2 segment distance; omit suggestion otherwise; never auto-redirect reads |
| Existing `test_auto_replan` asserts threshold-5 behavior | Low | Update tests in same PR — intentional default change |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-26*