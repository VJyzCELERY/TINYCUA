# Implementation: State Objects, NodeInput, NodePayload (Milestone 1.4)

Implement the internal transport layer for TinyCUA node communication. `StateObject` provides the serialization base class. `NodePayload` wraps a single node's structured output. `NodeInput` wraps the full handoff envelope between nodes. `NodeInputLike` and `convert_node_input_to_messages()` enable flexible input from external users, internal nodes, or pre-constructed message lists.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: M (~7 hours: integration tests ~2h, verification ~1h, implementation ~4h)

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

- [x] **None** — no external services needed

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

**Estimated time**: ~2 hours

```python
# Test file: tests/integration/test_node_transport.py
"""Integration tests for node transport via NodeInput/NodePayload."""


def test_node_payload_round_trip_through_node_handoff():
    """NodePayload carries structured output through serialize → deserialize → convert."""
    from tinycua.models import NodePayload, NodeInput, convert_node_input_to_messages

    # Arrange: Node A produces a task analysis payload
    payload = NodePayload(
        payload_type="task_analysis",
        source_node="TaskAnalyzer",
        content={"task_id": "T-0.1", "status": "analyzed"},
        metadata={"confidence": 0.95},
    )
    node_input = NodeInput(
        input_type="continuation",
        source_node="TaskAnalyzer",
        target_node="TaskExecutor",
        payloads=[payload],
        messages=[{"role": "user", "content": "Analyze task T-0.1"}],
    )

    # Act: serialize → deserialize → convert to messages
    json_str = node_input.to_json()
    restored = NodeInput.from_json(json_str)
    messages = convert_node_input_to_messages(restored)

    # Assert: messages contain payload as assistant message + continuation user message
    assert len(messages) == 2
    assert messages[0]["role"] == "assistant"
    assert "task_analysis" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Analyze task T-0.1"


def test_node_input_like_union_type_in_build_messages():
    """NodeInputLike union type works in a mock node build_messages() method."""
    from tinycua.models import NodePayload, NodeInput, NodeInputLike, convert_node_input_to_messages

    def build_messages(node_input: NodeInputLike) -> list[dict]:
        return convert_node_input_to_messages(node_input)

    # External user string
    user_msgs = build_messages("What is the weather?")
    assert user_msgs == [{"role": "user", "content": "What is the weather?"}]

    # Internal assistant string
    assistant_msgs = build_messages("I will analyze the task.")
    assert assistant_msgs == [{"role": "assistant", "content": "I will analyze the task."}]

    # NodePayload
    payload = NodePayload(payload_type="decision", content="approved")
    payload_msgs = build_messages(payload)
    assert payload_msgs[0]["role"] == "assistant"

    # NodeInput
    node_input = NodeInput(input_type="initial", payloads=[payload])
    node_msgs = build_messages(node_input)
    assert len(node_msgs) == 1

    # list[dict] passthrough
    prebuilt = [{"role": "user", "content": "hello"}]
    passthrough_msgs = build_messages(prebuilt)
    assert passthrough_msgs is prebuilt
```

### Key Test Scenarios

- [ ] **Scenario 1**: Full node handoff — construct NodePayload → wrap in NodeInput → serialize → deserialize → convert to messages. Verifies the complete transport pipeline.
- [ ] **Scenario 2**: NodeInputLike union type — mock node accepts any NodeInputLike variant and converts correctly. Verifies the flexible input API.
- [ ] **Edge case**: Empty payloads and empty messages — verify `to_messages()` returns empty list.

## Verification Plan

**Estimated time**: ~1 hour

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for StateObject — test `to_dict()`, `from_dict()`, `to_json()`, `from_json()` round-trip, missing field validation, invalid JSON handling
- [ ] Unit tests for NodePayload — test construction, defaults, `to_message()` with all content types, `to_messages()`, serialization round-trip
- [ ] Unit tests for NodeInput — test construction, defaults, `to_messages()` with various combinations, serialization round-trip with nested payloads
- [ ] Unit tests for `convert_node_input_to_messages()` — test all NodeInputLike variants, source parameter, empty inputs
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Import all new types from `tinycua.models` and verify they are accessible
- [ ] Verify `NodePayload.to_message()` produces valid assistant-role message dicts
- [ ] Verify `NodeInput.to_messages()` order: payloads first, then messages

### Performance Considerations

- [ ] Not applicable — pure data structures with no I/O

## Proposed Changes

**Estimated time**: ~4 hours

### Models Module

#### [NEW] `tinycua/models/state_object.py`

- **Description**: `StateObject` base class with `to_dict()`, `from_dict()`, `to_json()`, `from_json()` methods
- **Dependencies**: `dataclasses`, `json`, `typing` (stdlib only)
- **Rationale**: Provides serialization base for all TinyCUA model dataclasses

#### [NEW] `tinycua/models/node_payload.py`

- **Description**: `NodePayload` dataclass extending `StateObject` with `payload_type`, `source_node`, `content`, `metadata` fields and `to_message()`, `to_messages()` methods
- **Dependencies**: `state_object.py`
- **Rationale**: Internal transport envelope for a single node's structured output

#### [NEW] `tinycua/models/node_input.py`

- **Description**: `NodeInput` dataclass extending `StateObject`, `NodeInputLike` type alias, and `convert_node_input_to_messages()` function
- **Dependencies**: `state_object.py`, `node_payload.py`
- **Rationale**: Internal transport envelope for node-to-node handoff with flexible input conversion

#### [MODIFY] `tinycua/models/__init__.py`

- **Description**: Add exports for `StateObject`, `NodePayload`, `NodeInput`, `NodeInputLike`, `convert_node_input_to_messages`
- **Breaking changes**: None — additive only

### Tests

#### [NEW] `tests/unit/test_state_object.py`

- **Description**: Unit tests for `StateObject` base class serialization round-trip, missing field validation, invalid JSON handling

#### [NEW] `tests/unit/test_node_payload.py`

- **Description**: Unit tests for `NodePayload` construction, defaults, `to_message()` with all content types, `to_messages()`, serialization

#### [NEW] `tests/unit/test_node_input.py`

- **Description**: Unit tests for `NodeInput` construction, defaults, `to_messages()`, serialization, `convert_node_input_to_messages()` with all variants

#### [NEW] `tests/integration/test_node_transport.py`

- **Description**: Integration tests for full node handoff pipeline and NodeInputLike union type

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/models/state_object.py` | New | `StateObject` base class with dict/JSON serialization |
| `tinycua/models/node_payload.py` | New | `NodePayload` transport envelope for node output |
| `tinycua/models/node_input.py` | New | `NodeInput` transport envelope, `NodeInputLike`, `convert_node_input_to_messages()` |
| `tinycua/models/__init__.py` | Modified | Export new types |

## Data Model Changes

```python
# New types
StateObject:
    to_dict() -> dict
    from_dict(data: dict) -> Self
    to_json(**json_kwargs) -> str
    from_json(json_str: str) -> Self

NodePayload(StateObject):
    payload_type: str
    source_node: str | None = None
    content: str | dict | StateObject | list[dict] = ""
    metadata: dict = field(default_factory=dict)
    to_message() -> dict
    to_messages() -> list[dict]

NodeInput(StateObject):
    input_type: str
    source_node: str | None = None
    target_node: str | None = None
    messages: list[dict] = field(default_factory=list)
    payloads: list[NodePayload] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    to_messages() -> list[dict]

NodeInputLike = str | NodeInput | NodePayload | list[dict]

convert_node_input_to_messages(node_input: NodeInputLike, *, source: Literal["external", "internal"] = "internal") -> list[dict]
```

## API Changes

### New Exports from `tinycua.models`

| Name | Type | Description |
|------|------|-------------|
| `StateObject` | Class | Serialization base for model dataclasses |
| `NodePayload` | Dataclass | Internal transport envelope for node output |
| `NodeInput` | Dataclass | Internal transport envelope for node handoff |
| `NodeInputLike` | TypeAlias | Union type for flexible node input |
| `convert_node_input_to_messages` | Function | Converts any NodeInputLike to message dicts |

### No Modified Endpoints

None — this is a new module addition with no changes to existing APIs.

## Dependencies

### External Dependencies

None — stdlib only (`dataclasses`, `json`, `typing`).

### Internal Dependencies

- [ ] Depends on existing `Session` model format (message dicts) — compatible by design
- [ ] Blocks Milestone 1.5 (concrete node implementations)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `dataclasses.asdict()` doesn't handle all nested types correctly | Medium | Unit tests with nested `StateObject` subclasses verify round-trip |
| `from_dict()` type introspection fails for complex generic types | Medium | Test with `list[NodePayload]`, `str | None`, and `dict` field types |
| `NodePayload.to_message()` content serialization ambiguity | Low | Document exact serialization per content type; test all four content types |
| Incompatibility with existing `Session.session_context` format | High | `NodeInput.to_messages()` produces standard `list[dict]` matching existing format |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-07*
