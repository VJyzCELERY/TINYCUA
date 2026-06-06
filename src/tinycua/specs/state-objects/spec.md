# Feature Specification: State Objects, NodeInput, NodePayload (Milestone 1.4)

**Status**: Reviewed
**Created**: 2026-06-07
**Last Updated**: 2026-06-07
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Provide the internal transport layer for TinyCUA node communication — `StateObject` as the serialization base, `NodePayload` for structured node output, and `NodeInput` for node-to-node handoff — so that nodes can exchange typed, structured data without parsing untrusted strings.
- **Gaps**: Currently nodes have no typed internal transport. The existing `Session` model uses raw `list[dict]` for `session_context` and `chat_history`. There is no `NodePayload` or `NodeInput` to carry structured payloads between nodes. The `NodeInputLike` union type does not exist, so callers must manually construct message dicts. The architecture design docs (`docs/design/models/state_object.md`, `docs/design/loops/node.md`) define these transport models but they are not yet implemented.
- **Non-Goals**: `ExecutionLog` recording and `AgentState` lifecycle output (deferred to later lifecycle/audit milestones). Concrete node implementations (Milestone 1.5). Propagation rules and deduplication (Milestone 4.1). Node queue mechanics (Milestone 1.6). Compaction behavior (already implemented in M1.3).
- **Constraints**: Must follow the target architecture design docs in `src/tinycua/docs/design/`. Must not modify `tinycua-sdk` public APIs. Must not introduce untrusted string parsing for internal transport — `NodeInput` and `NodePayload` are trusted internal objects. Must remain compatible with the existing `Session`, `Todo`, and `CompactionStrategy` implementations from earlier milestones.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer building a TinyCUA node constructs a `NodePayload` to represent the node's structured output (e.g., a task analysis result). The node wraps it in a `NodeInput` along with any continuation messages, and passes it to the next node. The next node receives the typed `NodeInput`, accesses the `NodePayload` directly, and converts it to LLM messages when needed. At no point is the structured data parsed from a string.

### Acceptance Scenarios

1. **Given** a `StateObject` subclass with defined fields, **When** `to_dict()` is called, **Then** a dictionary with all fields is returned. **When** `from_dict(data)` is called with that dictionary, **Then** a matching object is reconstructed.
2. **Given** a `StateObject` subclass, **When** `to_json()` is called, **Then** a valid JSON string is produced. **When** `from_json(json_str)` is called, **Then** a matching object is reconstructed.
3. **Given** a `NodePayload` with `payload_type="task_analysis"`, `content={"task_id": "T-0.1", "status": "analyzed"}`, **When** `to_message()` is called, **Then** an assistant-role message dict `{"role": "assistant", "content": ...}` is returned.
4. **Given** a `NodePayload` with `content` as a string, **When** `to_messages()` is called, **Then** a single-element list containing the assistant-role message is returned.
5. **Given** a `NodePayload` with `content` as a `StateObject`, **When** `to_messages()` is called, **Then** the content is serialized to a dict within the assistant-role message.
6. **Given** a `NodeInput` with two `NodePayload` items and one continuation message, **When** `to_messages()` is called, **Then** the payloads are converted to assistant-role messages followed by the continuation message, all in order.
7. **Given** a `NodeInput` with `source_node="TaskAnalyzer"` and `target_node="TaskExecutor"`, **When** the node input is constructed, **Then** source and target are recorded for propagation tracking.
8. **Given** an external user string `"What is the weather?"`, **When** it is converted to `NodeInput`, **Then** it becomes a user-role message `{"role": "user", "content": "What is the weather?"}` — it is NOT parsed as structured internal input.
9. **Given** an internal assistant string `"I will analyze the task."`, **When** it is used as `NodeInput`, **Then** it becomes an assistant-role message `{"role": "assistant", "content": "I will analyze the task."}`.
10. **Given** a `NodeInput` that already contains typed `NodeInput` or `NodePayload` objects, **When** it is used as `NodeInput`, **Then** the objects are passed through without string conversion.
11. **Given** a `list[dict]` of pre-constructed messages, **When** it is used as `NodeInput`, **Then** the messages are passed through directly as the node's input messages.

### Edge Cases

- What happens when `NodePayload.content` is `None`? `to_message()` produces an assistant-role message with `content=None` (or empty string, depending on LLM provider expectations — implementation chooses the safer empty string).
- What happens when `NodePayload.metadata` is empty? Defaults to `{}`.
- What happens when `NodeInput.payloads` is empty? `to_messages()` returns only the `messages` list (or empty list if both are empty).
- What happens when `NodeInput.messages` is empty? `to_messages()` returns only the converted payloads.
- What happens when `NodeInputLike` is a plain `str`? External strings become user-role messages; internal strings become assistant-role messages. The distinction is determined by the caller (node) context, not by the transport itself — the conversion function accepts a `source` parameter indicating whether the string is external (user) or internal (assistant).
- What happens when `StateObject.from_dict()` receives a dict with missing required fields? Raises `ValueError` listing the missing field.
- What happens when `StateObject.from_json()` receives invalid JSON? Propagates `json.JSONDecodeError`.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a `StateObject` base class with methods: `to_dict()`, `from_dict(data)`, `to_json()`, `from_json(json_str)`.
- **FR-002**: `StateObject.to_dict()` MUST return a dictionary representation of all dataclass fields, recursively serializing nested `StateObject` instances.
- **FR-003**: `StateObject.from_dict(data)` MUST reconstruct a typed object from a dictionary, recursively deserializing nested `StateObject` instances. MUST raise `ValueError` for missing required fields.
- **FR-004**: `StateObject.to_json()` MUST return a JSON string representation, delegating to `to_dict()` then `json.dumps()`.
- **FR-005**: `StateObject.from_json(json_str)` MUST reconstruct a typed object from a JSON string, delegating to `json.loads()` then `from_dict()`.
- **FR-006**: System MUST provide a `NodePayload` dataclass extending `StateObject` with fields: `payload_type` (str), `source_node` (str | None), `content` (str | dict | StateObject | list[dict]), `metadata` (dict).
- **FR-007**: `NodePayload.to_message()` MUST return a single assistant-role message dict `{"role": "assistant", "content": <serialized_content>}`.
- **FR-008**: `NodePayload.to_messages()` MUST return a list containing the result of `to_message()` (a single-element list).
- **FR-009**: System MUST provide a `NodeInput` dataclass extending `StateObject` with fields: `input_type` (str), `source_node` (str | None), `target_node` (str | None), `messages` (list[dict]), `payloads` (list[NodePayload]), `metadata` (dict).
- **FR-010**: `NodeInput.to_messages()` MUST return a list of message dicts: converted payloads (via `NodePayload.to_message()`) followed by `self.messages`, in order.
- **FR-011**: System MUST provide `NodeInputLike = str | NodeInput | NodePayload | list[dict]` as a type alias for flexible node input.
- **FR-012**: System MUST provide a conversion function `convert_node_input_to_messages(node_input: NodeInputLike, *, source: Literal["external", "internal"] = "internal") -> list[dict]` that converts any `NodeInputLike` variant to a list of message dicts.
- **FR-013**: When `source="external"`, string inputs MUST become user-role messages `{"role": "user", "content": <text>}`.
- **FR-014**: When `source="internal"` (default), string inputs MUST become assistant-role messages `{"role": "assistant", "content": <text>}`.
- **FR-015**: `NodeInput` and `NodePayload` inputs to `convert_node_input_to_messages()` MUST be treated as trusted internal transport — their `.to_messages()` method is called directly without string parsing.
- **FR-016**: `list[dict]` inputs to `convert_node_input_to_messages()` MUST be passed through directly as the message list.
- **FR-017**: All `StateObject` subclasses MUST support round-trip serialization via `to_dict()`/`from_dict()` and `to_json()`/`from_json()`.
- **FR-018**: `NodePayload` MUST default `source_node` to `None` and `metadata` to `{}`.
- **FR-019**: `NodeInput` MUST default `source_node`, `target_node` to `None` and `metadata` to `{}`.
- **FR-020**: `NodePayload.content` serialization in `to_message()` MUST handle `str`, `dict`, `StateObject` (via `.to_dict()`), and `list[dict]` content types correctly.

### Key Entities _(include if feature involves data)_

- **StateObject**: Serialization base class for all TinyCUA model dataclasses. Provides `to_dict()`, `from_dict()`, `to_json()`, `from_json()`.
- **NodePayload**: Internal transport envelope for a single node's structured output. Contains `payload_type`, `source_node`, `content` (polymorphic), and `metadata`. Converts to assistant-role LLM messages.
- **NodeInput**: Internal transport envelope for node-to-node handoff. Contains `input_type`, `source_node`, `target_node`, `messages`, `payloads`, and `metadata`. Converts to a list of LLM messages.
- **NodeInputLike**: Union type alias `str | NodeInput | NodePayload | list[dict]` enabling flexible node input from external users, internal nodes, or pre-constructed messages.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

> **Note**: These criteria define implementation success. Checkboxes will be verified during implementation — see `task.md` for tracking.

- [ ] **StateObject base exists**: `StateObject` class with `to_dict()`, `from_dict()`, `to_json()`, `from_json()`.
- [ ] **NodePayload exists**: `NodePayload` dataclass with documented fields and defaults.
- [ ] **NodeInput exists**: `NodeInput` dataclass with documented fields and defaults.
- [ ] **NodeInputLike type alias exists**: `NodeInputLike = str | NodeInput | NodePayload | list[dict]`.
- [ ] **NodePayload.to_message() works**: Returns assistant-role message dict with serialized content.
- [ ] **NodePayload.to_messages() works**: Returns single-element list from `to_message()`.
- [ ] **NodeInput.to_messages() works**: Returns payloads as assistant messages followed by messages list.
- [ ] **convert_node_input_to_messages() works**: Handles all `NodeInputLike` variants correctly.
- [ ] **External string conversion works**: Strings become user-role messages when `source="external"`.
- [ ] **Internal string conversion works**: Strings become assistant-role messages when `source="internal"`.
- [ ] **Round-trip serialization works**: `StateObject` subclasses survive `to_dict()`/`from_dict()` and `to_json()`/`from_json()`.
- [ ] **No untrusted string parsing**: `NodeInput` and `NodePayload` are never parsed from strings for internal transport.
- [ ] **Unit tests pass**: All transport conversion and serialization tests pass.
- [ ] **Integration with Session model**: `NodeInput`/`NodePayload` work with existing `Session.session_context` message format.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `StateObject` base class: `to_dict()`, `from_dict()`, `to_json()`, `from_json()` round-trip for a test subclass.
- `StateObject.from_dict()` with missing required fields raises `ValueError`.
- `StateObject.from_json()` with invalid JSON raises `json.JSONDecodeError`.
- `NodePayload` construction with all fields and defaults.
- `NodePayload.to_message()` with string content, dict content, `StateObject` content, and `list[dict]` content.
- `NodePayload.to_messages()` returns single-element list.
- `NodePayload` round-trip serialization.
- `NodeInput` construction with all fields and defaults.
- `NodeInput.to_messages()` with payloads only, messages only, both, and empty.
- `NodeInput` round-trip serialization with nested `NodePayload` items.
- `convert_node_input_to_messages()` with `str` (external), `str` (internal), `NodeInput`, `NodePayload`, `list[dict]`, and `None` payloads.
- `convert_node_input_to_messages()` with empty inputs returns empty list.

### Integration Tests

- `NodeInput` carrying a `NodePayload` through a mock node handoff: construct → serialize → deserialize → convert to messages.
- `NodeInputLike` union type used in a mock node `build_messages()` method.

### Manual Tests _(if applicable)_

- None in scope — all tests are unit/integration.

---

## Open Questions _(optional)_

See also: [design.md Open Questions](design.md#open-questions-optional) for implementation-level decisions.

1. **NodePayload.content serialization for `list[dict]`**: Should `list[dict]` content be stored as-is in the assistant message, or should each dict be treated as a separate message?
   - **Owner**: @VJyzCELERY
   - **Status**: Resolved — see design.md for decisions.
   - **Proposed Answer**: Store as-is — `list[dict]` is already a message list format; wrapping it in a single assistant message preserves the structure for downstream consumers.

2. **convert_node_input_to_messages source parameter**: Should the conversion function accept a `source` parameter to distinguish external vs internal strings, or should the caller always wrap strings before calling?
   - **Owner**: @VJyzCELERY
   - **Status**: Resolved — see design.md for decisions.
   - **Proposed Answer**: Accept a `source` parameter for convenience; default to `"internal"` (assistant-role) since most node-to-node communication is internal.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
