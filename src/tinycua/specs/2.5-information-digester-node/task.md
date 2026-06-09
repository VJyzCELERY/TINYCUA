# Tasks: TinyCUAInformationDigesterNode

Implementation tasks for TinyCUAInformationDigesterNode. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write 4 end-to-end integration tests for InformationDigesterNode (spec-aligned; defined in implementation-plan.md): <!-- id: 48 -->
  - `test_information_digester_with_response_node_suspension` — ResponseNode suspends → digester gathers → ResponseNode resumes <!-- id: 44 -->
  - `test_information_digester_no_useful_context_path` — no context found → fallback reaches downstream <!-- id: 45 -->
  - `test_information_digester_enhanced_retrieval_end_to_end` — enhanced_context_retrieval → digest from cache <!-- id: 46 -->
  - `test_information_digester_propagation_to_parent_session` — digest propagates to parent's session_context <!-- id: 47 -->
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [x] Create `DigestedInformation` dataclass in `src/tinycua/tinycua/models/digested_information.py` <!-- id: 2 -->
  - [x] Define fields: `context_summary`, `key_points`, `advisory_instructions`, `constraints`, `known_gaps` <!-- id: 16 -->
  - [x] Add to `tinycua/models/__init__.py` exports <!-- id: 17 -->
- [x] Create `TinyCUAInformationDigesterNodeConfig` in `src/tinycua/tinycua/config/node_config.py` <!-- id: 3 -->
  - [x] Extend `NodeConfigBase` with `retrieval_enabled`, `max_digest_sources` <!-- id: 18 -->
  - [ ] `digest_schema` deferred to M4.2 when digest_information tool is fully implemented
- [x] Implement `TinyCUAInformationDigesterNode` class in `src/tinycua/tinycua/loops/information_digester.py` <!-- id: 4 -->
  - [x] Implement `__init__()` with `parent` parameter and config defaults (FR-001, FR-017, FR-018) <!-- id: 19 -->
  - [x] Implement `__call__()` with fresh session creation (FR-002, FR-003, FR-004) <!-- id: 20 -->
  - [x] Implement `_should_use_enhanced_retrieval()` (FR-006) <!-- id: 21 -->
  - [x] Implement `_invoke_enhanced_retrieval()` with cache behavior (FR-007, FR-008) <!-- id: 22 -->
  - [x] Implement `_produce_digest()` calling `digest_information` (FR-009, FR-010) <!-- id: 23 -->
  - [x] Implement `_produce_fallback()` with user query preservation (FR-011, FR-013) <!-- id: 24 -->
  - [x] Implement `on_complete()` with selected-output propagation (FR-005, FR-012) <!-- id: 25 -->
  - [x] Verify tool scope: only `enhanced_context_retrieval` and `digest_information` (FR-013) <!-- id: 26 -->
- [x] Add exports to `src/tinycua/tinycua/loops/__init__.py` <!-- id: 5 -->
  - [x] Add `TinyCUAInformationDigesterNode` to `__all__` <!-- id: 27 -->

> **Note**: Phase 2 items (ResponseNode suspension path → M3.6, full `enhanced_context_retrieval` tool → M4.2, full `digest_information` tool → M4.2) are intentionally deferred per design.md:322-328 and spec.md Open Questions. Do NOT implement in this milestone.

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 6 -->
- [x] Write unit tests for InformationDigesterNode <!-- id: 7 -->
  - [x] `test_fresh_session_created` <!-- id: 28 -->
  - [x] `test_does_not_inherit_parent_session` <!-- id: 29 -->
  - [x] `test_stores_only_own_output` <!-- id: 30 -->
  - [x] `test_propagates_to_parent` <!-- id: 31 -->
  - [x] `test_enhanced_retrieval_creates_cache` <!-- id: 32 -->
  - [x] `test_enhanced_retrieval_search_limited_to_cache` <!-- id: 33 -->
  - [x] `test_no_useful_context_fallback` <!-- id: 34 -->
  - [x] `test_digest_information_produces_structured_output` <!-- id: 35 -->
  - [x] `test_tool_scope_restricted` <!-- id: 36 -->
  - [x] `test_retry_on_empty_digest` <!-- id: 37 -->
  - [x] `test_chat_history_not_passed_wholesale` <!-- id: 38 -->
  - [x] `test_fallback_preserves_user_query` <!-- id: 39 -->
  - [x] `test_config_defaults_when_none` <!-- id: 40 -->
  - [x] `test_parent_parameter_accepted` <!-- id: 41 -->
  - [x] `test_does_not_execute_tasks` <!-- id: 42 -->
  - [x] `test_does_not_synthesize_response` <!-- id: 43 -->
  - [x] `test_retrieval_disabled_proceeds_with_input` <!-- id: 60 -->
  - [x] `test_cache_creation_failure_logs_and_proceeds` <!-- id: 61 -->
  - [x] `test_max_digest_sources_limits_context` <!-- id: 62 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 8 -->

## Verification Phase

- [x] Verify InformationDigesterNode creates fresh session with unique session_id <!-- id: 9 -->
- [x] Verify InformationDigesterNode stores only its own digest output, not copied input messages (SC-002) <!-- id: 49 -->
- [x] Verify digest output propagates to parent session via selected-output rule (SC-003, SC-008) <!-- id: 50 -->
- [x] Verify enhanced_context_retrieval lazily creates scoped cache (SC-004) <!-- id: 51 -->
- [x] Verify fallback continuation message format with user query preserved <!-- id: 10 -->
- [x] Verify input contains selected parent messages, not full session_context (SC-009) <!-- id: 52 -->
- [x] Verify tool scope is restricted to two tools only <!-- id: 11 -->
- [x] Verify retry behavior per NodeRetryPolicy before fallback (SC-011) <!-- id: 53 -->
- [x] Verify chat_history remains available for audit, not passed wholesale (SC-012) <!-- id: 54 -->
- [x] Verify enhanced_context_retrieval cache isolation — search/read operations do not escape cache boundaries <!-- id: 63 -->
- [x] Verify DigestedInformation output has all 5 required fields: context_summary, key_points, advisory_instructions, constraints, known_gaps <!-- id: 64 -->
- [x] Verify tinycua-sdk public API surface is unmodified (SC-014) <!-- id: 55 -->
- [x] Verify node does not execute tasks, mutate tasks, or synthesize responses (SC-015) <!-- id: 56 -->
- [x] Verify InformationDigesterNode proceeds without cache when `retrieval_enabled=False` (Edge Cases: retrieval disabled) <!-- id: 57 -->
- [x] Verify InformationDigesterNode logs error and produces partial digest on cache creation failure (SC-016) <!-- id: 58 -->
- [x] Verify InformationDigesterNode limits sources to `max_digest_sources` when exceeded (SC-017) <!-- id: 59 -->

## Documentation Phase

- [x] Update status tracker in `spec.md` to reflect completed items <!-- id: 12 -->

## Review and Merge

- [x] Create pull request <!-- id: 13 -->
- [x] Address review feedback <!-- id: 14 -->
- [ ] Merge to main branch <!-- id: 15 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-09*
