# Tasks: WorkerNode Information-Digestion via QueryAnalyst

Implementation tasks for WorkerNode Information-Digestion via QueryAnalyst. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write DigestedInformation model unit tests (`test_digested_information_model.py`) <!-- id: 1 -->
  - [x] Test dataclass field defaults and construction
  - [x] Test `fallback()` classmethod produces correct context_summary with original query
  - [x] Test `has_useful_context` property returns True when key_points/advisory_instructions/constraints exist
  - [x] Test `has_useful_context` returns False for fallback-only instances
- [x] Write QueryAnalyst worker route tests (`test_query_analyst_worker_digest.py`) <!-- id: 2 -->
  - [x] Test `_route_worker` spawns InformationDigesterNode before WorkerNode via `queue.spawn_after_current()`
  - [x] Test `_check_existing_digest` returns True when DigestedInformation exists in target Worker's session_context
  - [x] Test `_check_existing_digest` returns False when no digest present
  - [x] Test `_extract_user_query` extracts last user message from input messages
  - [x] Test no duplicate digester spawned when digest already exists
- [x] Write InformationDigesterNode tests (`test_information_digester_node.py`) <!-- id: 3 -->
  - [x] Test fresh session creation (does not inherit parent session_id)
  - [x] Test fallback produces DigestedInformation.fallback(original_query) when no useful context
  - [x] Test propagate() outputs DigestedInformation to session_context
- [x] Write WorkerNode digest integration tests (`test_worker_digested_information.py`) <!-- id: 4 -->
  - [x] Test `_get_digested_input` returns DigestedInformation from session_context when present
  - [x] Test `_get_digested_input` returns None when no digest in session_context
  - [x] Test `propagate()` forwards DigestedInformation to session_context for downstream nodes
  - [x] Test WorkerNode gracefully handles missing DigestedInformation (fallback to raw query)
- [x] Write TaskCreateNode digested input tests (`test_task_create_digested_information.py`) <!-- id: 5 -->
  - [x] Test `build_messages()` includes DigestedInformation from Worker propagate() output
  - [x] Test TaskCreateNode falls back to raw user_query when no DigestedInformation present
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 6 -->

## Implementation Phase

- [x] Implement `tinycua/models/digested_information.py` <!-- id: 7 -->
  - [x] Define `DigestedInformation` dataclass with all fields
  - [x] Implement `fallback()` classmethod
  - [x] Implement `has_useful_context` property
- [x] Update `tinycua/models/__init__.py` to export DigestedInformation <!-- id: 8 -->
- [x] Implement `tinycua/loops/information_digester.py` <!-- id: 9 -->
  - [x] Create `TinyCUAInformationDigesterNode(ProcessNode)` class
  - [x] Implement fresh session creation in `ensure_session()` override
  - [x] Implement fallback behavior: produce DigestedInformation.fallback(original_query)
  - [x] Implement propagate() to output DigestedInformation to session_context
- [x] Implement `tinycua/loops/query_analyst.py` <!-- id: 10 -->
  - [x] Create `TinyCUAQueryAnalystNode(DecisionNode)` class
  - [x] Implement `_route_worker()` that spawns InformationDigesterNode before WorkerNode
  - [x] Implement `_check_existing_digest()` for deduplication logic
  - [x] Implement `_extract_user_query()` to get original query from input messages
  - [x] Wire worker route into DecisionNode dispatch via `on_complete()`
- [x] Implement `tinycua/loops/worker.py` <!-- id: 11 -->
  - [x] Create `TinyCUAWorkerNode(DecisionNode)` class
  - [x] Implement `_get_digested_input()` to read DigestedInformation from session_context
  - [x] Implement `propagate()` to forward DigestedInformation to downstream nodes
- [x] Implement `tinycua/loops/task_create.py` <!-- id: 12 -->
  - [x] Create `TinyCUATaskCreateNode(ProcessNode)` class
  - [x] Implement `build_messages()` to accept DigestedInformation from Worker
  - [x] Include DigestedInformation in LLM message assembly for root task creation
- [x] Update `tinycua/loops/__init__.py` to export new node classes <!-- id: 13 -->
- [x] Wire QueryAnalyst as entry node in `tinycua_loop.py` queue bootstrap, replacing the current Worker entry point <!-- id: 14 -->

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 15 -->
- [x] Run DigestedInformation model unit tests <!-- id: 16 -->
- [x] Run QueryAnalyst worker route unit tests <!-- id: 17 -->
- [x] Run InformationDigesterNode unit tests <!-- id: 18 -->
- [x] Run WorkerNode digest unit tests <!-- id: 19 -->
- [x] Run TaskCreateNode digested input unit tests <!-- id: 20 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 21 -->
- [ ] Write end-to-end integration test with MockLLM for full pipeline flow (`test_pipeline_integration.py`) <!-- id: 22 -->
  - [ ] Test QueryAnalyst → InformationDigester → Worker → TaskCreate with mock LLM responses
  - [ ] Test digester failure produces fallback and Worker proceeds normally

## Verification Phase

- [ ] Verify queue transitions match design.md diagrams for fresh spawn case <!-- id: 23 -->
- [ ] Verify queue transitions match design.md diagrams for reused Worker with existing digest <!-- id: 24 -->
- [ ] Verify DigestedInformation serialization/deserialization works with session_context <!-- id: 25 -->
- [ ] Verify no regressions in existing loop tests <!-- id: 26 -->

## Documentation Phase

- [ ] Update `specs/tinycua-worker-digestion/spec.md` Status Tracker to reflect completion <!-- id: 27 -->
- [ ] Update README if needed <!-- id: 28 -->
- [ ] Update changelog <!-- id: 29 -->

## Review and Merge

- [ ] Update PR #119 description with final implementation details <!-- id: 30 -->
- [ ] Address review feedback <!-- id: 31 -->
- [ ] Merge PR to feat/tinycua-research-prototype <!-- id: 32 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-12*
