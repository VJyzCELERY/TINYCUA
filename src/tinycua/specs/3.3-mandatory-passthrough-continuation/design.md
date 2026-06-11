# Design Document: Mandatory Passthrough and Continuation Routing

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-11
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
| tinycua.loops.query_analyst | Modified | `route_passthrough()` forwards input to target node (currently a no-op) |
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

The `MandatoryPassthrough` directive is stored in `root_session.input_context` as a special message with metadata:

```python
# Injected into root_session.input_context by _on_reviewer_open_question()
{
    "role": "user",
    "content": "",  # empty — this is a routing directive, not user content
    "metadata": {
        "mandatory_passthrough": MandatoryPassthrough(
            target_node_id="result_reviewer",
            target_session_id="<result_reviewer session_id>",
            reason="open_question needs user continuation",
            allow_query_analyst_restart=True,
        )
    }
}
```

**Why input_context?** `_build_query_analyst_input()` already extracts metadata from `root_session.input_context` messages into `NodeInput.metadata`. This means the passthrough directive flows naturally through the existing message pipeline without new storage mechanisms. The `check_mandatory_passthrough()` precheck already reads from `NodeInput.metadata["mandatory_passthrough"]`.

---

## API / Interface Contracts

### Modified Functions

```python
def _on_reviewer_open_question(self, active_task: Task) -> None:
    """Install MandatoryPassthrough targeting ResultReviewer for open_question.

    Creates a MandatoryPassthrough directive and injects it into
    root_session.input_context so the next user continuation is
    routed deterministically to the ResultReviewer.

    Args:
        active_task: The task with an open question.
    """
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
    """Inject a MandatoryPassthrough directive into root_session.input_context.

    Args:
        mandatory: The passthrough directive to install.
    """
    # Clear any existing passthrough first (only latest is active)
    self._clear_mandatory_passthrough()
    self.root_session.input_context.append({
        "role": "user",
        "content": "",
        "metadata": {"mandatory_passthrough": mandatory},
    })
    logger.info(
        "installed_mandatory_passthrough target=%s session=%s reason=%s",
        mandatory.target_node_id,
        mandatory.target_session_id,
        mandatory.reason,
    )
```

```python
def _clear_mandatory_passthrough(self) -> None:
    """Remove any existing MandatoryPassthrough from root_session.input_context."""
    self.root_session.input_context = [
        msg for msg in self.root_session.input_context
        if not (isinstance(msg.get("metadata"), dict)
                and "mandatory_passthrough" in msg["metadata"])
    ]
```

```python
def _find_result_reviewer(self) -> Node | None:
    """Find the active ResultReviewer node in the queue.

    Returns:
        The ResultReviewer node if found, None otherwise.
    """
    for node in self.queue.items():
        if isinstance(node, TinyCUAResultReviewerNode):
            return node
    return None
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
| Passthrough consumed after forward | Cleared from input_context | Prevents stale re-use |

---

## Implementation Phases

### Phase 1 — MVP (required for initial release)

- [ ] Implement `_install_mandatory_passthrough()` on `TinyCUALoop`
- [ ] Implement `_clear_mandatory_passthrough()` on `TinyCUALoop`
- [ ] Implement `_find_result_reviewer()` on `TinyCUALoop`
- [ ] Update `_on_reviewer_open_question()` to install MandatoryPassthrough
- [ ] Add unit tests for installation, clearing, and forwarding
- [ ] Add integration test for end-to-end open_question → passthrough → continuation

### Phase 2 — Enhancements (post-MVP)

- [ ] Clear passthrough after successful forward in `_execute_decision_node()` (consumption tracking)
- [ ] Support `allow_query_analyst_restart=False` behavior in stale guard (already exists in `check_mandatory_passthrough`)

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Store MandatoryPassthrough in `root_session.input_context` metadata
   - **Reason**: `_build_query_analyst_input()` already extracts metadata from `input_context` messages into `NodeInput.metadata`. This reuses the existing pipeline without new storage mechanisms.
   - **Alternatives Considered**: Store on loop as `self._pending_mandatory_passthrough` — rejected because it requires a new injection point in `_build_query_analyst_input()` and creates a parallel storage path.

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

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| input_context metadata message may confuse downstream nodes | Low | Medium | Empty content string + metadata-only message; nodes that don't check metadata will ignore it |
| ResultReviewer may not be in queue when open_question fires | Low | Low | `_find_result_reviewer()` returns None; warning logged; no passthrough installed; falls back to normal flow |
| Stale passthrough from a previous run cycle | Medium | Low | `_clear_mandatory_passthrough()` before installing; stale guard in `check_mandatory_passthrough()` |
| User sends empty continuation after open_question | Low | Low | QueryAnalyst classifies empty input as uncertain; normal behavior |

---

## Open Questions (optional)

1. **Should the passthrough message be removed from input_context after forwarding, or kept for audit?**
   - **Status**: Proposed — remove after forwarding to prevent stale re-use. Audit trail is already in chat_history/session_context.

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
