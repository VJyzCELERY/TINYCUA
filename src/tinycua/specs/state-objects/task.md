# Tasks: State Objects, NodeInput, NodePayload (Milestone 1.4)

**Status**: Reviewed (derived from spec.md and design.md)

Implementation tasks for State Objects, NodeInput, NodePayload. Check off items as completed.

**Phase Order**: Phases must be executed in order: TDD → Implementation → Testing → Verification → Documentation → Review and Merge. Each phase depends on the previous phase completing successfully.

## TDD Phase (Tests First)

- [ ] Write integration tests for node transport (`tests/integration/test_node_transport.py`) <!-- id: 0 -->
- [ ] Write unit tests for StateObject (`tests/unit/test_state_object.py`) <!-- id: 1 -->
- [ ] Write unit tests for NodePayload (`tests/unit/test_node_payload.py`) <!-- id: 2 -->
- [ ] Write unit tests for NodeInput and convert_node_input_to_messages (`tests/unit/test_node_input.py`) <!-- id: 3 -->
- [ ] Run all new tests — expect RED (failures) since no implementation yet <!-- id: 4 -->

## Implementation Phase

- [ ] Create `tinycua/models/state_object.py` with `StateObject` base class <!-- id: 5 -->
  - [ ] Implement `to_dict()` using `dataclasses.asdict()`
  - [ ] Implement `from_dict()` with type introspection for nested StateObject subclasses
  - [ ] Implement `to_json()` delegating to `to_dict()` → `json.dumps()`
  - [ ] Implement `from_json()` delegating to `json.loads()` → `from_dict()`
- [ ] Create `tinycua/models/node_payload.py` with `NodePayload` dataclass <!-- id: 6 -->
  - [ ] Define fields: `payload_type`, `source_node`, `content`, `metadata` with defaults
  - [ ] Implement `to_message()` with content serialization for str/dict/StateObject/list[dict]
  - [ ] Implement `to_messages()` returning single-element list from `to_message()`
- [ ] Create `tinycua/models/node_input.py` with `NodeInput`, `NodeInputLike`, `convert_node_input_to_messages()` <!-- id: 7 -->
  - [ ] Define `NodeInput` fields: `input_type`, `source_node`, `target_node`, `messages`, `payloads`, `metadata` with defaults
  - [ ] Implement `NodeInput.to_messages()` — payloads as assistant messages then messages list
  - [ ] Define `NodeInputLike = str | NodeInput | NodePayload | list[dict]`
  - [ ] Implement `convert_node_input_to_messages()` with source parameter
- [ ] Update `tinycua/models/__init__.py` to export new types <!-- id: 8 -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 9 -->
- [ ] Run unit tests for StateObject — expect GREEN <!-- id: 10 -->
- [ ] Run unit tests for NodePayload — expect GREEN <!-- id: 11 -->
- [ ] Run unit tests for NodeInput — expect GREEN <!-- id: 12 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` — no regressions <!-- id: 13 -->

## Verification Phase

- [ ] Import all new types from `tinycua.models` and verify accessibility <!-- id: 14 -->
- [ ] Verify round-trip serialization: `to_json()` → `from_json()` preserves all fields <!-- id: 15 -->
- [ ] Verify `NodePayload.to_message()` produces valid assistant-role message dicts <!-- id: 16 -->
- [ ] Verify `convert_node_input_to_messages()` handles all NodeInputLike variants <!-- id: 17 -->

## Documentation Phase

- [ ] Verify spec.md success criteria checkboxes match implementation <!-- id: 18 -->
- [ ] Verify design.md error handling table matches implementation <!-- id: 18a -->
- [ ] Verify public API exports match design.md export list <!-- id: 18b -->
- [ ] Add docstrings to StateObject, NodePayload, NodeInput, convert_node_input_to_messages <!-- id: 18c -->

## Review and Merge

- [x] Create pull request <!-- id: 19 --> (PR #95 already exists)
- [ ] Address review feedback <!-- id: 20 -->
- [ ] Merge to base branch <!-- id: 21 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-07*
