# Implementation: Propagation and Dedupe (Milestone 4.1)

Implement explicit propagation rules and dedupe logic for TinyCUA node context. Separates `chat_history` (append-only audit) from `session_context` (mutable LLM-reusable context), introduces `PropagationRule` for configurable boundary crossing, adds `ChatRecord` as a durable audit model, and implements deduplication during propagation and LLM input assembly.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P0
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies (pure model/logic changes)

### Running Services

- [x] **None** — no external services needed (unit/integration tests only)

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11, uv
- [x] **None** — no special tooling required beyond standard dev setup

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/unit/test_propagation.py
"""Integration tests for propagation and dedupe."""

from tinycua.models.chat_record import ChatRecord
from tinycua.models.session_context_entry import SessionContextEntry
from tinycua.models.session import Session
from tinycua.loops.propagation import (
    PropagationRule,
    propagate_on_termination,
    forward_output_to_next,
    finalize_terminal_output,
    dedupe_records,
    PROPAGATION_PROFILES,
)
from tinycua.config.node_config import NodeConfigBase, NodeMessagePolicy


def test_propagation_upward_and_forwarding():
    """On node termination, prior+input propagate upward, output forwards to next."""
    # Arrange
    root_session = Session(session_id="root", chat_history=[], session_context=[], input_context=[])
    parent_session = Session(session_id="parent", parent_id="root", chat_history=[], session_context=[], input_context=[])
    node_session = Session(session_id="node1", parent_id="parent", chat_history=[], session_context=[], input_context=[])

    prior = SessionContextEntry(content="prior context", segment="prior", source_node_id="n0", created_seq=1)
    inp = SessionContextEntry(content="input data", segment="input", source_node_id="n1", created_seq=2)
    out = SessionContextEntry(content="output result", segment="output", source_node_id="n1", created_seq=3)
    node_session.session_context = [prior, inp, out]

    rule = PROPAGATION_PROFILES["natural_termination_legacy"]

    # Act
    propagate_on_termination(node_session, parent_session, root_session, rule)

    # Assert — output NOT in parent/root (forwarded to next node)
    parent_contents = [e.content for e in parent_session.session_context]
    root_contents = [e.content for e in root_session.session_context]
    assert "prior context" in parent_contents
    assert "input data" in parent_contents
    assert "output result" not in parent_contents
    assert "output result" not in root_contents


def test_dedupe_on_propagation_filters_duplicates():
    """When dedupe=True, records with matching origin_record_id are filtered."""
    # Arrange
    root_session = Session(session_id="root", chat_history=[], session_context=[], input_context=[])
    parent_session = Session(session_id="parent", parent_id="root", chat_history=[], session_context=[], input_context=[])
    node_session = Session(session_id="node1", parent_id="parent", chat_history=[], session_context=[], input_context=[])

    existing = SessionContextEntry(
        content="already propagated", segment="prior", source_node_id="n0",
        origin_record_id="orig-123", created_seq=1
    )
    parent_session.session_context = [existing]

    duplicate = SessionContextEntry(
        content="already propagated", segment="prior", source_node_id="n0",
        origin_record_id="orig-123", created_seq=2
    )
    fresh = SessionContextEntry(
        content="new context", segment="input", source_node_id="n1",
        origin_record_id="orig-456", created_seq=3
    )
    node_session.session_context = [duplicate, fresh]

    rule = PROPAGATION_PROFILES["natural_termination_legacy"]

    # Act
    propagate_on_termination(node_session, parent_session, root_session, rule)

    # Assert — duplicate filtered, fresh added
    contents = [e.content for e in parent_session.session_context]
    assert contents.count("already propagated") == 1
    assert "new context" in contents


def test_terminal_output_exception():
    """Terminal output is committed to root session_context and returned, not forwarded."""
    root_session = Session(session_id="root", chat_history=[], session_context=[], input_context=[])
    terminal_session = Session(session_id="terminal", parent_id="root", chat_history=[], session_context=[], input_context=[])

    out = SessionContextEntry(content="final answer", segment="output", source_node_id="resp1", created_seq=1)
    prior = SessionContextEntry(content="context", segment="prior", source_node_id="resp1", created_seq=2)
    terminal_session.session_context = [prior, out]

    result = finalize_terminal_output(terminal_session, root_session)

    # Assert — output committed to root
    root_contents = [e.content for e in root_session.session_context]
    assert "final answer" in root_contents
    assert result == "final answer"


def test_chat_record_appended_during_propagation():
    """ChatRecord is appended to chat_history per PropagationRule.chat_history."""
    root_session = Session(session_id="root", chat_history=[], session_context=[], input_context=[])
    parent_session = Session(session_id="parent", parent_id="root", chat_history=[], session_context=[], input_context=[])
    node_session = Session(session_id="node1", parent_id="parent", chat_history=[], session_context=[], input_context=[])

    out = SessionContextEntry(content="result", segment="output", source_node_id="n1", created_seq=1)
    node_session.session_context = [out]

    rule = PROPAGATION_PROFILES["natural_termination_legacy"]

    # Act
    propagate_on_termination(node_session, parent_session, root_session, rule)

    # Assert — ChatRecord appended to both parent and root chat_history
    assert len(parent_session.chat_history) > 0
    assert len(root_session.chat_history) > 0
    assert isinstance(parent_session.chat_history[0], ChatRecord)
    assert parent_session.chat_history[0].record_type == "propagation"


def test_empty_output_no_forwarding():
    """Empty output segment does not cause forwarding; prior+input still propagate."""
    root_session = Session(session_id="root", chat_history=[], session_context=[], input_context=[])
    parent_session = Session(session_id="parent", parent_id="root", chat_history=[], session_context=[], input_context=[])
    node_session = Session(session_id="node1", parent_id="parent", chat_history=[], session_context=[], input_context=[])

    prior = SessionContextEntry(content="prior", segment="prior", source_node_id="n0", created_seq=1)
    node_session.session_context = [prior]

    rule = PROPAGATION_PROFILES["natural_termination_legacy"]

    # Act — no output segment
    propagate_on_termination(node_session, parent_session, root_session, rule)

    # Assert — prior propagated to parent
    contents = [e.content for e in parent_session.session_context]
    assert "prior" in contents


def test_dedupe_records_by_origin_record_id():
    """dedupe_records filters by origin_record_id when present."""
    source = [
        SessionContextEntry(content="copy1", segment="prior", origin_record_id="orig-1", created_seq=1),
        SessionContextEntry(content="copy2", segment="input", origin_record_id="orig-2", created_seq=2),
    ]
    destination = [
        SessionContextEntry(content="existing", segment="prior", origin_record_id="orig-1", created_seq=0),
    ]

    result = dedupe_records(source, destination)

    # orig-1 filtered (already exists), orig-2 kept
    assert len(result) == 1
    assert result[0].origin_record_id == "orig-2"


def test_dedupe_falls_back_to_record_id():
    """dedupe_records falls back to record_id when origin_record_id is None."""
    source = [
        SessionContextEntry(content="item", segment="prior", record_id="id-abc", origin_record_id=None, created_seq=1),
    ]
    destination = [
        SessionContextEntry(content="item", segment="prior", record_id="id-abc", origin_record_id=None, created_seq=0),
    ]

    result = dedupe_records(source, destination)
    assert len(result) == 0  # filtered by record_id match


def test_propagation_profiles_all_defined():
    """All four required profiles are defined with correct field values."""
    assert "transient_legacy" in PROPAGATION_PROFILES
    assert "natural_termination_legacy" in PROPAGATION_PROFILES
    assert "mid_progress_legacy" in PROPAGATION_PROFILES
    assert "selected_internal_output" in PROPAGATION_PROFILES

    t = PROPAGATION_PROFILES["transient_legacy"]
    assert t.session_context_target == "none"
    assert t.session_context_mode == "none"

    nt = PROPAGATION_PROFILES["natural_termination_legacy"]
    assert nt.session_context_target == "parent_and_root"
    assert nt.session_context_mode == "final"

    mp = PROPAGATION_PROFILES["mid_progress_legacy"]
    assert mp.session_context_mode == "full"

    si = PROPAGATION_PROFILES["selected_internal_output"]
    assert si.chat_history == "root"
    assert si.session_context_target == "root"
    assert si.session_context_mode == "selected"


def test_node_message_policy_dedupe_by_origin():
    """NodeMessagePolicy.dedupe_by_origin_record_id filters duplicates from LLM input."""
    from tinycua.loops.node import build_messages_with_dedupe

    session = Session(session_id="s1", chat_history=[], session_context=[], input_context=[])
    e1 = SessionContextEntry(content="ctx1", segment="prior", origin_record_id="orig-1", created_seq=1)
    e2 = SessionContextEntry(content="ctx2", segment="input", origin_record_id="orig-2", created_seq=2)
    e3 = SessionContextEntry(content="ctx1-dup", segment="prior", origin_record_id="orig-1", created_seq=3)
    session.session_context = [e1, e2, e3]

    messages = build_messages_with_dedupe(session, dedupe_by_origin_record_id=True)

    # Only 2 unique entries (by origin_record_id)
    context_msgs = [m for m in messages if m.get("role") == "user"]
    origin_ids = [m.get("metadata", {}).get("origin_record_id") for m in context_msgs if m.get("metadata")]
    assert len([x for x in origin_ids if x == "orig-1"]) == 1


def test_segmented_context_creation():
    """SessionContextEntry supports all three segment values."""
    prior = SessionContextEntry(content="p", segment="prior", created_seq=1)
    inp = SessionContextEntry(content="i", segment="input", created_seq=2)
    out = SessionContextEntry(content="o", segment="output", created_seq=3)
    assert prior.segment == "prior"
    assert inp.segment == "input"
    assert out.segment == "output"
```

### Key Test Scenarios

- [ ] **Scenario 1**: Upward propagation + output forwarding — verifies segmented context flows correctly on node termination
- [ ] **Scenario 2**: Dedupe on propagation — filters duplicates by origin_record_id before writing to parent/root
- [ ] **Scenario 3**: Terminal output exception — terminal output committed to root, not forwarded
- [ ] **Scenario 4**: ChatRecord audit trail — records appended to chat_history during propagation
- [ ] **Scenario 5**: Empty output handling — no forwarding, but prior+input still propagate
- [ ] **Edge case**: Dedupe fallback to record_id when origin_record_id is None

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for each new module: chat_record, session_context_entry, propagation
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify propagation behavior with a minimal two-node queue: inspect session_context at each step
- [ ] Verify terminal output exception with ResponseNode as terminal node

### Performance Considerations

- [ ] Dedupe is O(n) per destination — acceptable for prototype scale (verified in design)

## Proposed Changes

### Models

#### NEW `src/tinycua/tinycua/models/chat_record.py`

- **ChatRecord dataclass**: Append-only durable audit transcript with fields: `record_id`, `role`, `record_type`, `content`, `visibility`, `source_node_id`, `source_session_id`, `receiver_node_id`, `receiver_session_id`, `origin_record_id`, `created_seq`, `metadata`.
- **Rationale**: Required by FR-003 for separate audit trail from mutable session_context.

#### NEW `src/tinycua/tinycua/models/session_context_entry.py`

- **SessionContextEntry dataclass**: Mutable LLM-reusable context with segment metadata (`prior`, `input`, `output`), origin/source IDs (`origin_record_id`, `source_node_id`, `source_session_id`), and `created_seq`.
- **Rationale**: Required by FR-004, FR-005 for segmented context model.

#### MODIFY `src/tinycua/tinycua/models/session.py`

- **Separate chat_history and session_context types**: `chat_history` becomes `list[ChatRecord]` (append-only), `session_context` becomes `list[SessionContextEntry]` (mutable, deduped).
- **Rationale**: Required by FR-002 to separate audit from LLM-reusable context.

#### MODIFY `src/tinycua/tinycua/models/__init__.py`

- **Re-export new models**: Add `ChatRecord` and `SessionContextEntry` to module exports.

### Propagation Engine

#### NEW `src/tinycua/tinycua/loops/propagation.py`

- **PropagationRule dataclass**: Configuration with fields: `chat_history`, `session_context_target`, `session_context_mode`, `token_usage`, `failure`, `dedupe`.
- **PROPAGATION_PROFILES dict**: Predefined profiles for `transient_legacy`, `natural_termination_legacy`, `mid_progress_legacy`, `selected_internal_output`.
- **`propagate_on_termination()`**: Upward propagation — prior + input segments to parent/root per rule; output segment excluded from upward. Dedupe applied when `rule.dedupe=True`.
- **`forward_output_to_next()`**: Forwards output segment to next node as NodeInput.
- **`finalize_terminal_output()`**: Terminal output exception — commits output to root session_context and returns content string.
- **`dedupe_records()`**: Filters source records against destination by `origin_record_id` (fallback `record_id`), keeping earliest existing record.
- **Rationale**: Core implementation of FR-001, FR-006, FR-007, FR-008, FR-010.

### Config

#### MODIFY `src/tinycua/tinycua/config/node_config.py`

- **NodeConfigBase.propagation**: Change type from `Any` to `PropagationRule | None` (currently a placeholder).
- **NodeMessagePolicy.dedupe_by_origin_record_id**: Already declared as `bool = True`; wire into message assembly logic.
- **Rationale**: Required by FR-009.

### Loop Integration

#### MODIFY `src/tinycua/tinycua/loops/tinycua_loop.py`

- **Replace `_transfer_session_context()`**: Use `propagate_on_termination()` from propagation module instead of ad-hoc identity-based copying.
- **Wire terminal output exception**: In `_run_sync()`/`_run_stream()` finalization, call `finalize_terminal_output()` when the terminal node is a ResponseNode.
- **Update `_build_node_messages()`**: Apply `dedupe_by_origin_record_id` filtering when assembling LLM-bound messages.
- **Update `_record_node_output()`**: Append `ChatRecord` to `chat_history` instead of raw dict.
- **Rationale**: Integration point for all propagation and dedupe logic.

#### MODIFY `src/tinycua/tinycua/loops/node.py`

- **Add `build_messages_with_dedupe()` helper**: Filters session_context by origin_record_id before building messages for LLM.
  - Signature:
    ```python
    def build_messages_with_dedupe(
        session: Session,
        dedupe_by_origin_record_id: bool = False,
    ) -> list[dict[str, str]]:
    ```
  - When `dedupe_by_origin_record_id=True`, filters `session_context` entries to remove duplicates by `origin_record_id` (falling back to `record_id`) before assembling LLM-bound messages.
- **Update `Node.propagate()`**: No-op default stays; concrete nodes override as needed.
- **Rationale**: FR-009 dedupe on LLM input.

#### MODIFY `src/tinycua/tinycua/loops/node_queue.py`

- **Update `advance()`**: After `propagate()`, handle output forwarding via `forward_output_to_next()`.
- **Rationale**: Propagation hooks on node termination per design.

### Concrete Node Updates

#### MODIFY `src/tinycua/tinycua/loops/information_digester.py`

- **Update `propagate()`**: Use `SessionContextEntry` with `segment="output"` instead of raw dict.
- **Rationale**: Align with segmented context model.

#### MODIFY `src/tinycua/tinycua/loops/worker.py`

- **Update `propagate()`**: Use `SessionContextEntry` with segment metadata.
- **Rationale**: Align with segmented context model.

### Tests

#### NEW `tests/unit/test_propagation.py`

- **Integration tests** (defined above): All 10 test functions covering propagation, dedupe, terminal output, ChatRecord, profiles, and edge cases.

#### NEW `tests/unit/test_chat_record.py`

- **Unit tests**: ChatRecord creation, metadata fields, serialization.

#### NEW `tests/unit/test_session_context_entry.py`

- **Unit tests**: SessionContextEntry creation, segment values, origin/source IDs.

---

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| tinycua.models.chat_record | New | ChatRecord append-only audit model |
| tinycua.models.session_context_entry | New | SessionContextEntry with segment metadata |
| tinycua.loops.propagation | New | PropagationRule, propagation logic, dedupe |
| tinycua.models.session | Modified | Separate chat_history (ChatRecord) and session_context (SessionContextEntry) |
| tinycua.config.node_config | Modified | PropagationRule typing, dedupe wiring |
| tinycua.loops.node_queue | Modified | Propagation hooks on node termination |
| tinycua.loops.tinycua_loop | Modified | Terminal output exception, propagation integration |
| tinycua.loops.node | Modified | build_messages_with_dedupe helper |
| tinycua.loops.information_digester | Modified | Segment-aware propagation |
| tinycua.loops.worker | Modified | Segment-aware propagation |

## Data Model Changes

```python
# New types
ChatRecord(dataclass):
    record_id: str                    # uuid4 hex
    role: Literal["user", "assistant", "system", "tool"]
    record_type: str                  # node_output, propagation, tool_result, etc.
    content: str | dict | list[dict]
    visibility: Literal["user_visible", "internal", "tool_only"]
    source_node_id: str | None
    source_session_id: str | None
    receiver_node_id: str | None
    receiver_session_id: str | None
    origin_record_id: str | None
    created_seq: int
    metadata: dict

SessionContextEntry(dataclass):
    record_id: str                    # uuid4 hex
    segment: Literal["prior", "input", "output"]
    content: str | dict | list[dict]
    origin_record_id: str | None
    source_node_id: str | None
    source_session_id: str | None
    created_seq: int

PropagationRule(dataclass):
    chat_history: Literal["none", "parent", "root", "parent_and_root"]
    session_context_target: Literal["none", "parent", "root", "parent_and_root"]
    session_context_mode: Literal["none", "final", "full", "selected"]
    token_usage: Literal["none", "parent", "root", "parent_and_root"]
    failure: Literal["none", "parent", "root", "parent_and_root"]
    dedupe: bool

# Modified interfaces
Session:
    chat_history: list[ChatRecord]          # was list[dict]
    session_context: list[SessionContextEntry]  # was list[dict]
```

## Dependencies

### External Dependencies

- [x] **None** — no new external packages required

### Internal Dependencies

- [x] Depends on existing NodeQueue suspension/prepend from Milestone 1.7 (already implemented)
- [ ] Blocks no other features — this is a standalone milestone

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Propagation interacts unexpectedly with compaction | High | Compaction operates on session_context; propagation happens after. ChatHistory preserves audit trail regardless. |
| Dedupe performance with large context | Medium | Dedupe is O(n) per destination; acceptable for prototype scale |
| Segment metadata increases memory usage | Low | Metadata is lightweight; acceptable tradeoff for explicit propagation |
| Terminal output exception edge cases with suspension | Medium | Document all suspension/resume paths; test with InformationDigester suspension |
| Backward compatibility with existing node propagate() overrides | Medium | Update InformationDigester and Worker node propagate() to use new segment model |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-12*
