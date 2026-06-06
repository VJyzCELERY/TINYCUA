# Design Document: State Objects, NodeInput, NodePayload (Milestone 1.4)

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-07

---

## Overview

Implement the internal transport layer for TinyCUA node communication. `StateObject` provides the serialization base class for all TinyCUA model dataclasses. `NodePayload` wraps a single node's structured output for internal transport. `NodeInput` wraps the full handoff envelope between nodes (payloads + continuation messages). `NodeInputLike` is a union type enabling flexible input from external users, internal nodes, or pre-constructed message lists. The `convert_node_input_to_messages()` function converts any `NodeInputLike` variant to a list of LLM message dicts. No untrusted string parsing is used for internal transport — `NodeInput` and `NodePayload` are trusted typed objects.

---

## Architecture

### Component Overview

```
[Node A output]
    → NodePayload (structured content)
    → NodeInput (payloads + messages + metadata)
    → convert_node_input_to_messages() → list[dict]
    → [Node B input]
```

### Affected Components

> **Note**: These are planned implementation changes, not changes in this docs-only PR.

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/models/state_object.py` | New | `StateObject` base class with serialization |
| `tinycua/models/node_payload.py` | New | `NodePayload` transport envelope |
| `tinycua/models/node_input.py` | New | `NodeInput` transport envelope, `NodeInputLike`, `convert_node_input_to_messages()` |
| `tinycua/models/__init__.py` | Modified | Export new types |

---

## Data Model

### StateObject Base Class

```python
@dataclass
class StateObject:
    """Serialization base for TinyCUA model dataclasses."""

    def to_dict(self) -> dict:
        """Serialize to dictionary. Nested StateObject instances are recursively converted."""
        ...

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Reconstruct from dictionary. Nested dicts are recursively deserialized."""
        ...

    def to_json(self, **json_kwargs) -> str:
        """Serialize to JSON string via to_dict() → json.dumps()."""
        ...

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Reconstruct from JSON string via json.loads() → from_dict()."""
        ...
```

Implementation uses `dataclasses.asdict()` for `to_dict()` and per-field construction with `typing.get_type_hints()` introspection for `from_dict()` to auto-convert nested `StateObject` subclasses.

### NodePayload

```python
@dataclass
class NodePayload(StateObject):
    """Internal transport envelope for a single node's structured output."""

    payload_type: str                     # e.g., "task_analysis", "reviewer_decision"
    source_node: str | None = None        # originating node id
    content: str | dict | StateObject | list[dict] = ""  # polymorphic content
    metadata: dict = field(default_factory=dict)

    def to_message(self) -> dict:
        """Convert to a single assistant-role message dict.

        Content serialization:
        - str → used directly as content
        - dict → serialized via json.dumps()
        - StateObject → serialized via .to_json()
        - list[dict] → serialized via json.dumps()
        """
        ...

    def to_messages(self) -> list[dict]:
        """Return single-element list from to_message()."""
        return [self.to_message()]
```

### NodeInput

```python
@dataclass
class NodeInput(StateObject):
    """Internal transport envelope for node-to-node handoff."""

    input_type: str                       # e.g., "continuation", "initial"
    source_node: str | None = None        # originating node id
    target_node: str | None = None        # intended recipient node id
    messages: list[dict] = field(default_factory=list)   # continuation messages
    payloads: list[NodePayload] = field(default_factory=list)  # structured payloads
    metadata: dict = field(default_factory=dict)

    def to_messages(self) -> list[dict]:
        """Convert to list of message dicts.

        Order: payloads converted via NodePayload.to_message(),
        then self.messages appended in order.
        """
        ...
```

### NodeInputLike and Conversion

```python
NodeInputLike = str | NodeInput | NodePayload | list[dict]

def convert_node_input_to_messages(
    node_input: NodeInputLike,
    *,
    source: Literal["external", "internal"] = "internal",
) -> list[dict]:
    """Convert any NodeInputLike variant to a list of message dicts.

    Conversion rules:
    - str + source="external" → [{"role": "user", "content": text}]
    - str + source="internal" → [{"role": "assistant", "content": text}]
    - NodeInput → node_input.to_messages()
    - NodePayload → node_payload.to_messages()
    - list[dict] → passed through directly
    """
    ...
```

### Schema Changes

None — this is a new module addition. Existing `Session` model is not modified; `NodeInput`/`NodePayload` are separate transport types that produce message dicts compatible with `Session.session_context`.

---

## API / Interface Contracts

### Public API: `tinycua.models` package additions

```python
from tinycua.models import (
    # Existing
    Session,
    Todo,
    TodoItem,
    # New in M1.4
    StateObject,
    NodePayload,
    NodeInput,
    NodeInputLike,
    convert_node_input_to_messages,
)
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Missing field in `from_dict()` | `ValueError` | Lists missing required field name |
| Invalid JSON in `from_json()` | `json.JSONDecodeError` | Propagated from stdlib |
| Type mismatch in `from_dict()` | `TypeError` | Incompatible type for field |
| `NodePayload.to_message()` with unknown content type | `TypeError` | Unsupported content type |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create `tinycua/models/state_object.py` with `StateObject` base class
- [ ] Create `tinycua/models/node_payload.py` with `NodePayload` dataclass
- [ ] Create `tinycua/models/node_input.py` with `NodeInput`, `NodeInputLike`, `convert_node_input_to_messages()`
- [ ] Update `tinycua/models/__init__.py` to export new types
- [ ] Write unit tests for `StateObject` base class serialization
- [ ] Write unit tests for `NodePayload` construction, `to_message()`, `to_messages()`, serialization
- [ ] Write unit tests for `NodeInput` construction, `to_messages()`, serialization
- [ ] Write unit tests for `convert_node_input_to_messages()` with all variants
- [ ] Write integration test for node handoff via `NodeInput`/`NodePayload`
- [ ] Run `uv run pytest` — all tests pass

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

None — Phase 1 covers the full M1.4 scope.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: `StateObject` uses `dataclasses.asdict()` for `to_dict()` and introspection-based `from_dict()`.
   - **Reason**: Zero external dependencies. `dataclasses.asdict()` handles recursive serialization of nested dataclasses automatically. `from_dict()` uses `typing.get_type_hints()` + `dataclasses.fields()` to auto-convert nested `StateObject` instances.
   - **Alternatives Considered**: Pydantic — rejected for dependency overhead. Manual serialization — rejected for maintenance burden with nested types.

2. **Decision**: `NodePayload.content` is polymorphic (`str | dict | StateObject | list[dict]`) rather than a single type.
   - **Reason**: Nodes produce different output shapes. A task analyzer produces a structured dict/object; a simple process node produces a string; an aggregation node produces a list of messages. The transport should accommodate all without forcing conversion at the node boundary.
   - **Alternatives Considered**: Always require `dict` — rejected for forcing unnecessary serialization in simple cases. Always require `StateObject` — rejected for not covering pre-constructed message lists.

3. **Decision**: `convert_node_input_to_messages()` accepts a `source` parameter to distinguish external vs internal strings.
   - **Reason**: External user strings must become user-role messages; internal node strings must become assistant-role messages. The conversion function handles this cleanly rather than requiring callers to wrap strings manually.
   - **Alternatives Considered**: Caller always wraps strings — rejected for being error-prone and duplicating conversion logic across nodes.

4. **Decision**: `NodePayload.to_message()` always produces assistant-role messages.
   - **Reason**: Node payloads are internal node outputs. The architecture design doc specifies that internal TinyCUA node communication is assistant-role continuation. External user input is handled separately via the `source="external"` path in `convert_node_input_to_messages()`.
   - **Alternatives Considered**: Configurable role — rejected for adding unnecessary complexity; the role is always assistant for internal payloads by architectural contract.

5. **Decision**: `list[dict]` content in `NodePayload` is serialized as a JSON array string within the assistant message, not split into multiple messages.
   - **Reason**: Preserves the structure for downstream consumers who need to deserialize it back. Splitting would lose the grouping semantics.
   - **Alternatives Considered**: Split into multiple messages — rejected for losing structure and complicating deserialization.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `dataclasses.asdict()` doesn't handle all nested types correctly | Low | Medium | Unit tests with nested `StateObject` subclasses verify round-trip |
| `from_dict()` type introspection fails for complex generic types | Low | Medium | Test with `list[NodePayload]`, `str | None`, and `dict` field types |
| `NodePayload.to_message()` content serialization ambiguity | Medium | Low | Document exact serialization per content type; test all four content types |
| Incompatibility with existing `Session.session_context` format | Low | High | `NodeInput.to_messages()` produces standard `list[dict]` matching existing format |

---

## Open Questions _(optional)_

See also: [spec.md Open Questions](spec.md#open-questions-optional) for API-level decisions.

1. **Should `StateObject` validate required fields in `__post_init__`?**
   - Currently not planned — `from_dict()` handles missing field validation. `StateObject` subclasses that need runtime validation (e.g., enum checks) should implement their own `__post_init__`.
   - **Status**: Proposed

2. **Should `NodePayload` support `content` as `None`?**
   - Allowed by the type signature. `to_message()` would produce `{"role": "assistant", "content": ""}` (empty string) for LLM provider compatibility.
   - **Status**: Proposed

---

## References

- Spec: `./spec.md`
- Architecture state objects: `src/tinycua/docs/design/models/state_object.md`
- Architecture node design: `src/tinycua/docs/design/loops/node.md`
- Architecture propagation: `src/tinycua/docs/design/loops/propagation.md`
- Existing session model: `src/tinycua/tinycua/models/session.py`
