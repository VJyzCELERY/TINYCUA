# Tasks: State Objects, NodeInput, NodePayload (Milestone 1.4)

**Status**: Reviewed (derived from spec.md and design.md)

Implementation tasks for State Objects, NodeInput, NodePayload. Check off items as completed.

**Phase Order**: Phases must be executed in order: TDD → Implementation → Testing → Verification → Documentation → Review and Merge. Each phase depends on the previous phase completing successfully.

## TDD Phase (Tests First)

- [x] Write integration tests for node transport (`tests/integration/test_node_transport.py`) <!-- id: 0 -->
- [x] Write unit tests for StateObject (`tests/unit/test_state_object.py`) <!-- id: 1 -->
- [x] Write unit tests for NodePayload (`tests/unit/test_node_payload.py`) <!-- id: 2 -->
- [x] Write unit tests for NodeInput and convert_node_input_to_messages (`tests/unit/test_node_input.py`) <!-- id: 3 -->
- [x] Run all new tests — expect RED (failures) since no implementation yet <!-- id: 4 -->

## Implementation Phase

- [x] Create `tinycua/models/state_object.py` with `StateObject` base class <!-- id: 5 -->
  - [x] Implement `to_dict()` using `dataclasses.asdict()`
  - [x] Implement `from_dict()` with type introspection for nested StateObject subclasses
  - [x] Implement `to_json()` delegating to `to_dict()` → `json.dumps()`
  - [x] Implement `from_json()` delegating to `json.loads()` → `from_dict()`
- [x] Create `tinycua/models/node_payload.py` with `NodePayload` dataclass <!-- id: 6 -->
  - [x] Define fields: `payload_type`, `source_node`, `content`, `metadata` with defaults
  - [x] Implement `to_message()` with content serialization for str/dict/StateObject/list[dict]
  - [x] Implement `to_messages()` returning single-element list from `to_message()`
- [x] Create `tinycua/models/node_input.py` with `NodeInput`, `NodeInputLike`, `convert_node_input_to_messages()` <!-- id: 7 -->
  - [x] Define `NodeInput` fields: `input_type`, `source_node`, `target_node`, `messages`, `payloads`, `metadata` with defaults
  - [x] Implement `NodeInput.to_messages()` — payloads as assistant messages then messages list
  - [x] Define `NodeInputLike = str | NodeInput | NodePayload | list[dict]`
  - [x] Implement `convert_node_input_to_messages()` with source parameter
- [x] Update `tinycua/models/__init__.py` to export new types <!-- id: 8 -->

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 9 -->
- [x] Run unit tests for StateObject — expect GREEN <!-- id: 10 -->
- [x] Run unit tests for NodePayload — expect GREEN <!-- id: 11 -->
- [x] Run unit tests for NodeInput — expect GREEN <!-- id: 12 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` — no regressions <!-- id: 13 -->

## Verification Phase

- [x] Import all new types from `tinycua.models` and verify accessibility <!-- id: 14 -->
- [x] Verify round-trip serialization: `to_json()` → `from_json()` preserves all fields <!-- id: 15 -->
- [x] Verify `NodePayload.to_message()` produces valid assistant-role message dicts <!-- id: 16 -->
- [x] Verify `convert_node_input_to_messages()` handles all NodeInputLike variants <!-- id: 17 -->

## Documentation Phase

- [x] Verify spec.md success criteria checkboxes match implementation <!-- id: 18 -->
- [x] Verify design.md error handling table matches implementation <!-- id: 18a -->
- [x] Verify public API exports match design.md export list <!-- id: 18b -->
- [x] Add docstrings to StateObject, NodePayload, NodeInput, convert_node_input_to_messages <!-- id: 18c -->

## Review and Merge

- [x] Create pull request <!-- id: 19 --> (PR #95 already exists)
- [ ] Address review feedback <!-- id: 20 -->
- [ ] Merge to base branch <!-- id: 21 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-07*
