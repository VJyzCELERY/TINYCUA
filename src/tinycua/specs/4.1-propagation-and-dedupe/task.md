# Tasks: Propagation and Dedupe (Milestone 4.1)

Implementation tasks for Propagation and Dedupe. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for propagation, dedupe, terminal output, and ChatRecord in `tests/test_propagation.py` <!-- id: 0 -->
- [ ] Write unit tests for ChatRecord in `tests/test_chat_record.py` <!-- id: 1 -->
- [ ] Write unit tests for SessionContextEntry in `tests/test_session_context_entry.py` <!-- id: 2 -->
- [ ] Run all new tests — expect RED (failures) since no implementation exists yet <!-- id: 3 -->

## Implementation Phase — Data Models

- [ ] Create `src/tinycua/tinycua/models/chat_record.py` — ChatRecord dataclass with all metadata fields <!-- id: 4 -->
  - [ ] Define record_id (uuid4), role, record_type, content, visibility fields
  - [ ] Define source_node_id, source_session_id, receiver_node_id, receiver_session_id, origin_record_id fields
  - [ ] Define created_seq and metadata fields
  - [ ] Add to_dict() / from_dict() serialization (extend StateObject pattern)
- [ ] Create `src/tinycua/tinycua/models/session_context_entry.py` — SessionContextEntry with segment metadata <!-- id: 5 -->
  - [ ] Define segment field (prior | input | output)
  - [ ] Define origin_record_id, source_node_id, source_session_id, created_seq fields
  - [ ] Add to_dict() / from_dict() serialization
- [ ] Update `src/tinycua/tinycua/models/session.py` — separate chat_history and session_context types <!-- id: 6 -->
  - [ ] Change chat_history type to list[ChatRecord]
  - [ ] Change session_context type to list[SessionContextEntry]
  - [ ] Update compact_context() to work with new types
- [ ] Update `src/tinycua/tinycua/models/__init__.py` — re-export ChatRecord and SessionContextEntry <!-- id: 7 -->

## Implementation Phase — Propagation Engine

- [ ] Create `src/tinycua/tinycua/loops/propagation.py` — core propagation logic <!-- id: 8 -->
  - [ ] Implement PropagationRule dataclass with all fields
  - [ ] Implement PROPAGATION_PROFILES dict with all four profiles
  - [ ] Implement propagate_on_termination() — upward propagation of prior+input segments
  - [ ] Implement forward_output_to_next() — output segment forwarding
  - [ ] Implement finalize_terminal_output() — terminal output exception
  - [ ] Implement dedupe_records() — origin_record_id comparison with record_id fallback

## Implementation Phase — Integration

- [ ] Update `src/tinycua/tinycua/config/node_config.py` — wire PropagationRule and dedupe <!-- id: 9 -->
  - [ ] Change NodeConfigBase.propagation type from Any to PropagationRule | None
  - [ ] Verify NodeMessagePolicy.dedupe_by_origin_record_id is wired
- [ ] Add `build_messages_with_dedupe()` helper to `src/tinycua/tinycua/loops/node.py` <!-- id: 10 -->
  - [ ] Filter session_context by origin_record_id when dedupe flag is True
- [ ] Update `src/tinycua/tinycua/loops/tinycua_loop.py` — integrate propagation engine <!-- id: 11 -->
  - [ ] Replace _transfer_session_context() with propagate_on_termination() call
  - [ ] Wire terminal output exception in _run_sync()/_run_stream() finalization
  - [ ] Apply dedupe_by_origin_record_id in _build_node_messages()
  - [ ] Update _record_node_output() to append ChatRecord to chat_history
- [ ] Update `src/tinycua/tinycua/loops/node_queue.py` — propagation hooks on termination <!-- id: 12 -->
  - [ ] Update advance() to handle output forwarding via forward_output_to_next()
- [ ] Update `src/tinycua/tinycua/loops/information_digester.py` — segment-aware propagation <!-- id: 13 -->
  - [ ] Update propagate() to use SessionContextEntry with segment="output"
- [ ] Update `src/tinycua/tinycua/loops/worker.py` — segment-aware propagation <!-- id: 14 -->
  - [ ] Update propagate() to use SessionContextEntry with segment metadata

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 15 -->
- [ ] Run unit tests for ChatRecord and SessionContextEntry <!-- id: 16 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` — confirm no regressions <!-- id: 17 -->

## Verification Phase

- [ ] Verify propagation with minimal two-node queue — inspect session_context at each step <!-- id: 18 -->
- [ ] Verify terminal output exception with ResponseNode as terminal <!-- id: 19 -->
- [ ] Verify dedupe filtering with duplicate origin_record_ids <!-- id: 20 -->
- [ ] Verify ChatRecord audit trail accumulates across node executions <!-- id: 21 -->

## Documentation Phase

- [ ] Update `src/tinycua/docs/design/loops/propagation.md` with implementation details <!-- id: 22 -->
- [ ] Update `src/tinycua/docs/design/models/chat_record.md` if it exists <!-- id: 23 -->
- [ ] Update spec.md status from Draft to In Progress <!-- id: 24 -->

## Review and Merge

- [ ] Run `/review-report` on the branch <!-- id: 25 -->
- [ ] Address review findings <!-- id: 26 -->
- [ ] Create pull request <!-- id: 27 -->
- [ ] Address PR review feedback <!-- id: 28 -->
- [ ] Merge to base branch <!-- id: 29 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-12*
