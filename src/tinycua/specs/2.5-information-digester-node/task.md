# Tasks: TinyCUAInformationDigesterNode

Implementation tasks for TinyCUAInformationDigesterNode. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write 4 end-to-end integration tests for InformationDigesterNode (spec-aligned; defined in implementation-plan.md): <!-- id: 48 -->
  - `test_information_digester_with_response_node_suspension` — ResponseNode suspends → digester gathers → ResponseNode resumes <!-- id: 44 -->
  - `test_information_digester_no_useful_context_path` — no context found → fallback reaches downstream <!-- id: 45 -->
  - `test_information_digester_enhanced_retrieval_end_to_end` — enhanced_context_retrieval → digest from cache <!-- id: 46 -->
  - `test_information_digester_propagation_to_parent_session` — digest propagates to parent's session_context <!-- id: 47 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Create `DigestedInformation` dataclass in `src/tinycua/tinycua/models/digested_information.py` <!-- id: 2 -->
  - [ ] Define fields: `context_summary`, `key_points`, `advisory_instructions`, `constraints`, `known_gaps` <!-- id: 16 -->
  - [ ] Add to `tinycua/models/__init__.py` exports <!-- id: 17 -->
- [ ] Create `TinyCUAInformationDigesterNodeConfig` in `src/tinycua/tinycua/config/node_config.py` <!-- id: 3 -->
  - [ ] Extend `NodeConfigBase` with `retrieval_enabled`, `max_digest_sources`, `digest_schema` <!-- id: 18 -->
- [ ] Implement `TinyCUAInformationDigesterNode` class in `src/tinycua/tinycua/loops/information_digester.py` <!-- id: 4 -->
  - [ ] Implement `__init__()` with `parent` parameter and config defaults (FR-001, FR-017, FR-018) <!-- id: 19 -->
  - [ ] Implement `__call__()` with fresh session creation (FR-002, FR-003, FR-004) <!-- id: 20 -->
  - [ ] Implement `_should_use_enhanced_retrieval()` (FR-006) <!-- id: 21 -->
  - [ ] Implement `_invoke_enhanced_retrieval()` with cache behavior (FR-007, FR-008) <!-- id: 22 -->
  - [ ] Implement `_produce_digest()` calling `digest_information` (FR-009, FR-010) <!-- id: 23 -->
  - [ ] Implement `_produce_fallback()` with user query preservation (FR-011, FR-013) <!-- id: 24 -->
  - [ ] Implement `on_complete()` with selected-output propagation (FR-005, FR-012) <!-- id: 25 -->
  - [ ] Verify tool scope: only `enhanced_context_retrieval` and `digest_information` (FR-013) <!-- id: 26 -->
- [ ] Add exports to `src/tinycua/tinycua/loops/__init__.py` <!-- id: 5 -->
  - [ ] Add `TinyCUAInformationDigesterNode` to `__all__` <!-- id: 27 -->

> **Note**: Phase 2 items (ResponseNode suspension path → M3.6, full `enhanced_context_retrieval` tool → M4.2, full `digest_information` tool → M4.2) are intentionally deferred per design.md:322-328 and spec.md Open Questions. Do NOT implement in this milestone.

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 6 -->
- [ ] Write unit tests for InformationDigesterNode <!-- id: 7 -->
  - [ ] `test_fresh_session_created` <!-- id: 28 -->
  - [ ] `test_does_not_inherit_parent_session` <!-- id: 29 -->
  - [ ] `test_stores_only_own_output` <!-- id: 30 -->
  - [ ] `test_propagates_to_parent` <!-- id: 31 -->
  - [ ] `test_enhanced_retrieval_creates_cache` <!-- id: 32 -->
  - [ ] `test_enhanced_retrieval_search_limited_to_cache` <!-- id: 33 -->
  - [ ] `test_no_useful_context_fallback` <!-- id: 34 -->
  - [ ] `test_digest_information_produces_structured_output` <!-- id: 35 -->
  - [ ] `test_tool_scope_restricted` <!-- id: 36 -->
  - [ ] `test_retry_on_failure` <!-- id: 37 -->
  - [ ] `test_chat_history_not_passed_wholesale` <!-- id: 38 -->
  - [ ] `test_fallback_preserves_user_query` <!-- id: 39 -->
  - [ ] `test_config_defaults_when_none` <!-- id: 40 -->
  - [ ] `test_parent_parameter_accepted` <!-- id: 41 -->
  - [ ] `test_does_not_execute_tasks` <!-- id: 42 -->
  - [ ] `test_does_not_synthesize_response` <!-- id: 43 -->
  - [ ] `test_retrieval_disabled_proceeds_with_input` <!-- id: 60 -->
  - [ ] `test_cache_creation_failure_logs_and_proceeds` <!-- id: 61 -->
  - [ ] `test_max_digest_sources_limits_context` <!-- id: 62 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 8 -->

## Verification Phase

- [ ] Verify InformationDigesterNode creates fresh session with unique session_id <!-- id: 9 -->
- [ ] Verify InformationDigesterNode stores only its own digest output, not copied input messages (SC-002) <!-- id: 49 -->
- [ ] Verify digest output propagates to parent session via selected-output rule (SC-003, SC-008) <!-- id: 50 -->
- [ ] Verify enhanced_context_retrieval lazily creates scoped cache (SC-004) <!-- id: 51 -->
- [ ] Verify fallback continuation message format with user query preserved <!-- id: 10 -->
- [ ] Verify input contains selected parent messages, not full session_context (SC-009) <!-- id: 52 -->
- [ ] Verify tool scope is restricted to two tools only <!-- id: 11 -->
- [ ] Verify retry behavior per NodeRetryPolicy before fallback (SC-011) <!-- id: 53 -->
- [ ] Verify chat_history remains available for audit, not passed wholesale (SC-012) <!-- id: 54 -->
- [ ] Verify enhanced_context_retrieval cache isolation — search/read operations do not escape cache boundaries <!-- id: 16 -->
- [ ] Verify DigestedInformation output has all 5 required fields: context_summary, key_points, advisory_instructions, constraints, known_gaps <!-- id: 17 -->
- [ ] Verify tinycua-sdk public API surface is unmodified (SC-014) <!-- id: 55 -->
- [ ] Verify node does not execute tasks, mutate tasks, or synthesize responses (SC-015) <!-- id: 56 -->
- [ ] Verify InformationDigesterNode proceeds without cache when `retrieval_enabled=False` (Edge Cases: retrieval disabled) <!-- id: 57 -->
- [ ] Verify InformationDigesterNode logs error and produces partial digest on cache creation failure (SC-016) <!-- id: 58 -->
- [ ] Verify InformationDigesterNode limits sources to `max_digest_sources` when exceeded (SC-017) <!-- id: 59 -->

## Documentation Phase

- [ ] Update status tracker in `spec.md` to reflect completed items <!-- id: 12 -->

## Review and Merge

- [ ] Create pull request <!-- id: 13 -->
- [ ] Address review feedback <!-- id: 14 -->
- [ ] Merge to main branch <!-- id: 15 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-09*
