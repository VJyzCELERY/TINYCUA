# Design Document: Propagation and Dedupe

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-12
**Milestone**: 4.1 — Propagation and Dedupe

---

## Overview

This design implements explicit propagation rules and dedupe logic for TinyCUA node context. It separates `chat_history` (append-only audit) from `session_context` (mutable LLM-reusable context), introduces `PropagationRule` for configurable boundary crossing, and adds `ChatRecord` as a durable audit model. The segmented context model (`prior`, `input`, `output`) ensures nodes propagate context correctly without duplication.

---

## Architecture

### Component Overview

```
Node terminates
  ├── Upward propagation (to parent/root)
  │     ├── session_context: prior + input segments (deduped per PropagationRule)
  │     └── chat_history: ChatRecord appended (per PropagationRule.chat_history)
  └── Forwarding (to next node)
        └── session_context: output segment becomes next node's NodeInput
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| tinycua.models.chat_record | New | ChatRecord append-only audit model |
| tinycua.models.session_context_entry | New | SessionContextEntry with segment metadata |
| tinycua.loops.propagation | New | PropagationRule, propagation logic, dedupe |
| tinycua.models.session | Modified | Separate chat_history (append-only) and session_context (mutable) |
| tinycua.config.node_config | Modified | NodeMessagePolicy.dedupe_by_origin_record_id |
| tinycua.loops.node_queue | Modified | Propagation hooks on node termination |
| tinycua.loops.tinycua_loop | Modified | Terminal output exception during finalization |

---

## Data Model

### New Entities

```python
# ChatRecord — append-only durable audit transcript
ChatRecord:
    record_id: str                    # unique identifier (uuid4)
    role: Literal["user", "assistant", "system", "tool"]
    record_type: str                  # audit category: node_output, internal_continuation, tool_result, retry, queue_lifecycle, propagation
    content: str | dict | list[dict]  # message content
    visibility: Literal["user_visible", "internal", "tool_only"]
    source_node_id: str | None        # node that produced this record
    source_session_id: str | None     # session that produced this record
    receiver_node_id: str | None      # intended consumer node
    receiver_session_id: str | None   # intended consumer session
    origin_record_id: str | None      # original record_id when copied/propagated (for dedupe)
    created_seq: int                   # monotonic sequence for ordering
    metadata: dict                     # extensible metadata

# SessionContextEntry — mutable LLM-reusable context with segment metadata
# A separate mutable context record (not an extension of the append-only ChatRecord).
# Carries the same provenance fields as ChatRecord plus segment metadata.
# NOTE: This milestone implements SessionContextEntry as a standalone dataclass for simplicity.
# Extending ChatRecord is a potential future refactoring target (see session.md for the
# target architecture's extended model).
SessionContextEntry (dataclass):
    record_id: str = field(default_factory=lambda: uuid4().hex)  # auto-generated unique identifier
    segment: Literal["prior", "input", "output"]
    content: str | dict | list[dict]
    origin_record_id: str | None = None
    source_node_id: str | None = None
    source_session_id: str | None = None
    created_seq: int
```

### PropagationRule

```python
PropagationRule:
    chat_history: Literal["none", "parent", "root", "parent_and_root"]
    session_context_target: Literal["none", "parent", "root", "parent_and_root"]
    session_context_mode: Literal["none", "final", "full", "selected"]
    token_usage: Literal["none", "parent", "root", "parent_and_root"]
    failure: Literal["none", "parent", "root", "parent_and_root"]
    dedupe: bool
```

### session_context_mode Values

- `none`: No session context is propagated upward.
- `final`: Only the final session_context entry is propagated.
- `full`: All session_context entries are propagated.
- `selected`: Only session_context entries matching a configurable filter (e.g., `visibility="internal"` or `segment="output"`) are propagated. The filter criteria is determined by the propagation profile or node-level configuration.

### Propagation Profiles

| Profile | chat_history | session_context_target | session_context_mode | token_usage | failure |
|---------|--------------|------------------------|----------------------|-------------|---------|
| transient_legacy | parent_and_root | none | none | parent_and_root | parent_and_root |
| natural_termination_legacy | parent_and_root | parent_and_root | final | parent_and_root | parent_and_root |
| mid_progress_legacy | parent_and_root | parent_and_root | full | parent_and_root | parent_and_root |
| selected_internal_output | root | root | selected | root | root |

### Schema Changes

- `Session.chat_history` becomes append-only `list[ChatRecord]` (was `list[dict]`).
- `Session.session_context` becomes `list[SessionContextEntry]` (was `list[dict]`).
- `SessionContextEntry` extends or replaces raw dict entries with segment metadata.
- `NodeMessagePolicy` gains `dedupe_by_origin_record_id: bool` field.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
class PropagationRule:
    """Configuration for what crosses node/session boundaries."""
    
    chat_history: Literal["none", "parent", "root", "parent_and_root"]
    session_context_target: Literal["none", "parent", "root", "parent_and_root"]
    session_context_mode: Literal["none", "final", "full", "selected"]
    token_usage: Literal["none", "parent", "root", "parent_and_root"]
    failure: Literal["none", "parent", "root", "parent_and_root"]
    dedupe: bool  # True to filter duplicates during propagation


def propagate_on_termination(
    node_session: Session,
    parent_session: Session | None,
    root_session: Session,
    rule: PropagationRule,
) -> None:
    """
    Propagate context when a node terminates.
    
    Upward: prior + input segments propagate to parent/root per rule.
    The output segment is NOT propagated upward (forwarded to next node).
    Dedupe is applied when rule.dedupe is True.
    
    Replaces the ad-hoc `_transfer_session_context()` with rule-based propagation.
    When parent_session is None, only root propagation occurs.
    Non-propagated fields (task, todo, session_config) are NOT transferred by
    this function — they remain handled elsewhere (e.g., Session identity fields).
    """


def forward_output_to_next(
    node_session: Session,
    next_node_input: NodeInput,  # existing type defined in tinycua.models.node_input
) -> None:
    """
    Forward the output segment to the next node as NodeInput.
    """


def finalize_terminal_output(
    terminal_session: Session,
    root_session: Session,
) -> str:
    """
    Terminal output exception: commit terminal output segment to root
    session_context and return to SDK caller.
    """


def dedupe_records(
    source: list[SessionContextEntry],
    destination: list[SessionContextEntry],
) -> list[SessionContextEntry]:
    """
    Filter duplicates from source before adding to destination.
    Compare origin_record_id when present, fall back to record_id.
    Keep earliest existing record in destination.
    """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Empty output segment | No forwarding occurs | Prior + input still propagate upward |
| Invalid propagation rule field | ValueError | Rule validation at construction |
| Terminal output with no root session | LoopError | Should not happen with proper bootstrap |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create `ChatRecord` dataclass with all metadata fields
- [ ] Create `SessionContextEntry` dataclass with segment metadata
- [ ] Create `PropagationRule` dataclass with all fields
- [ ] Implement propagation profiles as predefined PropagationRule instances
- [ ] Implement `propagate_on_termination()` for upward propagation
- [ ] Implement `forward_output_to_next()` for output segment forwarding
- [ ] Implement `finalize_terminal_output()` for terminal exception
- [ ] Implement `dedupe_records()` with origin_record_id comparison
- [ ] Integrate propagation into NodeQueue node termination
- [ ] Integrate terminal output exception into TinyCUALoop finalization
- [ ] Update Session model to use ChatRecord and SessionContextEntry
- [ ] Add `NodeMessagePolicy.dedupe_by_origin_record_id` field
- [ ] Write unit tests for all propagation and dedupe logic
- [ ] Write integration tests for propagation e2e

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Advanced propagation profiles beyond the four defined
- [ ] Propagation debugging/logging hooks

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Separate ChatRecord (audit) from SessionContextEntry (LLM-reusable)
   - **Reason**: ChatRecord preserves provenance even when session_context compacts; session_context is mutable and deduped for LLM use
   - **Alternatives Considered**: Single combined record — rejected because audit trail would be lost during compaction

2. **Decision**: Segment metadata on SessionContextEntry (not index slicing)
   - **Reason**: Records carry segment info explicitly; implementation does not rely on list indices which can shift
   - **Alternatives Considered**: Index-based slicing — rejected because fragile with insertions/removals

3. **Decision**: Dedupe by origin_record_id with record_id fallback
   - **Reason**: Copied/propagated records preserve original id in origin_record_id; new records use their own record_id
   - **Alternatives Considered**: Dedupe by content hash — rejected because content comparison is expensive and ambiguous

4. **Decision**: Terminal output exception in TinyCUALoop finalization
   - **Reason**: Terminal ResponseNode output has no successor; must be explicitly committed to root and returned
   - **Alternatives Considered**: Treat terminal like any other node — rejected because output would be lost with no next node

5. **Decision**: Propagation profiles as predefined PropagationRule instances
   - **Reason**: Common patterns are reusable and documented; nodes can reference profiles by name
   - **Alternatives Considered**: Inline rule construction everywhere — rejected because verbose and error-prone

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Propagation interacts unexpectedly with compaction | Medium | High | Compaction operates on session_context; propagation happens after. ChatHistory preserves audit trail regardless. |
| Dedupe performance with large context | Low | Medium | Dedupe is O(n) per destination; acceptable for prototype scale |
| Segment metadata increases memory usage | Low | Low | Metadata is lightweight; acceptable tradeoff for explicit propagation |
| Terminal output exception edge cases with suspension | Medium | Medium | Document all suspension/resume paths; test with InformationDigester suspension |

---

## Open Questions

1. **Should PropagationRule be per-node or per-session?**
   - **Status**: Resolved
   - **Resolution**: Per-node with session-level defaults, allowing nodes to override.

2. **How should propagation interact with compaction?**
   - **Status**: Resolved
   - **Resolution**: Compaction operates on session_context; propagation happens after compaction. Compacted records lose their individual entry but chat_history preserves the audit trail. Propagation never re-propagates already-compacted entries.

---

## References

- Spec: `./spec.md`
- Propagation design: `src/tinycua/docs/design/loops/propagation.md`
- Session design: `src/tinycua/docs/design/models/session.md`
- ChatRecord design: `src/tinycua/docs/design/models/chat_record.md`
- NodeQueue design: `src/tinycua/docs/design/loops/node_queue.md`
- TinyCUALoop design: `src/tinycua/docs/design/loops/tinycua_loop.md`
- Node design: `src/tinycua/docs/design/loops/node.md` (see also `node.md` for node message assembly and `build_messages_with_dedupe` behavior)
