# Design Document: Mandatory Passthrough and Continuation Routing

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-11 (review-revision-2)
**Milestone**: 3.3 — Mandatory Passthrough and Continuation Routing

---

## Overview

This design wires the end-to-end `open_question` continuation path: when `ResultReviewer` decides `open_question`, a `MandatoryPassthrough` directive is installed targeting the ResultReviewer's node/session, and the next user input is routed deterministically back to it — bypassing LLM classification. The existing `MandatoryPassthrough` model, `QueryAnalyst.check_mandatory_passthrough()` precheck, and `_execute_decision_node()` passthrough detection already exist. The missing piece is the *installation* of the directive when `open_question` is decided, and the *cleanup* after successful forwarding.

---

## Architecture

### Component Overview

```text
User sends continuation
  │
  ▼
TinyCUALoop.run(agent, messages, ...)
  │  root_session.input_context = messages
  │  + MandatoryPassthrough metadata injected from previous open_question
  │
  ├─ [QUEUE RESTART] If _pending_mandatory_passthrough is set,
  │   ensure QueryAnalyst is at front of the queue so the
  │   passthrough can be detected. (See Queue Restart section.)
  │
  ▼
_execute_decision_node(QueryAnalyst)
  │  _build_query_analyst_input() → NodeInput
  │    metadata["mandatory_passthrough"] = MandatoryPassthrough(...)
  │
  ├─ check_mandatory_passthrough() → valid → PASSTHROUGH route
  │    │  node.on_complete(queue, decision) → route_passthrough (no-op)
  │    │  forward input to target node (ResultReviewer)
  │    │
  │    ▼
  │  ResultReviewer.__call__(input) → receives user's continuation
  │    → re-evaluates with new information
  │
  └─ check_mandatory_passthrough() → stale → fallback to LLM classification
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| tinycua.loops.tinycua_loop | Modified | `_on_reviewer_open_question()` installs MandatoryPassthrough; `_install_mandatory_passthrough()` helper; `_clear_mandatory_passthrough()` after consumption |
| tinycua.loops.query_analyst | No change | Precheck and stale guard already implemented; `route_passthrough()` is a no-op acknowledged by design (see Technical Decision #5) |
| tinycua.loops.result_reviewer | No change | Already calls `loop._on_reviewer_open_question()` — no modification needed |
| tinycua.models.classification | No change | `MandatoryPassthrough` dataclass already exists |

---

## Data Model

### No New Entities

The `MandatoryPassthrough` dataclass already exists in `models/classification.py`:

```python
MandatoryPassthrough:
    target_node_id: str
    target_session_id: str | None = None
    reason: str = ""
    payload: NodeInput | NodePayload | None = None
    allow_query_analyst_restart: bool = True
```

### Storage Mechanism

The `MandatoryPassthrough` directive is stored as a loop-level field (`_pending_mandatory_passthrough`) rather than in `input_context`, because `TinyCUALoop.run()` replaces `root_session.input_context` with incoming messages on every invocation (see `run()` method — the `self.root_session.input_context = list(messages)` assignment). Any directive stored in `input_context` during one `run()` call would be lost before the next `run()` can detect it.

```python
# Stored on TinyCUALoop instance by _on_reviewer_open_question()
self._pending_mandatory_passthrough: MandatoryPassthrough | None = None
```

**Injection point:** In `_execute_decision_node()`, after building the QueryAnalyst input via `_build_query_analyst_input()`, the loop injects `self._pending_mandatory_passthrough` into the input metadata before the precheck runs:

```python
input_data = self._build_query_analyst_input()
if self._pending_mandatory_passthrough is not None:
    input_data.metadata["mandatory_passthrough"] = self._pending_mandatory_passthrough
mandatory = node.check_mandatory_passthrough(input_data)
```

**Why not input_context?** `_build_query_analyst_input()` extracts metadata from `root_session.input_context` messages — this is correct for the message pipeline and still happens. But the passthrough directive itself must survive the `input_context` reset between `run()` calls, which requires a persistent field on the loop. The injection in `_execute_decision_node()` is a single additional line that merges the pending directive into the same `NodeInput.metadata` dict where `check_mandatory_passthrough()` already reads from.

---

### Queue Restart for Passthrough Detection

**Problem:** The `NodeQueue` uses `items[0]` as the "current" node and never rewinds. After a `run()` call where `open_question` fires, the queue has advanced past `QueryAnalyst` (it has been popped by `advance()`). On the next `run()` call, the loop starts from whatever node is at `items[0]` — typically the terminal `ResponseNode`. Since `_execute_decision_node()` is only called for `DecisionNode` subclasses (i.e., `QueryAnalyst`), the pending `MandatoryPassthrough` injected in `_execute_decision_node()` is **never reached**.

**Solution:** At the start of `run()`, before the main execution loop, check if `_pending_mandatory_passthrough` is set. If so, ensure `QueryAnalyst` is at the front of the queue so the passthrough detection path is visited:

```python
async def run(self, agent, messages, ...):
    self.root_session.input_context = list(messages)

    # FR-001/FR-003: If a passthrough is pending from a previous open_question,
    # ensure QueryAnalyst is at the front of the queue so _execute_decision_node()
    # can inject the directive into the input metadata and detect it.
    if self._pending_mandatory_passthrough is not None:
        self._ensure_query_analyst_at_front()

    if self.default_terminal_node is not None:
        self.queue.ensure_terminal(self.default_terminal_node)
    ...
```

The helper method `_ensure_query_analyst_at_front()`:

```python
def _ensure_query_analyst_at_front(self) -> None:
    """Ensure QueryAnalyst is at the front of the queue for passthrough detection.

    If QueryAnalyst is already at items[0], this is a no-op.
    If QueryAnalyst exists elsewhere in the queue, it is moved to the front.
    If QueryAnalyst has been popped (not in the queue), a new instance is created
    and prepended. This is safe because QueryAnalyst's session is attached lazily
    by ensure_session() during _execute_decision_node().
    """
    # Already at front — nothing to do
    if self.queue.items and isinstance(self.queue.items[0], TinyCUAQueryAnalystNode):
        return

    # Try to find existing QueryAnalyst further back in the queue
    qa: TinyCUAQueryAnalystNode | None = None
    for i, node in enumerate(self.queue.items):
        if isinstance(node, TinyCUAQueryAnalystNode):
            qa = self.queue.items.pop(i)
            break

    # Not found — create a fresh instance (session attached lazily later)
    if qa is None:
        qa = TinyCUAQueryAnalystNode()

    # Prepend to front
    self.queue.items.insert(0, qa)
```

This ensures the `_execute_decision_node()` passthrough injection is always reachable when a continuation follows an `open_question` decision.

---

## API / Interface Contracts

### Modified Functions

```python
def _on_reviewer_open_question(self, active_task: Task) -> None:
    """Install MandatoryPassthrough targeting ResultReviewer for open_question.

    Creates a MandatoryPassthrough directive and stores it on the loop
    so the next user continuation is routed deterministically to the
    ResultReviewer.

    Args:
        active_task: The task with an open question.
    """
    if active_task is None:
        logger.warning("Cannot install passthrough: no active task")
        return
    # Find the ResultReviewer node in the queue to get its session_id
    reviewer_node = self._find_result_reviewer()
    if reviewer_node is None or reviewer_node.session is None:
        logger.warning("Cannot install passthrough: no active ResultReviewer")
        return

    mandatory = MandatoryPassthrough(
        target_node_id=reviewer_node.node_id,
        target_session_id=reviewer_node.session.session_id,
        reason=f"open_question on task {active_task.task_id}",
        allow_query_analyst_restart=True,
    )
    self._install_mandatory_passthrough(mandatory)
```

```python
def _install_mandatory_passthrough(self, mandatory: MandatoryPassthrough) -> None:
    """Store a MandatoryPassthrough directive on the loop for the next run().

    Persists the directive on the loop so it survives the input_context
    reset at the start of the next run() invocation.

    Args:
        mandatory: The passthrough directive to install.
    """
    # Clear any existing passthrough first (only latest is active)
    self._clear_mandatory_passthrough()
    self._pending_mandatory_passthrough = mandatory
    logger.info(
        "installed_mandatory_passthrough target=%s session=%s reason=%s",
        mandatory.target_node_id,
        mandatory.target_session_id,
        mandatory.reason,
    )
```

```python
def _clear_mandatory_passthrough(self) -> None:
    """Remove the pending MandatoryPassthrough directive from the loop."""
    self._pending_mandatory_passthrough = None
```

```python
def _find_result_reviewer(self) -> Node | None:
    """Find the first active ResultReviewer node in the queue.

    Returns the first TinyCUAResultReviewerNode found by scanning
    queue.items in order. If multiple ResultReviewers exist, only
    the first is targeted. Returns None if no ResultReviewer is in
    the queue.
    """
    for node in self.queue.items:
        if isinstance(node, TinyCUAResultReviewerNode):
            return node
    return None
```

```python
def _ensure_query_analyst_at_front(self) -> None:
    """Ensure QueryAnalyst is at the front of the queue for passthrough detection.

    If QueryAnalyst is already at items[0], this is a no-op.
    If QueryAnalyst exists elsewhere in the queue, it is moved to the front.
    If QueryAnalyst has been popped (not in the queue), a new instance is created
    and prepended. This is safe because QueryAnalyst's session is attached lazily
    by ensure_session() during _execute_decision_node().
    """
    # Already at front — nothing to do
    if self.queue.items and isinstance(self.queue.items[0], TinyCUAQueryAnalystNode):
        return

    # Try to find existing QueryAnalyst further back in the queue
    qa: TinyCUAQueryAnalystNode | None = None
    for i, node in enumerate(self.queue.items):
        if isinstance(node, TinyCUAQueryAnalystNode):
            qa = self.queue.items.pop(i)
            break

    # Not found — create a fresh instance (session attached lazily later)
    if qa is None:
        qa = TinyCUAQueryAnalystNode()

    # Prepend to front
    self.queue.items.insert(0, qa)
```

### _execute_decision_node() — Pending Passthrough Injection + Consumption

The loop's `_execute_decision_node()` is modified to (a) inject the pending passthrough into the QueryAnalyst input, and (b) clear it after successful forward:

```python
# Inside _execute_decision_node(), before the precheck:
if isinstance(node, TinyCUAQueryAnalystNode):
    input_data = self._build_query_analyst_input()

    # Inject pending MandatoryPassthrough from previous run() (FR-003)
    if self._pending_mandatory_passthrough is not None:
        input_data.metadata["mandatory_passthrough"] = (
            self._pending_mandatory_passthrough
        )

    mandatory = node.check_mandatory_passthrough(input_data)
    if mandatory is not None:
        logger.info(
            "node=%s mandatory_passthrough detected in loop, bypassing LLM",
            node.node_id,
        )
        from tinycua.models.classification import PASSTHROUGH

        passthrough_content = (
            f"[Passthrough] target={mandatory.target_node_id} "
            f"reason={mandatory.reason}"
        )
        self._record_node_output(node, passthrough_content)
        decision = DecisionResult(
            route_label=PASSTHROUGH,
            analysis_response=LLMResult(content="", role="assistant"),
            classification_response=LLMResult(
                content=PASSTHROUGH, role="assistant"
            ),
        )
        node.on_complete(self.queue, decision)

        # Clear passthrough after successful forward to prevent stale re-use (FR-010)
        self._clear_mandatory_passthrough()

        return passthrough_content, True, decision

    # Stale passthrough — clear so it doesn't persist across run() calls
    if self._pending_mandatory_passthrough is not None:
        logger.info(
            "node=%s clearing stale mandatory passthrough (session mismatch)",
            node.node_id,
        )
        self._clear_mandatory_passthrough()
```

### run() — Queue Restart for Passthrough Detection

The loop's `run()` method is modified to restart the queue from QueryAnalyst when a passthrough is pending:

```python
async def run(self, agent, messages, ...):
    self.root_session.input_context = list(messages)

    # FR-001/FR-003: Queue restart — when a passthrough is pending from a
    # previous open_question, ensure QueryAnalyst is at the front of the
    # queue so _execute_decision_node() can inject the directive.
    if self._pending_mandatory_passthrough is not None:
        self._ensure_query_analyst_at_front()

    if self.default_terminal_node is not None:
        self.queue.ensure_terminal(self.default_terminal_node)
    ...
```

### QueryAnalyst.route_passthrough (Currently a No-Op)

The existing `route_passthrough()` is documented as "a no-op at queue level — the actual forwarding happens via MandatoryPassthrough metadata." This is correct for the current architecture: the loop's `_execute_decision_node()` detects the passthrough and calls `node.on_complete()` with the PASSTHROUGH route, then the queue advances normally.

**No change needed to `route_passthrough()`** — the forwarding mechanism is the loop-level passthrough detection in `_execute_decision_node()`, not the route handler. The route handler's role is to log and acknowledge the passthrough.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| No active ResultReviewer node | Warning log, no passthrough installed | Fallback to normal classification |
| ResultReviewer has no session | Warning log, no passthrough installed | Should not happen in practice |
| Stale passthrough (session mismatch) | Fallback to LLM classification | Existing behavior in `check_mandatory_passthrough` |
| Passthrough consumed after forward | Cleared from loop field (`_clear_mandatory_passthrough()`) | Prevents stale re-use on next `run()` |

---

## Implementation Phases

### Phase 1 — MVP (required for initial release)

- [ ] Add `_pending_mandatory_passthrough` field to `TinyCUALoop`
- [ ] Implement `_install_mandatory_passthrough()` on `TinyCUALoop`
- [ ] Implement `_clear_mandatory_passthrough()` on `TinyCUALoop`
- [ ] Implement `_find_result_reviewer()` on `TinyCUALoop`
- [ ] Implement `_ensure_query_analyst_at_front()` on `TinyCUALoop` — ensures QueryAnalyst is at the front of the queue when a passthrough is pending, so `_execute_decision_node()` can detect it
- [ ] Update `run()` to call `_ensure_query_analyst_at_front()` when `_pending_mandatory_passthrough is not None`
- [ ] Update `_on_reviewer_open_question()` to install MandatoryPassthrough
- [ ] Update `_execute_decision_node()` to inject `_pending_mandatory_passthrough` into QueryAnalyst input and clear it after successful forward
- [ ] Add unit tests for installation, clearing, injection, forwarding, and queue restart
- [ ] Add integration test for end-to-end open_question → passthrough → continuation (two-call flow)

### Phase 2 — Enhancements (post-MVP)

- [ ] Add integration-level test for stale passthrough with `allow_query_analyst_restart=False` across multiple `run()` invocations (isolation-level test `test_stale_passthrough_restart_false_drops_continuation` already exists)

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Store MandatoryPassthrough as a loop-level field (`_pending_mandatory_passthrough`) and inject it in `_execute_decision_node()`
   - **Reason**: `TinyCUALoop.run()` replaces `root_session.input_context` on each invocation (the `self.root_session.input_context = list(messages)` assignment), so any passthrough stored in `input_context` during one `run()` call would be lost before the next. Loop-level storage survives the reset. The injection is a single line in `_execute_decision_node()` that merges the pending directive into `NodeInput.metadata` before the precheck.
   - **Alternatives Considered**: Store in `input_context` metadata — rejected; `run()` replaces `input_context` (`self.root_session.input_context = list(messages)`) on each call, destroying the passthrough before the next `run()` can detect it.

2. **Decision**: `_on_reviewer_open_question()` finds ResultReviewer via queue scan
   - **Reason**: The queue contains all active nodes. Scanning for `TinyCUAResultReviewerNode` is simple and reliable.
   - **Alternatives Considered**: Store reviewer reference on loop — rejected; adds coupling and the queue already provides the relationship.

3. **Decision**: `allow_query_analyst_restart=True` by default
   - **Reason**: Safety — if the user sends a new top-level query instead of answering, QueryAnalyst classifies it normally rather than forcing it to a stale reviewer.
   - **Alternatives Considered**: Default False — rejected; could trap user input in a stale continuation.

4. **Decision**: Clear existing passthrough before installing new one
   - **Reason**: Only the latest `open_question` decision should be active. Multiple sequential open_questions replace, not stack.
   - **Alternatives Considered**: Stack multiple passthroughs — rejected; adds complexity with no clear use case.

5. **Decision**: Do not modify `QueryAnalyst.route_passthrough()`
   - **Reason**: The forwarding mechanism is the loop-level passthrough detection in `_execute_decision_node()`, not the route handler. The route handler's role is to log and acknowledge.
   - **Alternatives Considered**: Move forwarding into route_passthrough — rejected; the loop already handles the passthrough detection and calling `on_complete()` with the PASSTHROUGH route.

6. **Decision**: Restart queue to QueryAnalyst at start of `run()` when passthrough is pending
   - **Reason**: After a `run()` call where `open_question` fires, the queue has advanced past QueryAnalyst. On the next `run()`, the loop starts from the terminal node and never reaches `_execute_decision_node()`, making the passthrough undetectable. By moving QueryAnalyst back to the front at the start of `run()`, the passthrough injection in `_execute_decision_node()` is always reachable.
   - **Implementation**: `_ensure_query_analyst_at_front()` scans the queue for an existing QueryAnalyst (moving it to front), or creates a fresh one if it has been popped. Called from `run()` only when `_pending_mandatory_passthrough is not None`.
   - **Alternatives Considered**:
     - Return `should_advance=False` from ResultReviewer on `open_question` — rejected; would prevent the loop from reaching the terminal node and returning a response.
     - Reset entire queue to initial state at each `run()` — rejected; loses dynamic queue mutations (spawned nodes) between calls.
     - Check for pending passthrough in `_execute_node()` for any node, not just DecisionNodes — rejected; couples non-DecisionNode logic to query analyst concerns.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ResultReviewer may not be in queue when open_question fires | Low | Low | `_find_result_reviewer()` returns None; warning logged; no passthrough installed; falls back to normal flow |
| Queue advanced past QueryAnalyst on continuation run() | Medium | High | `_ensure_query_analyst_at_front()` called from `run()` when `_pending_mandatory_passthrough` is set; moves QueryAnalyst to front of queue so passthrough injection is reachable |
| Stale passthrough from a previous run cycle | Medium | Low | Cleared after successful forward in `_execute_decision_node()`; stale guard in `check_mandatory_passthrough()` as second line of defense |
| User sends empty continuation after open_question | Low | Low | QueryAnalyst classifies empty input as uncertain; normal behavior |

---

## Open Questions (optional)

1. ~~**Should the MandatoryPassthrough be stored on the loop or in root session metadata?**~~ _(Resolved — loop-level storage, see Technical Decision #1)_
2. ~~**Should the passthrough message be removed from input_context after forwarding, or kept for audit?**~~ _(Resolved — stored on loop as `_pending_mandatory_passthrough`, cleared via `_clear_mandatory_passthrough()` after successful forward. Audit trail is in chat_history/session_context.)_

---

## References

- Spec: `./spec.md`
- RouteMap target architecture: `src/tinycua/docs/design/loops/route_map.md` — MandatoryPassthrough section
- ReviewerDecision target architecture: `src/tinycua/docs/design/models/reviewer_decision.md` — open_question behavior
- TinyCUALoop target architecture: `src/tinycua/docs/design/loops/tinycua_loop.md`
- MandatoryPassthrough model: `src/tinycua/tinycua/models/classification.py`
- QueryAnalyst precheck: `src/tinycua/tinycua/loops/query_analyst.py` — `check_mandatory_passthrough()`
- ResultReviewer dispatch: `src/tinycua/tinycua/loops/result_reviewer.py` — `on_complete()`
- Existing spec: `specs/tinycua-executor-reviewer/spec.md` — defers open_question routing to 3.3
